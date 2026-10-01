import os
import base64
from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from forensics import verify_3d_perspective_shift, blur_privacy_regions

app = FastAPI(title="Vehicle Fraud Prevention Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VALID_API_KEYS = {"lease_client_demo_key_9981", "fleet_manager_prod_4421"}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(BASE_DIR, "templates", "index.html")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    # Direct safe reading of index.html to prevent Jinja2 template errors
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h2>App Online - templates/index.html file not found in directory.</h2>", status_code=200)

@app.post("/api/v1/verify-stream")
async def verify_stream(
    frame1: UploadFile = File(...),
    frame2: UploadFile = File(...),
    is_virtual_camera: bool = Form(False),
    x_api_key: str = Header(None)
):
    if x_api_key and x_api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Unauthorized X-API-KEY header.")

    if is_virtual_camera:
        return JSONResponse(status_code=400, content={
            "authenticity_verdict": "REJECTED",
            "risk_score": 100,
            "reason": "Virtual camera / software injection detected."
        })

    frame1_bytes = await frame1.read()
    frame2_bytes = await frame2.read()

    liveness_result = verify_3d_perspective_shift(frame1_bytes, frame2_bytes)
    processed_bytes, redaction_info = blur_privacy_regions(frame1_bytes)
    base64_processed = base64.b64encode(processed_bytes).decode('utf-8')

    if not liveness_result["is_3d_valid"]:
        return {
            "authenticity_verdict": "FLAGGED",
            "risk_score": 85,
            "security_checks": {"2d_screen_spoof_detected": True},
            "reason": liveness_result["reason"],
            "processed_image_base64": f"data:image/jpeg;base64,{base64_processed}"
        }

    return {
        "authenticity_verdict": "PASSED",
        "risk_score": 5,
        "security_checks": {"2d_screen_spoof_detected": False},
        "liveness_metrics": liveness_result,
        "processed_image_base64": f"data:image/jpeg;base64,{base64_processed}"
    }
