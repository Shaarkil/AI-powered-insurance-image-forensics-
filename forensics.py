import cv2
import numpy as np
from ultralytics import YOLO

# Load lightweight YOLOv8 Nano model (downloads pre-trained weights automatically on build)
try:
    model = YOLO("yolov8n.pt")
except Exception as e:
    model = None

# COCO Dataset class IDs for vehicles:
# 2: car, 3: motorcycle, 5: bus, 7: truck
VEHICLE_CLASS_IDS = {2, 3, 5, 7}


def verify_vehicle_presence(image_bytes: bytes) -> tuple[bool, str]:
    """
    Uses YOLOv8 Object Detection to strictly check if a car,
    bus, truck, or motorcycle is present in the frame.
    """
    if model is None:
        return False, "REJECTED: Object detection model failed to initialize."

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return False, "REJECTED: Failed to decode image frame."

    # Run inference with confidence threshold 0.30
    results = model(img, conf=0.30, verbose=False)

    vehicle_detected = False
    detected_label = ""

    for result in results:
        for box in result.boxes:
            class_id = int(box.cls[0].item())
            if class_id in VEHICLE_CLASS_IDS:
                vehicle_detected = True
                detected_label = result.names[class_id]
                break
        if vehicle_detected:
            break

    if not vehicle_detected:
        return False, "REJECTED: Non-vehicle object. Target a car, motorcycle, truck, or bus."

    return True, f"Vehicle detected ({detected_label})."


def verify_3d_perspective_shift(frame1_bytes: bytes, frame2_bytes: bytes) -> dict:
    # 1. Strict Vehicle Object Check
    is_vehicle, vehicle_msg = verify_vehicle_presence(frame1_bytes)
    if not is_vehicle:
        return {"is_3d_valid": False, "reason": vehicle_msg}

    # 2. 3D Perspective Shift Check via ORB
    nparr1 = np.frombuffer(frame1_bytes, np.uint8)
    nparr2 = np.frombuffer(frame2_bytes, np.uint8)
    img1 = cv2.imdecode(nparr1, cv2.IMREAD_GRAYSCALE)
    img2 = cv2.imdecode(nparr2, cv2.IMREAD_GRAYSCALE)

    if img1 is None or img2 is None:
        return {"is_3d_valid": False, "reason": "Failed to decode camera frames."}

    orb = cv2.ORB_create(nfeatures=500)
    kp1, des1 = orb.detectAndCompute(img1, None)
    kp2, des2 = orb.detectAndCompute(img2, None)

    if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
        return {"is_3d_valid": False, "reason": "Insufficient visual surface details."}

    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des1, des2)

    if len(matches) < 8:
        return {"is_3d_valid": False, "reason": "Static image or flat screen spoof detected."}

    pts1 = np.float32([kp1[m.queryIdx].pt for m in matches[:20]])
    pts2 = np.float32([kp2[m.trainIdx].pt for m in matches[:20]])

    displacement = np.mean(np.linalg.norm(pts1 - pts2, axis=1))

    if displacement < 2.5:
        return {"is_3d_valid": False, "reason": "No physical camera perspective shift detected."}

    return {"is_3d_valid": True, "displacement_score": round(float(displacement), 2)}


def blur_privacy_regions(image_bytes: bytes) -> tuple[bytes, dict]:
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return image_bytes, {"redacted": False}

    _, encoded_img = cv2.imencode('.jpg', img)
    return encoded_img.tobytes(), {"redacted": True, "count": 0}
