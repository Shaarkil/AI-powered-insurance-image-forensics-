from fastapi import FastAPI, File, UploadFile
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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    return FileResponse("static/index.html")


@app.post("/assess")
async def assess_vehicle(file: UploadFile = File(...)):
    """
    Analyze uploaded vehicle image and return forensic assessment.
    """
    start_time = time.time()

    # Read the file (required even if we don't process it deeply in this mock)
    contents = await file.read()

    # Simulate processing time
    time.sleep(random.uniform(0.6, 1.8))

    processing_latency = round((time.time() - start_time) * 1000, 2)  # in ms

    # Generate realistic mock results (replace this with your real model later)
    plates = ["KBX356A", "KCA123B", "KDG789C", "KBL452D", "NO_MATCH_DETECTED"]
    colors = ["SILVER / METALLIC", "WHITE", "BLACK", "BLUE", "RED", "GREY"]
    body_types = ["SEDAN / HATCHBACK", "STATION WAGON / MPV", "SUV", "PICKUP", "HATCHBACK"]
    damage_statuses = ["NONE (Clean Panel)", "MINOR DENT", "MODERATE DAMAGE", "SEVERE DAMAGE"]
    affected = ["No Defect Detected", "Rear Bumper", "Left Rear Door", "Front Bumper", "Right Fender"]

    plate = random.choice(plates)
    ocr_confidence = round(random.uniform(85.0, 99.5), 1) if plate != "NO_MATCH_DETECTED" else 0.0

    damage_status = random.choice(damage_statuses)
    affected_panels = random.choice(affected)

    # Simple risk logic
    if plate == "NO_MATCH_DETECTED" or "SEVERE" in damage_status:
        risk_level = "MEDIUM RISK (Manual Check Required)"
        status = "PASSED"
    elif "MODERATE" in damage_status:
        risk_level = "LOW RISK (Verified Claim)"
        status = "PASSED"
    else:
        risk_level = "LOW RISK (Verified Claim)"
        status = "PASSED"

    # Generate Audit ID similar to your screenshots
    now = datetime.now()
    audit_id = f"CLM-KE-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}-{str(uuid.uuid4())[:4].upper()}"

    result = {
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

    return result
