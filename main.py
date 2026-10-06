from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uuid
import hashlib
import tempfile
import os
from ultralytics import YOLO

app = FastAPI(
    title="AI-Powered Insurance Image Forensics",
    description="Detects vehicle details, damage, plates, color and helps flag potential fraud for Kenyan insurance claims",
    version="0.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load YOLO model once (nano version for free tier)
model = YOLO("yolov8n.pt")

# COCO class mapping we care about
ALLOWED_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck"          # we treat truck as lorry
}

def generate_unique_id(image_bytes: bytes) -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    img_hash = hashlib.sha256(image_bytes).hexdigest()[:8]
    return f"{timestamp}_{img_hash}_{str(uuid.uuid4())[:6]}"


@app.get("/")
def health_check():
    return {
        "status": "online",
        "service": "AI-Powered Insurance Image Forensics",
        "version": "0.2.0",
        "message": "Ready to receive images"
    }


@app.post("/assess")
async def assess_vehicle(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed")

    image_bytes = await file.read()
    unique_id = generate_unique_id(image_bytes)

    # Save temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name

    try:
        # Run YOLO detection
        results = model(tmp_path, conf=0.35, verbose=False)

        detected_vehicles = []

        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])

                if cls_id in ALLOWED_CLASSES:
                    detected_vehicles.append({
                        "type": ALLOWED_CLASSES[cls_id],
                        "confidence": round(conf, 3)
                    })

        if not detected_vehicles:
            return {
                "id": unique_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "status": "rejected",
                "reason": "No allowed vehicle detected (only car, motorcycle, bus, lorry are accepted)",
                "filename": file.filename
            }

        # Take the highest confidence vehicle
        best = max(detected_vehicles, key=lambda x: x["confidence"])

        result = {
            "id": unique_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": "accepted",
            "vehicle_type": best["type"],
            "confidence": best["confidence"],
            "all_detections": detected_vehicles,
            "filename": file.filename,
            "message": "Vehicle type detected successfully. More features coming next."
        }

        return result

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
