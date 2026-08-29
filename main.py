import asyncio
import base64
import json
import os
import re
import sqlite3
import threading
import time
import urllib.request
from datetime import datetime
from typing import List, Optional

import cv2
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

import voice_module  # unchanged from the Tkinter version
from vision_module import FallDetector

DB_PATH = "hospital.db"

app = FastAPI(title="ULTRON Clinical Dashboard")

# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------


class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()
main_loop: Optional[asyncio.AbstractEventLoop] = None


def broadcast_threadsafe(message: dict):
    """Called from the background (non-async) video/voice threads."""
    if main_loop is not None:
        asyncio.run_coroutine_threadsafe(manager.broadcast(message), main_loop)


state = {
    "fall_detected": False,
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_patients():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT bed_id, patient_name, status, hr, bp, spo2, temp "
            "FROM patients ORDER BY bed_id ASC;"
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def ensure_log_table():
    conn = get_db_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alert_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                bed_id INTEGER,
                patient_name TEXT,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                acknowledged INTEGER DEFAULT 0
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def log_event(bed_id: Optional[int], patient_name: Optional[str], alert_type: str, message: str):
    """Persist an alert/spike event, then push it to any connected clients."""
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO alert_log (timestamp, bed_id, patient_name, alert_type, message) "
            "VALUES (?, ?, ?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), bed_id, patient_name, alert_type, message),
        )
        conn.commit()
    finally:
        conn.close()

    broadcast_threadsafe(
        {
            "type": "log",
            "message": f"[{alert_type.upper()}] {message}",
        }
    )


def fetch_logs(limit: int = 50):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, timestamp, bed_id, patient_name, alert_type, message, acknowledged "
            "FROM alert_log ORDER BY id DESC LIMIT ?;",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def _parse_hr(hr_str: Optional[str]) -> Optional[int]:
    match = re.search(r"\d+", hr_str or "")
    return int(match.group()) if match else None


# bed_id -> {"hr": int | None, "status": str} — used to detect spikes/transitions
# between vitals polls rather than re-alerting on every unchanged poll.
last_vitals_state: dict = {}
HR_SPIKE_DELTA = 15      # bpm change between polls that counts as a spike
HR_TACHYCARDIA = 110     # bpm considered high regardless of prior reading


def _check_vitals_for_alerts(patients: list):
    for p in patients:
        bed_id = p["bed_id"]
        hr = _parse_hr(p.get("hr"))
        prev = last_vitals_state.get(bed_id, {})
        prev_hr = prev.get("hr")
        prev_status = prev.get("status")

        if hr is not None:
            if prev_hr is not None and abs(hr - prev_hr) >= HR_SPIKE_DELTA:
                log_event(
                    bed_id, p["patient_name"], "hr_spike",
                    f"Bed {bed_id} HR changed {prev_hr} \u2192 {hr} bpm",
                )
            elif hr >= HR_TACHYCARDIA and (prev_hr is None or prev_hr < HR_TACHYCARDIA):
                log_event(
                    bed_id, p["patient_name"], "hr_high",
                    f"Bed {bed_id} HR at {hr} bpm (above {HR_TACHYCARDIA} bpm threshold)",
                )

        if p["status"] == "critical" and prev_status != "critical":
            log_event(
                bed_id, p["patient_name"], "status_critical",
                f"Bed {bed_id} status changed to critical (BP {p['bp']})",
            )

        last_vitals_state[bed_id] = {"hr": hr, "status": p["status"]}


# ---------------------------------------------------------------------------
# Vitals polling loop (replaces root.after(5000, fetch_database_data))
# ---------------------------------------------------------------------------


async def vitals_loop():
    while True:
        try:
            patients = fetch_patients()
            _check_vitals_for_alerts(patients)
            critical = [p for p in patients if p["status"] == "critical"]
            await manager.broadcast(
                {
                    "type": "vitals",
                    "patients": patients,
                    "critical_count": len(critical),
                    "critical": critical,
                }
            )
        except Exception as err:
            await manager.broadcast({"type": "log", "message": f"[DB Error]: {err}"})
        await asyncio.sleep(5)


# ---------------------------------------------------------------------------
# Video + fall detection worker (replaces update_video, runs in its own thread
# since cv2 capture is blocking)
# ---------------------------------------------------------------------------


def video_worker():
    detector = FallDetector(drop_threshold=0.12)
    cap = cv2.VideoCapture(0)

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None or frame.size == 0:
                time.sleep(0.05)
                continue

            resized = cv2.resize(frame, (480, 270))
            annotated, fall_now = detector.process_frame(resized)

            if fall_now and not state["fall_detected"]:
                state["fall_detected"] = True
                broadcast_threadsafe(
                    {
                        "type": "alert",
                        "fall": True,
                        "message": "ALERT: PATIENT DISTRESS DETECTED!",
                    }
                )
                log_event(None, "Camera feed", "fall", "Patient distress detected on camera")

            ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                b64 = base64.b64encode(buf).decode("utf-8")
                broadcast_threadsafe({"type": "video", "frame": b64})

            time.sleep(0.03)  # ~30fps cap, matches the old root.after(30, ...)
    finally:
        cap.release()
        detector.close()


# ---------------------------------------------------------------------------
# Voice / AI terminal (unchanged logic from app_ui.py, moved off the UI thread)
# ---------------------------------------------------------------------------


def query_ai(user_prompt: str) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return "Set OPENROUTER_API_KEY environment variable."

    try:
        db_context = json.dumps(fetch_patients())
    except Exception:
        db_context = "No database data currently loaded."

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "auto",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are ULTRON, a concise clinical assistant. Provide "
                    f"clear answers based on patient database: {db_context}"
                ),
            },
            {"role": "user", "content": user_prompt},
        ],
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data["choices"][0]["message"]["content"].strip()
    except Exception as err:
        return f"API Error: {err}"


def voice_worker():
    broadcast_threadsafe({"type": "voice_state", "listening": True})
    broadcast_threadsafe(
        {"type": "log", "message": "[Audio Engine]: Listening for voice input..."}
    )

    raw_cmd = voice_module.listen_command()

    if raw_cmd:
        cmd = raw_cmd.lower().strip()
        broadcast_threadsafe({"type": "log", "message": f"User: '{cmd}'"})

        if any(k in cmd for k in ["time", "clock"]):
            response = f"The current time is {datetime.now().strftime('%I:%M %p')}."
        elif any(k in cmd for k in ["date", "today"]):
            response = f"Today is {datetime.now().strftime('%A, %B %d, %Y')}."
        else:
            broadcast_threadsafe({"type": "log", "message": "OpenRouter AI thinking..."})
            response = query_ai(cmd)

        broadcast_threadsafe({"type": "log", "message": f"ULTRON: {response}"})
        voice_module.speak(response)
    else:
        broadcast_threadsafe(
            {"type": "log", "message": "[Audio Engine]: Speech uncaptured or timed out."}
        )

    broadcast_threadsafe({"type": "voice_state", "listening": False})


# ---------------------------------------------------------------------------
# FastAPI routes
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def on_startup():
    global main_loop
    main_loop = asyncio.get_event_loop()
    ensure_log_table()
    threading.Thread(target=video_worker, daemon=True).start()
    asyncio.create_task(vitals_loop())


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.post("/api/voice/trigger")
async def trigger_voice():
    threading.Thread(target=voice_worker, daemon=True).start()
    return {"status": "listening"}


@app.post("/api/alert/acknowledge")
async def acknowledge_alert():
    state["fall_detected"] = False
    log_event(None, None, "acknowledged", "All alerts acknowledged by staff")
    await manager.broadcast(
        {
            "type": "alert",
            "acknowledged": True,
            "message": "All alerts acknowledged by staff.",
        }
    )
    return {"status": "acknowledged"}


@app.get("/api/logs")
async def get_logs(limit: int = 50):
    return fetch_logs(limit)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        patients = fetch_patients()
        await ws.send_json(
            {
                "type": "vitals",
                "patients": patients,
                "critical_count": len([p for p in patients if p["status"] == "critical"]),
                "critical": [p for p in patients if p["status"] == "critical"],
            }
        )
        while True:
            # Client doesn't need to send anything; this just keeps the
            # connection open and detects disconnects.
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)