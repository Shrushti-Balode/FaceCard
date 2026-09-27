import argparse

import cv2


parser = argparse.ArgumentParser(description="Capture one camera frame without opening a window by default.")
parser.add_argument("--display", action="store_true", help="Try to display the captured frame using OpenCV HighGUI.")
args = parser.parse_args()

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW if hasattr(cv2, "CAP_DSHOW") else 0)
try:
    if not cap.isOpened():
        raise SystemExit("Camera could not be opened")

    ok, frame = cap.read()
    if not ok:
        raise SystemExit("Camera opened, but frame capture failed")

    print(f"Camera opened; frame captured: {frame.shape} {frame.dtype}")
    if args.display:
        try:
            cv2.imshow("Camera diagnostic", frame)
            cv2.waitKey(0)
        except cv2.error as error:
            print(f"OpenCV GUI display unavailable; frame capture itself succeeded: {error}")
finally:
    cap.release()
    if args.display:
        try:
            cv2.destroyAllWindows()
        except cv2.error:
            pass
