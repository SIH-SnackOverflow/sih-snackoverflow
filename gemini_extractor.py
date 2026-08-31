"""Gemini Vision boundary: image -> cautious, evidence-backed package facts."""
from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path
from typing import Any

from google import genai


MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# Gemini structured output deliberately cannot decide compliance.  It only returns
# what is actually visible, plus normalized bounding boxes for an auditor to inspect.
EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "full_text": {"type": "string"},
        "language_codes": {"type": "array", "items": {"type": "string"}},
        "manufacturer": {"type": ["object", "null"], "properties": {"name": {"type": "string"}, "address": {"type": "string"}}},
        "packer": {"type": ["object", "null"], "properties": {"name": {"type": "string"}, "address": {"type": "string"}}},
        "importer": {"type": ["object", "null"], "properties": {"name": {"type": "string"}, "address": {"type": "string"}}},
        "country_of_origin": {"type": ["string", "null"]},
        "generic_name": {"type": ["string", "null"]},
        "net_quantity": {"type": ["string", "null"]},
        "manufacture_month_year": {"type": ["string", "null"]},
        "best_before_or_use_by": {"type": ["string", "null"]},
        "mrp_declaration": {"type": ["string", "null"]},
        "consumer_care": {"type": ["object", "null"], "properties": {"name": {"type": "string"}, "address": {"type": "string"}, "phone": {"type": "string"}, "email": {"type": "string"}}},
        "may_become_unfit_for_consumption": {"type": ["boolean", "null"]},
        "manufacture_date_exempt": {"type": ["boolean", "null"], "description": "True only when the label clearly identifies a Bidi, incense-stick, or exempt LPG-cylinder case."},
        "is_imported": {"type": ["boolean", "null"]},
        "not_for_retail_sale": {"type": ["boolean", "null"]},
        "industrial_or_institutional_only": {"type": ["boolean", "null"]},
        "fast_food_packed_by_restaurant_or_hotel": {"type": ["boolean", "null"]},
        "drug_formulation_under_dpc": {"type": ["boolean", "null"]},
        "medical_device_declared_as_drug": {"type": ["boolean", "null"]},
        "mrp_sticker_covers_printed_mrp": {"type": ["boolean", "null"]},
        "evidence": {
            "type": "array",
            "items": {"type": "object", "properties": {
                "field": {"type": "string"}, "text": {"type": "string"},
                "box_2d": {"type": "array", "items": {"type": "integer"}},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]}
            }, "required": ["field", "text", "box_2d", "confidence"]}
        }
    },
    "required": ["full_text", "language_codes", "evidence"]
}

PROMPT = """You are a cautious package-label transcription system for an Indian
Legal Metrology review. Read only text and facts visibly supported by this image.
Do not infer or invent missing declarations. Use null when unreadable or uncertain.
Return every visible required declaration and an evidence row for it. `box_2d` must
be [ymin, xmin, ymax, xmax], normalized 0..1000. `full_text` must be a faithful
transcription. Detect English as `en` and Hindi written in Devanagari as `hi-Deva`.
Do not make legal conclusions and do not claim a physical font size or contrast pass.
For flags about product scope/stickers, set null unless visually clear. Do not set
`manufacture_date_exempt` based on a guess."""


def extract_label(image_path: str | Path) -> dict[str, Any]:
    """Call Gemini without storing the API key or modifying the supplied image."""
    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("Set GEMINI_API_KEY in your environment; do not put it in source code.")
    mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    client = genai.Client(api_key=key)
    response = client.interactions.create(
        model=MODEL,
        input=[
            {"type": "text", "text": PROMPT},
            {"type": "image", "data": encoded, "mime_type": mime_type},
        ],
        response_format={"type": "text", "mime_type": "application/json", "schema": EXTRACTION_SCHEMA},
    )
    import json
    return json.loads(response.output_text)
