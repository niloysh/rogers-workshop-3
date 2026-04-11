#!/usr/bin/env python3
"""
Tiny Lab 3 HTTP server for h2.

It returns small 200 OK responses for the handful of paths used in the lab so
students can focus on SRv6 steering and IDS behavior instead of HTTP 404s.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer


RESPONSES = {
    "/": "h2 HTTP server is running.\n",
    "/index.html": "This is a normal sample request.\n",
    "/malware": "This is a sample malware request used for IDS detection.\n",
    "/test": "This is a sample test request.\n",
    "/exploit": "This is a sample exploit request used for IDS detection.\n",
}


class Lab3Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = RESPONSES.get(
            self.path,
            f"This is a sample response for {self.path}.\n",
        ).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        body = RESPONSES.get(
            self.path,
            f"This is a sample response for {self.path}.\n",
        ).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()

    def log_message(self, format, *args):
        print(f"[h2 http] {self.address_string()} - {format % args}")


def main():
    server = HTTPServer(("0.0.0.0", 80), Lab3Handler)
    print("Serving Lab 3 HTTP responses on 0.0.0.0:80")
    server.serve_forever()


if __name__ == "__main__":
    main()
