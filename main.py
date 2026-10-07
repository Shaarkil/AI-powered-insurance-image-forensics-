from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import time
import random
import uuid

app = FastAPI(
    title="AI-Powered Insurance Image Forensics",
    description="Detects vehicle details, damage, plates, color and helps flag potential fraud for Kenyan insurance claims",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    return FileResponse("static/index.html")


@app.post("/assess")
async def assess_vehicle(file: UploadFile = File(...)):
    start_time = time.time()

    # Read the uploaded file
    contents = await file.read()
    file_size = len(contents)

    # Simulate processing time
    time.sleep(random.uniform(0.8, 1.6))

    processing_latency = round((time.time() - start_time) * 1000, 2)

    # ===============================
    # MOCK VEHICLE DETECTION
    # In real system this would be a proper model
    # ===============================
    # For demo: randomly reject \~25% of images as "not a vehicle"
    is_vehicle = random.random() > 0.25

    if not is_vehicle:
        return {
            "status": "rejected",
            "message": "This image does not appear to contain a valid vehicle (car, lorry, motorcycle or bus). Please take a clear photo of the vehicle.",
            "allowed_vehicles": ["Car", "Lorry / Truck", "Motorcycle", "Bus"],
            "processing_latency": processing_latency
        }

    # ===============================
    # NORMAL SUCCESSFUL ANALYSIS
    # ===============================
    plates = ["KBX356A", "KCA123B", "KDG789C", "KBL452D", "KCE901F", "NO_MATCH_DETECTED"]
    colors = ["SILVER / METALLIC", "WHITE", "BLACK", "BLUE", "RED", "GREY", "GREEN"]
    body_types = ["SEDAN / HATCHBACK", "STATION WAGON / MPV", "SUV", "PICKUP / LORRY", "HATCHBACK", "BUS", "MOTORCYCLE"]
    damage_statuses = ["NONE (Clean Panel)", "MINOR DENT", "MODERATE DAMAGE", "SEVERE DAMAGE"]
    affected = ["No Defect Detected", "Rear Bumper", "Left Rear Door", "Front Bumper", "Right Fender", "Side Panel"]

    plate = random.choice(plates)
    ocr_confidence = round(random.uniform(87.0, 99.4), 1) if plate != "NO_MATCH_DETECTED" else 0.0

    damage_status = random.choice(damage_statuses)
    affected_panels = random.choice(affected)

    if plate == "NO_MATCH_DETECTED" or "SEVERE" in damage_status:
        risk_level = "MEDIUM RISK (Manual Check Required)"
        status = "PASSED"
    else:
        risk_level = "LOW RISK (Verified Claim)"
        status = "PASSED"

    now = datetime.now()
    audit_id = f"CLM-KE-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}-{str(uuid.uuid4())[:4].upper()}"

    return {
        "status": "success",
        "audit_id": audit_id,
        "registration_plate": plate,
        "ocr_confidence": ocr_confidence,
        "primary_body_color": random.choice(colors),
        "body_type": random.choice(body_types),
        "panel_damage_status": damage_status,
        "affected_panels": affected_panels,
        "processing_latency": processing_latency,
        "fraud_risk": risk_level,
        "claim_status": status
    }
