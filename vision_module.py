import os
import time
import urllib.request

import cv2
import mediapipe as mp

# The legacy `mp.solutions.pose` API is broken in current mediapipe pip
# releases on some platforms (a known, currently open packaging issue).
# This uses the actively-supported Tasks API (PoseLandmarker) instead.

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
)
MODEL_PATH = os.path.join(os.path.dirname(__file__), "pose_landmarker_lite.task")

# Reduced skeleton connections (landmark index pairs) for drawing the
# overlay. Full 33-point reference:
# https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker
POSE_CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),  # shoulders + arms
    (11, 23), (12, 24), (23, 24),                      # torso
    (23, 25), (25, 27), (24, 26), (26, 28),            # legs
    (27, 29), (29, 31), (28, 30), (30, 32),            # feet
]

NOSE_INDEX = 0


def _ensure_model():
    if not os.path.exists(MODEL_PATH):
        print("[ULTRON] Downloading pose landmarker model (first run only)...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("[ULTRON] Model downloaded.")


class FallDetector:
    """Pose-based fall / sudden-motion detector.

    Call process_frame(frame) once per captured frame. It draws the
    skeleton overlay in place and returns whether a fall was detected
    on this frame.
    """

    def __init__(self, drop_threshold: float = 0.12):
        _ensure_model()

        base_options = mp.tasks.BaseOptions(model_asset_path=MODEL_PATH)
        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_poses=1,
        )
        self.landmarker = mp.tasks.vision.PoseLandmarker.create_from_options(options)

        self.drop_threshold = drop_threshold
        self.prev_y = None
        self._start_time = time.time()

    def _timestamp_ms(self) -> int:
        return int((time.time() - self._start_time) * 1000)

    def process_frame(self, frame):
        """
        frame: BGR frame from cv2.VideoCapture, modified in place with the
               skeleton overlay (and an ALERT caption if a fall is detected).
        Returns: (frame, fall_detected: bool)
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        result = self.landmarker.detect_for_video(mp_image, self._timestamp_ms())

        fall_detected = False

        if result.pose_landmarks:
            landmarks = result.pose_landmarks[0]
            h, w = frame.shape[:2]

            for a, b in POSE_CONNECTIONS:
                if a < len(landmarks) and b < len(landmarks):
                    pa, pb = landmarks[a], landmarks[b]
                    cv2.line(
                        frame,
                        (int(pa.x * w), int(pa.y * h)),
                        (int(pb.x * w), int(pb.y * h)),
                        (0, 255, 0),
                        2,
                    )
            for lm in landmarks:
                cv2.circle(frame, (int(lm.x * w), int(lm.y * h)), 3, (0, 200, 255), -1)

            current_y = landmarks[NOSE_INDEX].y

            if self.prev_y is not None:
                dy = current_y - self.prev_y
                if dy > self.drop_threshold:
                    fall_detected = True
                    cv2.putText(
                        frame,
                        "ALERT: PATIENT DISTRESS DETECTED!",
                        (20, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 0, 255),
                        2,
                    )

            self.prev_y = current_y
        else:
            # No pose in frame — don't let a stale prev_y trigger a false
            # delta once the subject reappears.
            self.prev_y = None

        return frame, fall_detected

    def close(self):
        self.landmarker.close()