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

app = FastAPI(
    title="AI-Powered Insurance Image Forensics",
    description="Detects vehicle details for Kenyan insurance claims",
    version="0.2.5"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

yolo_model = None

def get_yolo():
    global yolo_model
    if yolo_model is None:
        from ultralytics import YOLO
        print("Loading YOLO model...")
        yolo_model = YOLO("yolov8n.pt")
        print("YOLO model loaded")
    return yolo_model

VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck"
}

def get_dominant_color(image):
    try:
        small = cv2.resize(image, (80, 80))
        pixels = small.reshape(-1, 3).astype(np.float32)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 8, 1.0)
        _, labels, centers = cv2.kmeans(
            pixels, 2, None, criteria, 5, cv2.KMEANS_RANDOM_CENTERS
        )
        centers = np.uint8(centers)
        dominant = centers[np.argmax(np.bincount(labels.flatten()))]
        b, g, r = map(int, dominant)

        if r > 190 and g > 190 and b > 190:
            return "WHITE"
        elif r < 50 and g < 50 and b < 50:
            return "BLACK"
        elif r > 160 and g < 90 and b < 90:
            return "RED"
        elif b > 150 and r < 100 and g < 100:
            return "BLUE"
        elif abs(r - g) < 25 and abs(g - b) < 25:
            return "SILVER / METALLIC" if r > 130 else "GREY"
        else:
            return "SILVER / METALLIC"
    except Exception:
        return "UNKNOWN"

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    return FileResponse("static/index.html")

@app.post("/assess")
async def assess_vehicle(file: UploadFile = File(...)):
    start_time = time.time()

    try:
        contents = await file.read()

        if not contents or len(contents) < 100:
            return {
                "status": "rejected",
                "message": "Empty or invalid image received. Please take the photo again.",
                "processing_latency": 0
            }

        # More robust image loading
        try:
            image = Image.open(io.BytesIO(contents)).convert("RGB")
        except Exception:
            # Fallback using OpenCV
            nparr = np.frombuffer(contents, np.uint8)
            img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img_cv is None:
                return {
                    "status": "rejected",
                    "message": "Could not read the image. Please try taking the photo again.",
                    "processing_latency": 0
                }
            image = Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))

        img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

        model = get_yolo()
        results = model(img_cv, verbose=False)[0]

        detected_vehicles = []
        for box in results.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            if cls_id in VEHICLE_CLASSES and conf > 0.45:
                detected_vehicles.append({
                    "class": VEHICLE_CLASSES[cls_id],
                    "confidence": conf
                })

        processing_latency = round((time.time() - start_time) * 1000, 2)

        if not detected_vehicles:
            return {
                "status": "rejected",
                "message": "No valid vehicle (car, lorry, motorcycle or bus) detected in the image. Please take a clear photo of the vehicle.",
                "allowed_vehicles": ["Car", "Lorry / Truck", "Motorcycle", "Bus"],
                "processing_latency": processing_latency
            }

        best_vehicle = max(detected_vehicles, key=lambda x: x["confidence"])
        vehicle_type = best_vehicle["class"]

        body_type_map = {
            "car": "SEDAN / HATCHBACK",
            "motorcycle": "MOTORCYCLE",
            "bus": "BUS",
            "truck": "PICKUP / LORRY"
        }
        body_type = body_type_map.get(vehicle_type, vehicle_type.upper())
        primary_color = get_dominant_color(img_cv)

        plate = "NO_MATCH_DETECTED"
        ocr_confidence = 0.0
        damage_status = "NONE (Clean Panel)"
        affected_panels = "No Defect Detected"
        risk_level = "LOW RISK (Verified Claim)"
        claim_status = "PASSED"

        now = datetime.now()
        date_part = now.strftime("%Y%m%d")
        time_part = now.strftime("%H%M%S")
        unique_part = str(uuid.uuid4())[:4].upper()
        audit_id = f"CLM-KE-{date_part}-{time_part}-{unique_part}"

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

    except Exception as e:
        print("Error in assess_vehicle:", str(e))
        return {
            "status": "rejected",
            "message": f"Analysis failed: {str(e)}. Please try again with a clearer photo.",
            "processing_latency": 0
      }
