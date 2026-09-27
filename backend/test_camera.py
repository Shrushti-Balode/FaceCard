import cv2

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Camera FAILED")
    exit()

print("Camera OPENED ✓")

while True:
    ok, frame = cap.read()
    if not ok:
        print("READ FAILED")
        break

    print("Frame OK:", frame.shape, frame.dtype)
    cv2.imshow("TestCam", frame)

    if cv2.waitKey(1) == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
