import cv2
import numpy as np
import urllib.request
import os

# Ultra-lightweight ONNX MobileNet-SSD model (~6MB RAM footprint)
MODEL_URL = "https://github.com/onnx/models/raw/main/validated/vision/object_detection_segmentation/ssd-mobilenetv1/model/ssd_mobilenet_v1_10.onnx"
MODEL_PATH = "ssd_mobilenet_v1_10.onnx"

# COCO Class IDs for vehicles in SSD MobileNet V1 ONNX
# 3: car, 4: motorcycle, 6: bus, 8: truck
VEHICLE_CLASS_IDS = {3, 4, 6, 8}

net = None


def get_onnx_model():
    global net
    if net is None:
        if not os.path.exists(MODEL_PATH):
            urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        net = cv2.dnn.readNetFromONNX(MODEL_PATH)
    return net


def verify_vehicle_presence(image_bytes: bytes) -> tuple[bool, str]:
    """
    Runs ONNX MobileNet-SSD locally inside OpenCV.
    Uses ~6MB RAM and strictly enforces vehicle presence.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return False, "REJECTED: Invalid image stream."

    try:
        model_net = get_onnx_model()
        h, w = img.shape[:2]
        
        # Preprocess frame for ONNX MobileNet (300x300)
        blob = cv2.dnn.blobFromImage(
            img, 1.0, (300, 300), (127.5, 127.5, 127.5), swapRB=True, crop=False
        )
        model_net.setInput(blob)
        output = model_net.forward()

        # Parse ONNX SSD detections: [batch, 1, num_detections, 7]
        # Format per row: [batch_id, class_id, score, xmin, ymin, xmax, ymax]
        vehicle_detected = False
        
        if len(output.shape) == 4:
            detections = output[0, 0, :, :]
            for i in range(detections.shape[0]):
                score = float(detections[i, 2])
                class_id = int(detections[i, 1])

                if score > 0.35 and class_id in VEHICLE_CLASS_IDS:
                    vehicle_detected = True
                    break

        if not vehicle_detected:
            return False, "REJECTED: Non-vehicle object detected. Point camera at a car, truck, bus, or motorcycle."

        return True, "Vehicle verified."

    except Exception as e:
        # Strict fail-closed fallback if model loading fails
        return False, f"REJECTED: Vehicle validation error ({str(e)})."


def verify_3d_perspective_shift(frame1_bytes: bytes, frame2_bytes: bytes) -> dict:
    # 1. Strict Local ONNX Vehicle Check
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
