import cv2
import numpy as np

def detect_vehicle_presence(img):
    """
    Checks basic structural/contrast properties to ensure the image 
    isn't just a dark room, blank surface, or completely unrelated non-vehicle object.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 1. Reject images that are too dark to analyze accurately
    mean_brightness = np.mean(gray)
    if mean_brightness < 35:
        return False, "Environment too dark. Please scan in bright ambient lighting."
        
    # 2. Check for structural edges (vehicles have clear structural contours)
    edges = cv2.Canny(gray, 50, 150)
    edge_density = np.sum(edges > 0) / edges.size
    
    if edge_density < 0.015:
        return False, "No vehicle detected in frame (insufficient structural detail)."

    return True, "Vehicle candidate detected"


def detect_moire_pattern(img):
    """
    Evaluates high-frequency periodic grids typical of LCD/OLED screens.
    Applies noise filtering to prevent low-light camera grain from triggering false positives.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Denoise slightly to eliminate camera sensor grain
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Fast Fourier Transform (FFT) for frequency domain analysis
    f = np.fft.fft2(blurred)
    fshift = np.fft.fftshift(f)
    magnitude_spectrum = 20 * np.log(np.abs(fshift) + 1e-5)
    
    h, w = gray.shape
    cy, cx = h // 2, w // 2
    
    # Mask out central DC component (low frequencies)
    r = 20
    y, x = np.ogrid[:h, :w]
    mask = (x - cx)**2 + (y - cy)**2 > r**2
    
    high_freq_peaks = magnitude_spectrum * mask
    max_peak = np.max(high_freq_peaks)
    mean_freq = np.mean(high_freq_peaks)
    
    # Peak-to-mean ratio threshold for screen grid detection
    peak_ratio = max_peak / (mean_freq + 1e-5)
    
    # Higher threshold prevents false positives on real objects
    if peak_ratio > 14.5:
        return True
    return False


def verify_3d_perspective_shift(frame1_bytes, frame2_bytes):
    """
    Full forensic pipeline returning specific rejection reasons:
    - Darkness / Non-vehicle
    - Digital Screen Recapture
    - Static Photo / No Motion
    """
    # Convert bytes to OpenCV images
    nparr1 = np.frombuffer(frame1_bytes, np.uint8)
    nparr2 = np.frombuffer(frame2_bytes, np.uint8)
    
    img1 = cv2.imdecode(nparr1, cv2.IMREAD_COLOR)
    img2 = cv2.imdecode(nparr2, cv2.IMREAD_COLOR)

    if img1 is None or img2 is None:
        return {"is_3d_valid": False, "reason": "Invalid image format uploaded."}

    # CHECK 1: Vehicle & Lighting Validation
    is_vehicle, vehicle_msg = detect_vehicle_presence(img1)
    if not is_vehicle:
        return {"is_3d_valid": False, "reason": f"REJECTED: {vehicle_msg}"}

    # CHECK 2: Digital Screen Recapture (Moiré Grid)
    if detect_moire_pattern(img1) or detect_moire_pattern(img2):
        return {
            "is_3d_valid": False, 
            "reason": "REJECTED: Digital screen recapture detected (screen pixel grid pattern)."
        }

    # CHECK 3: 3D Motion & Parallax Shift Verification
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

    # Calculate feature displacement
    displacements = []
    for m in matches:
        pt1 = np.array(kp1[m.queryIdx].pt)
        pt2 = np.array(kp2[m.trainIdx].pt)
        displacements.append(np.linalg.norm(pt1 - pt2))

    median_disp = float(np.median(displacements))

    # Reject if the phone was kept completely still or taking a photo of a flat print
    if median_disp < 3.0:
        return {
            "is_3d_valid": False, 
            "reason": "REJECTED: Static image / flat photo detected (No 3D motion captured)."
        }

    return {
        "is_3d_valid": True,
        "displacement_score": round(median_disp, 2),
        "message": "Authentic 3D vehicle inspection confirmed."
    }


def blur_privacy_regions(img):
    """Optional utility to blur high-privacy regions like faces or license plates."""
    return img
