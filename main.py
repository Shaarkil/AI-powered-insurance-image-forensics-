import sys
import os
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

# Force Python path to resolve forensics module cleanly on Render
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from forensics import verify_3d_perspective_shift, blur_privacy_regions

app = FastAPI()


@app.get("/")
def root():
    return {"status": "Live Vehicle Inspection API Running"}


@app.post("/verify")
async def verify_inspection(
    frame1: UploadFile = File(...),
    frame2: UploadFile = File(...)
):
    try:
        frame1_bytes = await frame1.read()
        frame2_bytes = await frame2.read()

        result = verify_3d_perspective_shift(frame1_bytes, frame2_bytes)

        if not result.get("is_3d_valid"):
            return JSONResponse(
                status_code=400,
                content={"status": "REJECTED", "message": result.get("reason")}
            )

        return JSONResponse(
            status_code=200,
            content={"status": "PASSED", "details": result}
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "ERROR", "message": f"Server error processing verification: {str(e)}"}
        )
