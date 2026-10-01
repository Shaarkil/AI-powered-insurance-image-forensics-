import cv2
import numpy as np

def verify_3d_perspective_shift(frame1_bytes: bytes, frame2_bytes: bytes) -> dict:
    """
    Compares 2 sequential frames from the WebRTC stream using ORB feature matching.
    Verifies physical 3D movement to detect 2D flat screen playback attacks.
    """
    nparr1 = np.frombuffer(frame1_bytes, np.uint8)
    nparr2 = np.frombuffer(frame2_bytes, np.uint8)
    img1 = cv2.imdecode(nparr1, cv2.IMREAD_GRAYSCALE)
    img2 = cv2.imdecode(nparr2, cv2.IMREAD_GRAYSCALE)

    if img1 is None or img2 is None:
        return {"is_3d_valid": False, "reason": "Failed to decode frames."}

    orb = cv2.ORB_create(nfeatures=500)
    kp1, des1 = orb.detectAndCompute(img1, None)
    kp2, des2 = orb.detectAndCompute(img2, None)

    if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
        return {"is_3d_valid": False, "reason": "Insufficient optical surface features."}

    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des1, des2)
    matches = sorted(matches, key=lambda x: x.distance)

    # Check homography / geometric translation shift
    if len(matches) < 8:
        return {"is_3d_valid": False, "reason": "Static image or flat screen spoof detected."}

    pts1 = np.float32([kp1[m.queryIdx].pt for m in matches[:20]])
    pts2 = np.float32([kp2[m.trainIdx].pt for m in matches[:20]])

    # Calculate average displacement across matched points
    displacement = np.mean(np.linalg.norm(pts1 - pts2, axis=1))

    # A real 3D camera motion shows non-zero displacement; a completely static screen/image shows 0
    if displacement < 3.0:
        return {"is_3d_valid": False, "reason": "No camera angle movement detected (potential static screen)." }

    return {"is_3d_valid": True, "displacement_score": round(float(displacement), 2)}

def blur_privacy_regions(image_bytes: bytes) -> tuple[bytes, dict]:
    """
    Detects and blurs faces and license plates for privacy compliance.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if img is None:
        return image_bytes, {"redacted": False}

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Load OpenCV Haar Cascade classifiers
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    plate_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_russian_plate_number.xml')

    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
    plates = plate_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)

    redactions_count = len(faces) + len(plates)

    for (x, y, w, h) in faces:
        ROI = img[y:y+h, x:x+w]
        blurred = cv2.GaussianBlur(ROI, (51), 30)
        img[y:y+h, x:x+w] = blurred

    for (x, y, w, h) in plates:
        ROI = img[y:y+h, x:x+w]
        blurred = cv2.GaussianBlur(ROI, (51), 30)
        img[y:y+h, x:x+w] = blurred

    _, encoded_img = cv2.imencode('.jpg', img)
    return encoded_img.tobytes(), {"redacted": redactions_count > 0, "count": redactions_count}
