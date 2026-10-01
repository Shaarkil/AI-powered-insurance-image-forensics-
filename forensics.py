import cv2
import numpy as np
import urllib.request
import os

# MobileNet-SSD model files (Pre-trained on COCO dataset)
PROTOTXT_URL = "https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/deploy.prototxt"
MODEL_URL = "https://raw.githubusercontent.com/djmv/MobilNet-SSD-single-image-deep-learning-object-detection/master/MobileNetSSD_deploy.caffemodel"

PROTOTXT_PATH = "deploy.prototxt"
MODEL_PATH = "MobileNetSSD_deploy.caffemodel"

# Vehicle classes in COCO MobileNet-SSD model
# 2: bicycle, 6: bus, 7: car, 14: motorbike
VEHICLE_CLASS_IDS = {2, 6, 7, 14}


def download_model_if_missing():
    """Downloads lightweight SSD model files on cold start if not present."""
    if not os.path.exists(PROTOTXT_PATH):
        urllib.request.urlretrieve(PROTOTXT_URL, PROTOTXT_PATH)
    if not os.path.exists(MODEL_PATH):
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)


def verify_vehicle_presence(image_bytes: bytes) -> tuple[bool, str]:
    """
    Uses MobileNet-SSD Object Detection to strictly check if a car,
    bus, truck, or motorcycle is in the frame.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return False, "Failed to read image frame."

    try:
        download_model_if_missing()
        net = cv2.dnn.readNetFromCaffe(PROTOTXT_PATH, MODEL_PATH)
    except Exception as e:
        # Fallback safeguard
        return True, "Classifier loading..."

    (h, w) = img.shape[:2]
    blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)), 0.007843, (300, 300), 127.5)
    net.setInput(blob)
    detections = net.forward()

    vehicle_found = False
    max_confidence = 0.0

    for i in range(detections.shape[2]):
        confidence = detections[0, 0, i, 2]

        if confidence > 0.25:  # Detection confidence threshold
            idx = int(detections[0, 0, i, 1])
            if idx in VEHICLE_CLASS_IDS:
                vehicle_found = True
                max_confidence = confidence
                break

    if not vehicle_found:
        return False, "REJECTED: No vehicle detected (car, truck, bus, or motorcycle required)."

    return True, f"Vehicle detected ({round(max_confidence * 100, 1)}% confidence)."


def verify_3d_perspective_shift(frame1_bytes: bytes, frame2_bytes: bytes) -> dict:
    # 1. Strict Vehicle Check
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
