#!/usr/bin/env python3
import curses
import socket
import subprocess
import sys
import time
import signal
import threading
import queue
import re
from collections import deque

STREAM_URL = sys.argv[1] if len(sys.argv) > 1 else "tcp://10.0.0.1:6000"
INPUT_FORMAT = sys.argv[2] if len(sys.argv) > 2 else "mpegts"

# thresholds in seconds
STALL_WARN = 0.25
STALL_BAD = 0.75

FFMPEG_CMD = [
    "ffmpeg",
    "-nostdin",
    "-hide_banner",
    "-loglevel", "error",
    "-fflags", "nobuffer",
    "-flags", "low_delay",
    "-f", INPUT_FORMAT,
    "-i", "pipe:0",
    "-an",
    "-f", "null",
    "-",
    "-progress", "pipe:2",
    "-stats_period", "0.25",
]

TCP_RE = re.compile(r"^tcp://([^:/]+):(\d+)$")


def parse_tcp_url(url: str):
    m = TCP_RE.match(url)
    if not m:
        raise ValueError("Only tcp://host:port URLs are supported by this monitor")
    return m.group(1), int(m.group(2))


def format_hms_from_seconds(sec: float) -> str:
    if sec < 0:
        sec = 0.0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:05.2f}"


def format_hms_from_us(us_str: str) -> str:
    try:
        return format_hms_from_seconds(int(us_str) / 1_000_000)
    except Exception:
        return "--:--:--.--"


def human_bps(bps: float) -> str:
    units = ["b/s", "Kb/s", "Mb/s", "Gb/s"]
    i = 0
    while bps >= 1000 and i < len(units) - 1:
        bps /= 1000.0
        i += 1
    return f"{bps:5.2f} {units[i]}"


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


class SocketPump:
    def __init__(self, url: str):
        self.host, self.port = parse_tcp_url(url)
        self.sock = None
        self.thread = None
        self.stop_flag = threading.Event()
        self.byte_times = deque(maxlen=4000)   # (timestamp, nbytes)
        self.connected = False
        self.error = None

    def start(self, ffmpeg_stdin):
        self.sock = socket.create_connection((self.host, self.port), timeout=5)
        self.sock.settimeout(0.5)
        self.connected = True

        def run():
            try:
                while not self.stop_flag.is_set():
                    try:
                        data = self.sock.recv(64 * 1024)
                    except socket.timeout:
                        continue
                    if not data:
                        break
                    now = time.time()
                    self.byte_times.append((now, len(data)))
                    try:
                        ffmpeg_stdin.write(data)
                        ffmpeg_stdin.flush()
                    except BrokenPipeError:
                        break
            except Exception as e:
                self.error = str(e)
            finally:
                self.connected = False
                try:
                    ffmpeg_stdin.close()
                except Exception:
                    pass
                try:
                    if self.sock:
                        self.sock.close()
                except Exception:
                    pass

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_flag.set()
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass

    def bitrate_bps(self, window_sec=1.0):
        now = time.time()
        total = 0
        for ts, n in reversed(self.byte_times):
            if now - ts > window_sec:
                break
            total += n
        return 8.0 * total / window_sec


class ProgressReader:
    def __init__(self, stream):
        self.stream = stream
        self.q = queue.Queue()
        self.stop_flag = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        try:
            while not self.stop_flag.is_set():
                line = self.stream.readline()
                if not line:
                    break
                self.q.put(line.rstrip("\n"))
        except Exception:
            pass

    def drain(self):
        items = []
        while True:
            try:
                items.append(self.q.get_nowait())
            except queue.Empty:
                break
        return items

    def stop(self):
        self.stop_flag.set()


def main(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(150)

    ff = subprocess.Popen(
        FFMPEG_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=False,
        bufsize=0,
    )

    pump = SocketPump(STREAM_URL)
    pump.start(ff.stdin)

    # reopen stderr as text for progress parsing
    progress_reader = ProgressReader(
        open(ff.stderr.fileno(), mode="r", encoding="utf-8", errors="replace", closefd=False)
    )

    stats = {}
    start_time = time.time()

    # progress history: (wall_ts, media_sec)
    progress_hist = deque(maxlen=120)

    last_media_sec = 0.0
    last_media_advance_wall = time.time()
    stall_active = False
    current_stall = 0.0
    longest_stall = 0.0
    stall_count = 0

    rate_hist = deque(maxlen=40)
    lag_hist = deque(maxlen=40)

    def cleanup(*_):
        progress_reader.stop()
        pump.stop()
        try:
            ff.terminate()
        except Exception:
            pass

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    while True:
        ch = stdscr.getch()
        if ch in (ord("q"), ord("Q")):
            break

        # read ffmpeg progress updates
        for line in progress_reader.drain():
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            stats[k] = v
            if k == "out_time_us":
                now = time.time()
                try:
                    media_sec = int(v) / 1_000_000
                except Exception:
                    media_sec = last_media_sec

                progress_hist.append((now, media_sec))

                if media_sec > last_media_sec + 1e-6:
                    if stall_active:
                        stall_active = False
                        current_stall = 0.0
                    last_media_advance_wall = now
                    last_media_sec = media_sec
                else:
                    current_stall = now - last_media_advance_wall

        now = time.time()
        elapsed = now - start_time

        # stall logic
        gap = now - last_media_advance_wall
        if gap > STALL_WARN:
            if not stall_active:
                stall_active = True
                stall_count += 1
            current_stall = gap
            if current_stall > longest_stall:
                longest_stall = current_stall
        else:
            current_stall = 0.0

        # playback rate over recent window
        playback_rate = 0.0
        if len(progress_hist) >= 2:
            t0, m0 = progress_hist[0]
            t1, m1 = progress_hist[-1]
            dtw = max(1e-6, t1 - t0)
            dtm = max(0.0, m1 - m0)
            playback_rate = dtm / dtw
            rate_hist.append(playback_rate)

        avg_rate = sum(rate_hist) / len(rate_hist) if rate_hist else 0.0

        # lag = wall elapsed - media elapsed
        lag = max(0.0, elapsed - last_media_sec)
        lag_hist.append(lag)
        avg_lag = sum(lag_hist) / len(lag_hist) if lag_hist else lag

        # jitter: stddev-like roughness of instantaneous progress ratios
        inst_rates = []
        if len(progress_hist) >= 3:
            items = list(progress_hist)[-12:]
            for i in range(1, len(items)):
                (ta, ma), (tb, mb) = items[i - 1], items[i]
                dtw = tb - ta
                if dtw > 0:
                    inst_rates.append(max(0.0, (mb - ma) / dtw))
        if inst_rates:
            mean_r = sum(inst_rates) / len(inst_rates)
            var = sum((r - mean_r) ** 2 for r in inst_rates) / len(inst_rates)
            jitter = var ** 0.5
        else:
            jitter = 0.0

        recv_bps = pump.bitrate_bps(1.0)

        # status
        if ff.poll() is not None:
            status = "EXITED"
        elif not pump.connected and pump.error:
            status = "SOCKET_ERR"
        elif current_stall > STALL_BAD:
            status = "STALLING"
        elif current_stall > STALL_WARN:
            status = "HICCUP"
        elif avg_rate < 0.9:
            status = "BEHIND"
        elif avg_rate > 1.1:
            status = "CATCHUP"
        else:
            status = "PLAYING"

        max_y, max_x = stdscr.getmaxyx()

        def safe_addstr(y, x, s, attr=0):
            if y < 0 or y >= max_y or x >= max_x:
                return
            width = max_x - x - 1
            if width <= 0:
                return
            try:
                stdscr.addstr(y, x, str(s)[:width], attr)
            except curses.error:
                pass

        stdscr.erase()

        status_attr = curses.A_BOLD
        if status in ("STALLING", "SOCKET_ERR", "EXITED"):
            status_attr |= curses.A_REVERSE

        lines = [
            ("Realtime Stream QoE Monitor", curses.A_BOLD),
            (f"Source   : {STREAM_URL}", 0),
            (f"Status   : {status}", status_attr),
            (f"Playtime : {format_hms_from_seconds(last_media_sec)}", 0),
            (f"Rate now : {playback_rate:0.2f}x", 0),
            (f"Rate avg : {avg_rate:0.2f}x", 0),
            (f"Lag now  : {lag:0.2f}s", 0),
            (f"Lag avg  : {avg_lag:0.2f}s", 0),
            (f"Recv     : {human_bps(recv_bps)}", 0),
            (f"Stalls   : {stall_count}", 0),
            (f"CurrStall: {current_stall:0.2f}s", 0),
            (f"MaxStall : {longest_stall:0.2f}s", 0),
            (f"Jitter   : {jitter:0.2f}", 0),
            ("", 0),
            ("Interpretation:", curses.A_BOLD),
            ("rate<1.0 => media progress slower than real time", 0),
            ("stall>0.25s => visible hiccup likely", 0),
            ("lag growth => buffering or bursty delivery", 0),
            ("Press q to quit", 0),
        ]

        for i, (txt, attr) in enumerate(lines):
            safe_addstr(i, 1, txt, attr)

        # tiny bars if there is room
        bar_y = len(lines) + 1
        if bar_y + 2 < max_y:
            def bar(label, value, scale=1.0):
                frac = clamp(value / scale, 0.0, 1.0)
                width = max(10, min(30, max_x - 22))
                fill = int(width * frac)
                return f"{label:<8} [{'#' * fill}{'.' * (width - fill)}] {value:0.2f}"

            safe_addstr(bar_y, 1, bar("Rate", avg_rate, 1.0))
            safe_addstr(bar_y + 1, 1, bar("Stall", current_stall, 1.0))
            safe_addstr(bar_y + 2, 1, bar("Lag", lag, 3.0))

        stdscr.refresh()
        time.sleep(0.1)

    cleanup()


if __name__ == "__main__":
    curses.wrapper(main)