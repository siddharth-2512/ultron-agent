import threading
import cv2
import mediapipe as mp
import voice_module

# Global flag to manage active tracking state
RUNNING = True


def vision_thread():
    """Runs MediaPipe pose tracking in a separate thread."""
    global RUNNING
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)
    mp_draw = mp.solutions.drawing_utils

    cap = cv2.VideoCapture(0)
    prev_y = None

    print("[ULTRON System] Vision Feed active.")

    while cap.isOpened() and RUNNING:
        ret, frame = cap.read()
        if not ret:
            break

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb_frame)

        if results.pose_landmarks:
            mp_draw.draw_landmarks(frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
            nose = results.pose_landmarks.landmark[0]
            current_y = nose.y

            if prev_y is not None and (current_y - prev_y) > 0.12:
                cv2.putText(frame, "ALERT: DISTRESS DETECTED!", (30, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 3)

            prev_y = current_y

        cv2.imshow("ULTRON Guardian - Main View", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            RUNNING = False
            break

    cap.release()
    cv2.destroyAllWindows()


def main():
    global RUNNING
    voice_module.speak("ULTRON System Online. Monitoring active.")

    # Start Vision in a background thread
    v_thread = threading.Thread(target=vision_thread, daemon=True)
    v_thread.start()

    # Main thread handles continuous voice listening loop
    while RUNNING:
        command = voice_module.listen_command().lower()

        if "status" in command:
            voice_module.speak("All systems nominal. Patient status stable.")
        elif "emergency" in command or "help" in command:
            voice_module.speak("Warning. Dispatching assistance immediately.")
        elif "stop" in command or "exit" in command:
            voice_module.speak("Shutting down ULTRON guardian.")
            RUNNING = False
            break


if __name__ == "__main__":
    main()