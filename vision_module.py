import cv2
import mediapipe as mp

# Initialize MediaPipe Pose module
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)
mp_draw = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0)
prev_y = None

print("[ULTRON] Physical Vision Engine Online...")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = pose.process(rgb_frame)

    if results.pose_landmarks:
        # Draw skeleton keypoints
        mp_draw.draw_landmarks(frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

        # Extract Nose Keypoint (Landmark 0)
        nose = results.pose_landmarks.landmark[0]
        current_y = nose.y

        # Detect rapid downward posture shift
        if prev_y is not None:
            dy = current_y - prev_y
            if dy > 0.12:  # Posture drop threshold
                cv2.putText(frame, "ALERT: PATIENT DISTRESS DETECTED!", (30, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 3)
                print("[ALERT] Patient sudden motion/fall detected!")

        prev_y = current_y

    cv2.imshow("ULTRON Guardian - Physical Feed", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()