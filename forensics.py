import cv2
import numpy as np
import os
import urllib.request

# Include all common road transport indices in MobileNet SSD
VEHICLE_CLASSES = {7: "car", 6: "bus", 14: "motorbike", 19: "train"}

PROTO_PATH = "deploy.prototxt"
MODEL_PATH = "mobilenet_iter_73000.caffemodel"

PROTO_URL = "https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/deploy.prototxt"
MODEL_URL = "https://github.com/djmv/MobilNet-SSD-caffemodel/raw/master/mobilenet_iter_73000.caffemodel"

def ensure_model_exists():
    if not os.path.exists(PROTO_PATH):
        urllib.request.urlretrieve(PROTO_URL, PROTO_PATH)
    if not os.path.exists(MODEL_PATH):
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)

def run_ssd_detection(net, img):
    """Runs a single pass of MobileNet SSD with a flexible 25% confidence threshold."""
    h, w = img.shape[:2]
    blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)), 0.007843, (300, 300), 127.5)
    net.setInput(blob)
    detections = net.forward()

    for i in range(detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        class_id = int(detections[0, 0, i, 1])

        # Lowered threshold to 0.25 to reliably detect side-views, vans, and partial shots
        if confidence > 0.25 and class_id in VEHICLE_CLASSES:
            return True, VEHICLE_CLASSES[class_id]

    return False, None

def detect_vehicle_presence(img):
    try:
        ensure_model_exists()
        net = cv2.dnn.readNetFromCaffe(PROTO_PATH, MODEL_PATH)
        
        # Pass 1: Standard orientation
        found, label = run_ssd_detection(net, img)
        if found:
            return True, f"Vehicle confirmed: {label}"

        # Pass 2: Check 90° clockwise rotation (handles vertical phone captures)
        img_90 = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        found, label = run_ssd_detection(net, img_90)
        if found:
            return True, f"Vehicle confirmed: {label}"

        # Pass 3: Check 270° counter-clockwise rotation
        img_270 = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        found, label = run_ssd_detection(net, img_270)
        if found:
            return True, f"Vehicle confirmed: {label}"

        return False, "No vehicle detected in frame. Point camera clearly at a car, truck, or van."

    except Exception:
        # Fallback if DNN loading fails: lighting analysis
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if np.mean(gray) < 30:
            return False, "Environment too dark. Please scan in bright lighting."
        return False, "No vehicle detected in frame."

def detect_moire_pattern(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    f = np.fft.fft2(blurred)
    fshift = np.fft.fftshift(f)
    magnitude_spectrum = 20 * np.log(np.abs(fshift) + 1e-5)
    
    h, w = gray.shape
    cy, cx = h // 2, w // 2
    
    r = 20
    y, x = np.ogrid[:h, :w]
    mask = (x - cx)**2 + (y - cy)**2 > r**2
    
    high_freq_peaks = magnitude_spectrum * mask
    max_peak = np.max(high_freq_peaks)
    mean_freq = np.mean(high_freq_peaks)
    
    peak_ratio = max_peak / (mean_freq + 1e-5)
    return peak_ratio > 16.0  # Slightly increased to prevent false screen flags on cars

def verify_3d_perspective_shift(frame1_bytes, frame2_bytes):
    nparr1 = np.frombuffer(frame1_bytes, np.uint8)
    nparr2 = np.frombuffer(frame2_bytes, np.uint8)
    
    img1 = cv2.imdecode(nparr1, cv2.IMREAD_COLOR)
    img2 = cv2.imdecode(nparr2, cv2.IMREAD_COLOR)

    if img1 is None or img2 is None:
        return {"is_3d_valid": False, "reason": "Invalid image format uploaded."}

    # STEP 1: Verify actual vehicle (with multi-rotation support)
    is_vehicle, vehicle_msg = detect_vehicle_presence(img1)
    if not is_vehicle:
        return {"is_3d_valid": False, "reason": f"REJECTED: {vehicle_msg}"}

    # STEP 2: Check screen recapture
    if detect_moire_pattern(img1) or detect_moire_pattern(img2):
        return {
            "is_3d_valid": False, 
            "reason": "REJECTED: Digital screen recapture detected (screen pixel grid pattern)."
        }

    # STEP 3: Verify 3D depth and movement
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

    orb = cv2.ORB_create(nfeatures=1000)
    kp1, des1 = orb.detectAndCompute(gray1, None)
    kp2, des2 = orb.detectAndCompute(gray2, None)

    if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
        return {"is_3d_valid": False, "reason": "REJECTED: Unable to track surface features."}

    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des1, des2)

    if len(matches) < 10:
        return {"is_3d_valid": False, "reason": "REJECTED: Feature tracking lost between frames."}

    displacements = [np.linalg.norm(np.array(kp1[m.queryIdx].pt) - np.array(kp2[m.trainIdx].pt)) for m in matches]
    median_disp = float(np.median(displacements))

    if median_disp < 2.5:
        return {
            "is_3d_valid": False, 
            "reason": "REJECTED: Static image / flat photo detected (No 3D motion captured)."
        }

    return {
        "is_3d_valid": True,
        "displacement_score": round(median_disp, 2),
        "message": f"Authentic 3D vehicle inspection confirmed ({vehicle_msg})."
    }

def blur_privacy_regions(img):
    return img
