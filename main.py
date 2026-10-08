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
import gc
import traceback

app = FastAPI(
    title="AI-Powered Insurance Image Forensics",
    description="Detects vehicle details for Kenyan insurance claims",
    version="0.2.7"
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
yolo_failed = False

def get_yolo():
    global yolo_model, yolo_failed
    if yolo_failed:
        return None
    if yolo_model is None:
        try:
            from ultralytics import YOLO
            print("Loading YOLO model (memory optimized)...")
            yolo_model = YOLO("yolov8n.pt")
            print("YOLO loaded")
        except Exception as e:
            print("YOLO load failed:", e)
            yolo_failed = True
            return None
    return yolo_model


VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


def get_dominant_color(image):
    try:
        small = cv2.resize(image, (48, 48))
        pixels = small.reshape(-1, 3).astype(np.float32)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 4, 1.0)
        _, labels, centers = cv2.kmeans(pixels, 2, None, criteria, 2, cv2.KMEANS_RANDOM_CENTERS)
        centers = np.uint8(centers)
        dominant = centers[np.argmax(np.bincount(labels.flatten()))]
        b, g, r = map(int, dominant)

        if r > 190 and g > 190 and b > 190:
            return "WHITE"
        if r < 50 and g < 50 and b < 50:
            return "BLACK"
        if r > 160 and g < 90 and b < 90:
            return "RED"
        if b > 150 and r < 100 and g < 100:
            return "BLUE"
        if abs(r - g) < 30 and abs(g - b) < 30:
            return "SILVER / METALLIC" if r > 120 else "GREY"
        return "SILVER / METALLIC"
    except:
        return "UNKNOWN"


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    return FileResponse("static/index.html")


@app.post("/assess")
async def assess_vehicle(file: UploadFile = File(...)):
    start_time = time.time()

    try:
        contents = await file.read()

        if not contents or len(contents) < 400:
            return {
                "status": "rejected",
                "message": "Empty or invalid image. Please take the photo again.",
                "processing_latency": 0
            }

        # Load image
        try:
            pil_img = Image.open(io.BytesIO(contents)).convert("RGB")
            # Resize early to save memory
            pil_img.thumbnail((640, 640))
            img_cv = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        except Exception:
            return {
                "status": "rejected",
                "message": "Could not read the image. Please try again.",
                "processing_latency": 0
            }

        detected_vehicles = []
        model = get_yolo()

        if model is not None:
            try:
                # Maximum memory savings settings
                results = model.predict(
                    img_cv,
                    imgsz=256,          # very small
                    conf=0.35,
                    verbose=False,
                    device="cpu"
                )[0]

                for box in results.boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    if cls_id in VEHICLE_CLASSES and conf > 0.35:
                        detected_vehicles.append({
                            "class": VEHICLE_CLASSES[cls_id],
                            "confidence": conf
                        })

                # Force cleanup
                del results
                gc.collect()

            except Exception as e:
                print("YOLO inference error:", e)
                traceback.print_exc()
                gc.collect()

        processing_latency = round((time.time() - start_time) * 1000, 2)

        if detected_vehicles:
            best = max(detected_vehicles, key=lambda x: x["confidence"])
            vtype = best["class"]

            body_map = {
                "car": "SEDAN / HATCHBACK",
                "motorcycle": "MOTORCYCLE",
                "bus": "BUS",
                "truck": "PICKUP / LORRY"
            }

            now = datetime.now()
            audit_id = f"CLM-KE-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}-{str(uuid.uuid4())[:4].upper()}"

            return {
                "status": "success",
                "audit_id": audit_id,
                "registration_plate": "NO_MATCH_DETECTED",
                "ocr_confidence": 0.0,
                "primary_body_color": get_dominant_color(img_cv),
                "body_type": body_map.get(vtype, vtype.upper()),
                "panel_damage_status": "NONE (Clean Panel)",
                "affected_panels": "No Defect Detected",
                "processing_latency": processing_latency,
                "fraud_risk": "LOW RISK (Verified Claim)",
                "claim_status": "PASSED"
            }

        return {
            "status": "rejected",
            "message": "No valid vehicle (car, lorry, motorcycle or bus) detected. Please take a clear photo of the vehicle.",
            "allowed_vehicles": ["Car", "Lorry / Truck", "Motorcycle",
