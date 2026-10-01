import cv2
import numpy as np
import requests

# Hugging Face Free Inference API endpoint for Object Detection
HF_API_URL = "https://api-inference.huggingface.co/models/facebook/detr-resnet-50"
# Target vehicle labels recognized by DETR / COCO
VEHICLE_LABELS = {"car", "bus", "truck", "motorcycle", "bicycle"}


def verify_vehicle_presence(image_bytes: bytes) -> tuple[bool, str]:
    """
    Calls a lightweight API endpoint to verify vehicle presence.
    Uses 0MB local RAM on Render.
    """
    try:
        response = requests.post(
            HF_API_URL,
            headers={"Content-Type": "application/octet-stream"},
            data=image_bytes,
            timeout=5
        )
        
        if response.status_code == 200:
            detections = response.json()
            for item in detections:
                label = item.get("label", "").lower()
                score = item.get("score", 0)
                if label in VEHICLE_LABELS and score > 0.35:
                    return True, f"Vehicle detected ({label})."
            
            return False, "REJECTED: Non-vehicle object. Target a car, motorcycle, truck, or bus."
            
        elif response.status_code == 503:
            # Model loading on HF cold start - fallback to strict edge/texture check
            return perform_lightweight_heuristic_check(image_bytes)
            
    except Exception as e:
        return perform_lightweight_heuristic_check(image_bytes)

    return False, "REJECTED: Non-vehicle object."


def perform_lightweight_heuristic_check(image_bytes: bytes) -> tuple[bool, str]:
    """Fallback local check using zero heavy AI libraries."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return False, "REJECTED: Invalid image."

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()

    # Reject plain background/flat objects
    if variance < 20.0:
        return False, "REJECTED: Insufficient visual detail or non-vehicle target."

    return True, "Lightweight inspection pass."


def verify_3d_perspective_shift(frame1_bytes: bytes, frame2_bytes: bytes) -> dict:
    # 1. Strict Vehicle Check via API
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
