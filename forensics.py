import cv2
import numpy as np

def analyze_image(image_bytes):
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"error": "Invalid image"}
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, buffer = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        resaved = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        diff = cv2.absdiff(img, resaved)
        ela_score = float(np.mean(diff))
        edges = cv2.Canny(gray, 100, 200)
        edge_density = float(np.mean(edges)/255)
        risk = "Low"
        if ela_score > 8: risk = "High - Possible Tampering"
        elif ela_score > 4: risk = "Medium - Check Manually"
        return {
            "ela_score": round(ela_score,2),
            "edge_density": round(edge_density,4),
            "risk_level": risk,
            "image_size": f"{img.shape[1]}x{img.shape[0]}"
        }
    except Exception as e:
        return {"error": str(e)}
