import cv2
import numpy as np

def detect_ai_generated(image_bytes):
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        variance = float(laplacian.var())
        is_ai = False
        confidence = 20
        if variance < 50:
            is_ai = True
            confidence = 75
        elif variance < 120:
            confidence = 45
        return {
            "is_ai_generated": is_ai,
            "confidence": confidence,
            "noise_variance": round(variance,2),
            "note": "Heuristic model - low variance may indicate AI"
        }
    except Exception as e:
        return {"error": str(e), "is_ai_generated": False}
