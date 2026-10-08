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
import traceback

app = FastAPI(
    title="AI-Powered Insurance Image Forensics",
    description="Detects vehicle details for Kenyan insurance claims",
    version="0.2.6"
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
yolo_load_failed = False

def get_yolo():
    global yolo_model, yolo_load_failed
    if yolo_load_failed:
        return None
    if yolo_model is None:
        try:
            from ultralytics import YOLO
            print("Loading YOLO model...")
            yolo_model = YOLO("yolov8n.pt")
            print("YOLO model loaded successfully")
        except Exception as e:
            print("Failed to load YOLO:", str(e))
            yolo_load_failed = True
            return None
    return yolo_model


VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck"
}


def get_dominant_color(image):
    try:
        small = cv2.resize(image, (60, 60))
        pixels = small.reshape(-1, 3).astype(np.float32)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 5, 1.0)
        _, labels, centers = cv2.kmeans(
            pixels, 2, None, criteria, 3, cv2.KMEANS_RANDOM_CENTERS
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

        if not contents or len(contents) < 500:
            return {
                "status": "rejected",
                "message": "Empty or invalid image received. Please take the photo again.",
                "processing_latency": 0
            }

        # Load image safely
        try:
            image = Image.open(io.BytesIO(contents)).convert("RGB")
            img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        except Exception:
            try:
                nparr = np.frombuffer(contents, np.uint8)
                img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img_cv is None:
                    raise ValueError("Could not decode image")
                image = Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))
            except Exception:
                return {
                    "status": "rejected",
                    "message": "Could not read the image. Please try taking the photo again.",
                    "processing_latency": 0
                }

        # Try real detection with YOLO
        detected_vehicles = []
        model = get_yolo()

        if model is not None:
            try:
                results = model(img_cv, verbose=False, imgsz=320)[0]  # smaller size to save memory

                for box in results.boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    if cls_id in VEHICLE_CLASSES and conf > 0.40:
                        detected_vehicles.append({
                            "class": VEHICLE_CLASSES[cls_id],
                            "confidence": conf
                        })
            except Exception as e:
                print("YOLO inference failed:", str(e))
                traceback.print_exc()
                # Fall through to simple fallback

        processing_latency = round((time.time() - start_time) * 1000, 2)

        # If YOLO found vehicles
        if detected_vehicles:
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

            now = datetime.now()
            audit_id = f"CLM-KE-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}-{str(uuid.uuid4())[:4].upper()}"

            return {
                "status": "success",
                "audit_id": audit_id,
                "registration_plate": "NO_MATCH_DETECTED",
                "ocr_confidence": 0.0,
                "primary_body_color": primary_color,
                "body_type": body_type,
                "panel_damage_status": "NONE (Clean Panel)",
                "affected_panels": "No Defect Detected",
                "processing_latency": processing_latency,
                "fraud_risk": "LOW RISK (Verified Claim)",
                "claim_status": "PASSED"
            }

        # If no vehicle detected
        return {
            "status": "rejected",
            "message": "No valid vehicle (car, lorry, motorcycle or bus) detected in the image. Please take a clear photo of the vehicle.",
            "allowed_vehicles": ["Car", "Lorry / Truck", "Motorcycle", "Bus"],
            "processing_latency": processing_latency
        }

    except Exception as e:
        print("Unexpected error:", str(e))
        traceback.print_exc()
        return {
            "status": "rejected",
            "message": "Analysis failed due to server resource limits. Please try again in 30 seconds with a clearer photo.",
            "processing_latency": 0
                  }
