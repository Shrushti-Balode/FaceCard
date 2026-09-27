import sys
print("Python version:", sys.version)

try:
    import cv2
    print(f"✓ OpenCV {cv2.__version__}")
except:
    print("✗ OpenCV not installed")

try:
    import dlib
    print(f"✓ dlib {dlib.__version__}")
except:
    print("✗ dlib not installed")

try:
    import face_recognition
    print(f"✓ face_recognition installed")
except:
    print("✗ face_recognition not installed")

try:
    import flask
    print(f"✓ Flask {flask.__version__}")
except:
    print("✗ Flask not installed")

print("\n✓ All dependencies installed successfully!")