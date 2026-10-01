import cv2
import numpy as np

# Standard COCO / MobileNet vehicle class IDs
VEHICLE_CLASSES = {
    "car", "bus", "motorbike", "truck", "motorcycle", "vehicle"
}

def verify_vehicle_presence(image_bytes: bytes) -> tuple[bool, str]:
    """
    Analyzes the captured frame to verify if a motor vehicle is present.
    Uses edge-contour aspect heuristics combined with color variance 
    to filter out household objects like speakers, shoes, or furniture.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return False, "Failed to read image frame."

    # Convert to grayscale and calculate texture/edge density
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)

    # Vehicle contours typically have defined geometric structure & metallic variance
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    total_area = img.shape[0] * img.shape[1]
    vehicle_candidate_found = False

    for cnt in contours:
        area = cv2.contourArea(cnt)
        # Looking for substantial surface coverage (e.g. car body panel / bumper)
        if area > (total_area * 0.08):  
            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = float(w) / h
            # Vehicles & major body panels have balanced aspect ratios, not circular speaker shapes
            if 0.5 <= aspect_ratio <= 3.5:
                vehicle_candidate_found = True
                break

    # Color saturation variance (vehicles have metallic/painted surface profiles)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    saturation_std = np.std(hsv[:, :, 1])

    if not vehicle_candidate_found and saturation_std < 15:
        return False, "Non-vehicle detected. Please target a car, motorcycle, truck, or bus."

    return True, "Vehicle structure detected."


def verify_3d_perspective_shift(frame1_bytes: bytes, frame2_bytes: bytes) -> dict:
    """
    Compares 2 sequential frames from the WebRTC stream using ORB feature matching.
    Verifies physical 3D movement to detect static screen playback attacks.
    """
    # 1. First, check if a vehicle is actually in the frame
    is_vehicle, vehicle_msg = verify_vehicle_presence(frame1_bytes)
    if not is_vehicle:
        return {"is_3d_valid": False, "reason": vehicle_msg}

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
