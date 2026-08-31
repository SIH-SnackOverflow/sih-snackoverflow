"""Deterministic checks over cautious Gemini extraction output; not legal advice."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable

PASS, FAIL, REVIEW, EXEMPT, SKIPPED = "PASS", "POSSIBLE_VIOLATION", "NEEDS_REVIEW", "EXEMPT", "SKIPPED"
QTY_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(mg|g|gm|kg|ml|l|litre|liter|m|cm|mm|count|pcs?|pieces?|nos?|dozen|score|gross)\b", re.I)
DATE_RE = re.compile(r"(?:0?[1-9]|1[0-2])\s*[-/]\s*\d{4}|(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s*[-, ]\s*\d{4}", re.I)
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_RE = re.compile(r"(?:\+91[- ]?)?[6-9]\d{9}|1800[- ]?\d{3,4}[- ]?\d{3,4}")


@dataclass(frozen=True)
class Finding:
    rule_id: str
    outcome: str
    message: str
    observed: Any = None


def present(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def party_complete(value: Any) -> bool:
    return isinstance(value, dict) and present(value.get("name")) and present(value.get("address"))


def parse_quantity(value: Any) -> tuple[float, str] | None:
    match = QTY_RE.match(str(value or ""))
    if not match:
        return None
    unit = match.group(2).lower()
    return float(match.group(1)), {"gm": "g", "litre": "l", "liter": "l", "pc": "count", "pcs": "count", "piece": "count", "pieces": "count", "no": "count", "nos": "count"}.get(unit, unit)


def finding(rule_id: str, ok: bool, message: str, observed: Any = None) -> Finding:
    return Finding(rule_id, PASS if ok else REVIEW, message if ok else f"Cannot verify: {message}", observed)


class RuleEngine:
    """Only emits POSSIBLE_VIOLATION when image evidence positively shows a violation.

    An omitted/unreadable declaration is NEEDS_REVIEW because vision extraction is
    fallible.  This avoids treating an OCR error as a legal finding.
    """

    def evaluate(self, data: dict[str, Any]) -> dict[str, Any]:
        exemptions = self._exemptions(data)
        if exemptions:
            return self._report(exemptions, [])
        results = list(self._mandatory(data)) + list(self._declaration_format(data))
        skipped = [
            Finding("EX-02", SKIPPED, "The supplied bulk-exemption rule has no exact eligibility conditions; it is not encoded."),
            Finding("TYP-01", SKIPPED, "Physical PDP area cannot be calculated from an image without a calibrated scale and package geometry."),
            Finding("TYP-02", SKIPPED, "Physical font height requires a reliable pixels-per-mm calibration."),
            Finding("TYP-03", SKIPPED, "Character aspect ratio needs dependable character-level boxes; Gemini evidence boxes cover declarations, not glyphs."),
            Finding("TYP-04", SKIPPED, "Color contrast needs calibrated image capture and a defined contrast metric."),
            Finding("TYP-05", SKIPPED, "Clear-space measurement needs precise numeral boxes and a stable image scale."),
            Finding("VIO-04", SKIPPED, "Whether a sticker covers an original printed MRP is not dependable from one image; require human visual review."),
            Finding("VIO-05", SKIPPED, "Schedule II commodity-to-pack-size data was not supplied as a versioned configuration."),
        ]
        q = parse_quantity(data.get("net_quantity"))
        if q and ((q[1] == "kg" and q[0] > 25) or (q[1] == "l" and q[0] > 25)):
            skipped.append(Finding("EX-01", SKIPPED, "Large-package exemption not automatically applied; check cement/fertilizer/agricultural-produce exceptions manually.", data.get("net_quantity")))
        return self._report(results, skipped)

    def _exemptions(self, d: dict[str, Any]) -> list[Finding]:
        q = parse_quantity(d.get("net_quantity"))
        # Do not auto-exempt a >25 kg/L package: cement, fertilizer, and
        # agricultural-produce exceptions cannot safely be determined from a
        # single label image without a positively verified commodity category.
        if q and ((q[1] == "kg" and q[0] > 25) or (q[1] == "l" and q[0] > 25)):
            return []
        if d.get("not_for_retail_sale") is True and d.get("industrial_or_institutional_only") is True:
            return [Finding("EX-03", EXEMPT, "Clearly marked non-retail industrial/institutional package.")]
        if d.get("fast_food_packed_by_restaurant_or_hotel") is True:
            return [Finding("EX-04", EXEMPT, "Fast food packed by a restaurant or hotel.")]
        if d.get("drug_formulation_under_dpc") is True and d.get("medical_device_declared_as_drug") is False:
            return [Finding("EX-04", EXEMPT, "DPCO formulation; medical-device status must be reviewed separately.")]
        return []

    def _mandatory(self, d: dict[str, Any]) -> Iterable[Finding]:
        yield finding("MD-01", party_complete(d.get("manufacturer")), "manufacturer name and complete postal address", d.get("manufacturer"))
        if d.get("is_imported") is True:
            yield finding("MD-02", party_complete(d.get("importer")) and present(d.get("country_of_origin")), "importer name/address and country of origin", {"importer": d.get("importer"), "country": d.get("country_of_origin")})
        yield finding("MD-03", present(d.get("generic_name")), "common or generic commodity name", d.get("generic_name"))
        q = parse_quantity(d.get("net_quantity"))
        yield finding("MD-04", q is not None and q[1] not in {"dozen", "score", "gross"}, "net quantity in a recognized standard unit", d.get("net_quantity"))
        if d.get("manufacture_date_exempt") is True:
            yield Finding("MD-05", EXEMPT, "Image clearly identifies a configured manufacture-date exemption.")
        else:
            yield finding("MD-05", bool(DATE_RE.search(str(d.get("manufacture_month_year") or ""))), "manufacture/pre-pack/import month and year", d.get("manufacture_month_year"))
        if d.get("may_become_unfit_for_consumption") is True:
            yield finding("MD-06", bool(DATE_RE.search(str(d.get("best_before_or_use_by") or ""))), "best-before/use-by date with month and year", d.get("best_before_or_use_by"))
        mrp = str(d.get("mrp_declaration") or "")
        yield finding("MD-07", bool(re.search(r"\b(?:mrp|maximum retail price)\b.*(?:rs\.?|inr|₹)\s*\d", mrp, re.I)) and bool(re.search(r"inclus(?:ive|ive)\s+of\s+(?:all\s+)?tax", mrp, re.I)), "MRP amount marked inclusive of all taxes", d.get("mrp_declaration"))
        care = d.get("consumer_care") or {}
        care_ok = party_complete(care) and bool(PHONE_RE.search(str(care.get("phone") or ""))) and bool(EMAIL_RE.match(str(care.get("email") or "")))
        yield finding("MD-08", care_ok, "consumer-care name, postal address, phone, and email", care)
        languages = set(d.get("language_codes") or [])
        yield finding("MD-09", bool(languages & {"en", "hi-Deva"}), "English or Hindi in Devanagari declaration language", sorted(languages))

    def _declaration_format(self, d: dict[str, Any]) -> Iterable[Finding]:
        text = str(d.get("full_text") or "")
        q = parse_quantity(d.get("net_quantity"))
        bad_unit = q and q[1] in {"dozen", "score", "gross"}
        yield Finding("VIO-01", FAIL if bad_unit else PASS, "Non-standard count unit detected." if bad_unit else "No prohibited count unit detected.", d.get("net_quantity"))
        if q:
            number, unit = q
            wrong = (unit == "kg" and number < 1) or (unit == "m" and number < 1) or (unit == "l" and number < 1)
            yield Finding("VIO-02", FAIL if wrong else PASS, "Sub-threshold quantity uses a larger unit." if wrong else "Unit threshold check passed.", d.get("net_quantity"))
        else:
            yield Finding("VIO-02", REVIEW, "Cannot verify unit threshold without a readable net quantity.")
        phrase = re.search(r"\b(?:minimum|not\s+less\s+than|average|about|approximately)\b", text, re.I)
        yield Finding("VIO-03", FAIL if phrase else PASS, "Potentially misleading quantity modifier detected." if phrase else "No configured misleading quantity modifier detected.", phrase.group(0) if phrase else None)

    @staticmethod
    def _report(results: list[Finding], skipped: list[Finding]) -> dict[str, Any]:
        all_findings = results + skipped
        counts = {status: sum(f.outcome == status for f in all_findings) for status in (PASS, FAIL, REVIEW, EXEMPT, SKIPPED)}
        outcome = FAIL if counts[FAIL] else REVIEW if counts[REVIEW] else EXEMPT if counts[EXEMPT] else PASS
        return {"outcome": outcome, "counts": counts, "findings": [asdict(f) for f in all_findings]}
