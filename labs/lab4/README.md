# Lab 4

Start here:

- `lab4.md`
  Marp slide deck for the lab walkthrough and exercises.
- `demo/run.py`
  Instructor-led demo of a bandwidth-protected slice on the standard path.
- `demo/slice_request.py`
  Fixed request to inspect when the demo pauses after Phase 2.
- `exercises/part1/run.py`
  Ask for a low-latency slice by editing `exercises/part1/slice_request.py`.
- `exercises/part2/run.py`
  Express a standard-latency service chain by editing `exercises/part2/slice_request.py`.
- `exercises/part3/run.py`
  See how bandwidth limits can cause a slice request to be rejected by editing
  `exercises/part3/slice_request.py`.

Reference answers:

- `solutions/part1/slice_request.py`
- `solutions/part2/slice_request.py`
- `solutions/part3/slice_request.py`

Notes:

- Participants should focus on the `SLICE_REQUEST` block in each demo/exercise.
- The demo runner pauses after Phase 2 and asks learners to inspect
  `demo/slice_request.py` before the slice is applied.
- Each exercise runner pauses and asks learners to edit the local
  `slice_request.py` file in that part's folder.
- The exercise printout includes the topology roles, so participants can map
  service requirements to `waypoints` without reading controller code.
- The `_internal/` folder contains the topology, controller, and helper code.
- The low-latency case is taught through Exercise 1, so there is only one main demo.
