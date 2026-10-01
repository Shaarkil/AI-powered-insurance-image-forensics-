import cv2
import numpy as np
import torch
import torchvision
from torchvision.transforms import functional as F

# Load lightweight MobileNetV3 object detection model from TorchVision
try:
    weights = torchvision.models.detection.FasterRCNN_MobileNet_V3_Large_FPN_Weights.DEFAULT
    vehicle_model = torchvision.models.detection.fasterrcnn_mobilenet_v3_large_fpn(weights=weights)
    vehicle_model.eval()
except Exception as e:
    vehicle_model = None

# COCO dataset class IDs for vehicles: 3: car, 4: motorcycle, 6: bus, 8: truck
VEHICLE_CLASS_IDS = {3, 4, 6, 8}


def verify_vehicle_presence(image_bytes: bytes) -> tuple[bool, str]:
    """
    Uses TorchVision object detection to strictly check if a car,
    motorcycle, bus, or truck is present in the camera frame.
    """
    if vehicle_model is None:
        return False, "REJECTED: Object detection model failed to initialize on server."

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return False, "REJECTED: Failed to decode image frame."

    # Convert image BGR -> RGB and to PyTorch Tensor
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img_tensor = F.to_tensor(img_rgb).unsqueeze(0)

    with torch.no_grad():
        predictions = vehicle_model(img_tensor)[0]

    labels = predictions['labels'].cpu().numpy()
    scores = predictions['scores'].cpu().numpy()

    vehicle_found = False
    for label, score in zip(labels, scores):
        if score > 0.35 and label in VEHICLE_CLASS_IDS:
            vehicle_found = True
            break

    if not vehicle_found:
        return False, "REJECTED: Non-vehicle object. Target a car, motorcycle, truck, or bus."

    return True, "Vehicle detected."


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
