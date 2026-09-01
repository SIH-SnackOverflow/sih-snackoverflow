import os
import shutil
import tempfile
import traceback
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from gemini_extractor import extract_label
from image_annotator import draw_evidence
from rule_engine import RuleEngine

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

# Create directory to store annotated images for frontend display
ANNOTATED_DIR = Path("annotated_images")
ANNOTATED_DIR.mkdir(exist_ok=True)

app = FastAPI(title="LabelLens API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174",
    ).split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

# Endpoint to serve generated annotated images
@app.get("/api/images/{filename}")
async def get_image(filename: str):
    image_path = ANNOTATED_DIR / filename
    if not image_path.is_file():
        raise HTTPException(404, "Image not found")
    return FileResponse(image_path)

@app.post("/api/reviews")
async def create_review(image: UploadFile = File(...)) -> dict[str, Any]:
    if image.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(415, "Upload a JPEG, PNG, or WebP image.")

    suffix = Path(image.filename or "label.jpg").suffix or ".jpg"
    temporary_path: Path | None = None

    try:
        payload = await image.read()
        if not payload:
            raise HTTPException(400, "The uploaded image is empty.")
        if len(payload) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Image must be 10 MB or smaller.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary_file:
            temporary_file.write(payload)
            temporary_path = Path(temporary_file.name)

        # 1. Gemini Extraction
        extraction = extract_label(temporary_path)

        # 2. Legal Metrology Rule Evaluation
        report = RuleEngine().evaluate(extraction)
        report["extraction"] = extraction

        # 3. Draw Annotations & Return URL
        annotated_filename = f"annotated_{temporary_path.stem}.png"
        annotated_output_path = ANNOTATED_DIR / annotated_filename
        draw_evidence(temporary_path, extraction, annotated_output_path)
        
        report["annotated_image_url"] = f"/api/images/{annotated_filename}"

        return report

    except HTTPException:
        raise
    except RuntimeError as error:
        traceback.print_exc()
        raise HTTPException(503, str(error)) from error
    except Exception as error:
        traceback.print_exc()
        raise HTTPException(500, f"Analysis error: {error}") from error
    finally:
        if temporary_path:
            temporary_path.unlink(missing_ok=True)
        await image.close()
# --- STARTUP BLOCK ---
# This part is crucial! It tells Python to actually start the server.
if __name__ == "__main__":
    import uvicorn
    print("Starting LabelLens API server...")
    uvicorn.run(app, host="127.0.0.1", port=8000)
