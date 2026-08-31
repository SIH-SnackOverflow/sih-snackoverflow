"""FastAPI service for the package-label compliance dashboard."""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from gemini_extractor import extract_label
from rule_engine import RuleEngine

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

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


@app.post("/api/reviews")
async def create_review(image: UploadFile = File(...)) -> dict[str, Any]:
    """Analyze one label image and return the extraction plus rule-engine report."""
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

        extraction = extract_label(temporary_path)
        report = RuleEngine().evaluate(extraction)
        report["extraction"] = extraction
        return report
    except HTTPException:
        raise
    except RuntimeError as error:
        # In particular, return a readable setup error if GEMINI_API_KEY is absent.
        raise HTTPException(503, str(error)) from error
    except Exception as error:
        raise HTTPException(500, "The label could not be analyzed. Please try a clearer image.") from error
    finally:
        if temporary_path:
            temporary_path.unlink(missing_ok=True)
        await image.close()
