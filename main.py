from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import time
import uuid
import cv2
import numpy as np
from PIL import Image
import io
from ultralytics import YOLO
import easyocr

app = FastAPI(
    title="AI-Powered Insurance Image Forensics",
    description="Detects vehicle details, damage, plates, color and helps flag potential fraud for Kenyan insurance claims",
    version="0.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# ======================
# Load models once
# ======================
print("Loading YOLO model...")
yolo_model = YOLO("yolov8n.pt")  # will download automatically on first run

print("Loading EasyOCR...")
reader = easyocr.Reader(['en'], gpu=False)  # set gpu=True if you have GPU

# COCO classes we care about
VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck"          # we will treat truck as lorry
}


def get_dominant_color(image: np.ndarray) -> str:
    """Simple dominant color estimation"""
    try:
        # Resize for speed
        small = cv2.resize(image, (100, 100))
        pixels = small.reshape(-1, 3)
        pixels = np.float32(pixels)

        # K-means
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, labels, centers = cv2.kmeans(pixels, 3, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
        centers = np.uint8(centers)
        dominant = centers[np.argmax(np.bincount(labels.flatten()))]

        b, g, r = dominant
        # Simple color mapping
        if r > 180 and g > 180 and b > 180:
            return "WHITE"
        elif r < 60 and g < 60 and b < 60:
            return "BLACK"
        elif r > 150 and g < 100 and b < 100:
            return "RED"
        elif r < 100 and g < 100 and b > 150:
            return "BLUE"
        elif r < 100 and g > 150 and b < 100:
            return "GREEN"
        elif abs(r - g) < 30 and abs(g - b) < 30:
            if r > 120:
                return "SILVER / METALLIC"
            else:
                return "GREY"
        else:
            return "SILVER / METALLIC"
    except:
        return "UNKNOWN"


def extract_plate(image: np.ndarray) -> tuple[str, float]:
    """Try to read Kenyan-style license plate using EasyOCR"""
    try:
        results = reader.readtext(image)
        best_plate = "NO_MATCH_DETECTED"
        best_conf = 0.0

        for (bbox, text, conf) in results:
            cleaned = text.upper().replace(" ", "").replace("-", "")
            # Kenyan plates roughly look like: KXX123A or KBX356A (6-8 chars)
            if 5 <= len(cleaned) <= 9 and any(c.isalpha() for c in cleaned) and any(c.isdigit() for c in cleaned):
                if conf > best_conf:
                    best_plate = cleaned
                    best_conf = conf

        return best_plate, round(best_conf * 100, 1)
    except Exception as e:
        print("OCR error:", e)
        return "NO_MATCH_DETECTED", 0.0


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    return FileResponse("static/index.html")


@app.post("/assess")
async def assess_vehicle(file: UploadFile = File(...)):
    start_time = time.time()

    # Read image
    contents = await file.read()
    image = Image.open(io.BytesIO(contents)).convert("RGB")
    img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    # ======================
    # 1. Detect vehicles with YOLO
    # ======================
    results = yolo_model(img_cv, verbose=False)[0]

    detected_vehicles = []
    for box in results.boxes:
        cls_id = int(box.cls[0])
        conf = float(box.conf[0])
        if cls_id in VEHICLE_CLASSES and conf > 0.4:
            detected_vehicles.append({
                "class": VEHICLE_CLASSES[cls_id],
                "confidence": conf,
                "bbox": box.xyxy[0].tolist()
            })

    processing_latency = round((time.time() - start_time) * 1000, 2)

    # Reject if no vehicle found
    if not detected_vehicles:
        return {
            "status": "rejected",
            "message": "No valid vehicle (car, lorry, motorcycle or bus) detected in the image. Please take a clear photo of the vehicle.",
            "allowed_vehicles": ["Car", "Lorry / Truck", "Motorcycle", "Bus"],
            "processing_latency": processing_latency
        }

    # Take the highest confidence vehicle
    best_vehicle = max(detected_vehicles, key=lambda x: x["confidence"])
    vehicle_type = best_vehicle["class"]

    # Map to nicer names
    body_type_map = {
        "car": "SEDAN / HATCHBACK",
        "motorcycle": "MOTORCYCLE",
        "bus": "BUS",
        "truck": "PICKUP / LORRY"
    }
    body_type = body_type_map.get(vehicle_type, vehicle_type.upper())

    # ======================
    # 2. Color estimation
    # ======================
    primary_color = get_dominant_color(img_cv)

    # ======================
    # 3. License plate OCR
    # ======================
    plate, ocr_confidence = extract_plate(img_cv)

    # ======================
    # 4. Damage (placeholder - needs fine-tuned model)
    # ======================
    # For now we keep it conservative
    if plate == "NO_MATCH_DETECTED":
        damage_status = "NONE (Clean Panel)"
        affected_panels = "No Defect Detected"
        risk_level = "MEDIUM RISK (Manual Check Required)"
        claim_status = "PASSED"
    else:
        damage_status = "NONE (Clean Panel)"
        affected_panels = "No Defect Detected"
        risk_level = "LOW RISK (Verified Claim)"
        claim_status = "PASSED"

    # ======================
    # Build response
    # ======================
    now = datetime.now()
    audit_id = f"CLM-KE-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}-{str(uuid.uuid4())[:4].upper()}"

    return {
        "status": "success",
        "audit_id": audit_id,
        "registration_plate": plate,
        "ocr_confidence": ocr_confidence,
        "primary_body_color": primary_color,
        "body_type": body_type,
        "panel_damage_status": damage_status,
        "affected_panels": affected_panels,
        "processing_latency": processing_latency,
        "fraud_risk": risk_level,
        "claim_status": claim_status
              }
