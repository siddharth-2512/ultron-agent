[README (1).md](https://github.com/user-attachments/files/31600613/README.1.md)
# ULTRON — Ward 4B Clinical Dashboard (Web version)

FastAPI backend + a single dark-themed HTML/Tailwind-style frontend, replacing
the Tkinter UI. Live vitals, camera feed, and fall detection all stream over
one WebSocket instead of `root.after()` polling and a `Label` widget.

## What changed from `app_ui.py`

| Old (Tkinter) | New (Web) |
|---|---|
| `root.after(5000, fetch_database_data)` | `vitals_loop()` — async task, broadcasts over WebSocket every 5s |
| `update_video()` on the Tk main loop | `video_worker()` — runs in its own thread, encodes frames as JPEG/base64, pushes over WebSocket |
| HOG people-detector + bbox-delta fall logic | `vision_module.FallDetector` — MediaPipe Pose, tracks nose landmark y-delta, draws full skeleton overlay |
| `self.log_box.insert(...)` | `{"type": "log", ...}` WebSocket message, appended to the terminal panel in JS |
| `self.banner.config(...)` on fall detection | `{"type": "alert", "fall": true}` message, JS flips the banner styling |
| `acknowledge_alert()` button command | `POST /api/alert/acknowledge` |
| `trigger_voice()` button command | `POST /api/voice/trigger` — same `voice_module.listen_command()` / `query_ai()` logic, just run in a background thread and reported back over the WebSocket |

The DB layer, fall-detection math, and the OpenRouter `query_ai()` call are
carried over essentially unchanged — only the wiring on top changed.

## Setup

1. Copy your existing `voice_module.py` into this folder (it's referenced
   but not part of the files you shared, so it isn't included here).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Build the database (same as before):
   ```bash
   python setup_db.py
   ```
4. Run the server:
   ```bash
   python main.py
   ```
   or with auto-reload while developing:
   ```bash
   uvicorn main:app --reload
   ```
5. Open **http://localhost:8000** in a browser.

## Notes

- **Alert / spike logging**: every fall detection, patient-status change to
  `critical`, HR change ≥15bpm between polls, and manual acknowledgment now
  gets written to a new `alert_log` table in `hospital.db` (auto-created on
  startup — no need to re-run `setup_db.py`). Pull history via
  `GET /api/logs?limit=50`. Since the seed data in `hospital.db` is static,
  HR-spike/tachycardia logging won't fire on its own until something is
  actually writing new vitals into the `patients` table over time (a real
  sensor feed, or a script simulating one).

- `vision_module.py` uses the **MediaPipe Tasks API** (`PoseLandmarker`),
  not the legacy `mp.solutions.pose` API. Recent `mediapipe` pip releases
  have a known packaging issue where `mp.solutions` is missing/broken on
  some platforms — the Tasks API is the currently-working, actively
  supported path. On first run it auto-downloads a small (~5-6MB) pose
  model file (`pose_landmarker_lite.task`) into the project folder — this
  needs internet access once, then it's cached locally.
- `vision_module.py` was refactored from a standalone script (its own
  `while` loop + `cv2.imshow` window) into an importable `FallDetector`
  class. `video_worker()` in `main.py` now owns the single capture loop and
  calls `detector.process_frame(frame)` once per frame — don't run the old
  script's `while cap.isOpened(): ... cv2.imshow(...)` version standalone
  anymore, it'll fight over the camera with the server.
- `OPENROUTER_API_KEY` still needs to be set as an environment variable for
  the "Ask ULTRON" voice queries to work.
- The camera (`cv2.VideoCapture(0)`) opens once on server startup and stays
  open for as long as the server runs.
- If you deploy this anywhere other than `localhost`, switch the WebSocket
  scheme to `wss://` behind HTTPS (the frontend already detects this
  automatically) and consider adding auth — right now `/ws` and the API
  routes are unauthenticated.
