"""
Deterministic Legal Metrology (Packaged Commodities) Rules, 2011 Engine.
Evaluates structured extraction data against statutory rules and schedules.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable

PASS = "PASS"
FAIL = "POSSIBLE_VIOLATION"
REVIEW = "NEEDS_REVIEW"
EXEMPT = "EXEMPT"
SKIPPED = "SKIPPED"

# Standard Quantity & Unit Regex
QTY_RE = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*(mg|g|gm|gms|kg|kgs|ml|l|ltr|litre|litres|liter|liters|m|meter|metre|cm|mm|count|pcs?|pieces?|nos?|dozen|score|gross)\b",
    re.I,
)
DATE_RE = re.compile(
    r"(?:0?[1-9]|1[0-2])\s*[-/.]\s*(?:\d{4}|\d{2})|(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s*[-,/. ]\s*\d{4}",
    re.I,
)
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_RE = re.compile(r"(?:\+91[- ]?)?(?:[6-9]\d{9}|1800[- ]?\d{3,4}[- ]?\d{3,4}|0\d{2,4}[- ]?\d{6,8})")
MRP_RE = re.compile(r"\b(?:mrp|maximum retail price)\b.*(?:rs\.?|inr|₹)\s*\d", re.I)
TAX_RE = re.compile(r"\bincl(?:usive|\.)?\s+(?:of\s+)?(?:all\s+)?tax(?:es)?\b", re.I)
USP_RE = re.compile(r"(?:usp|unit\s+sale\s+price|₹\s*\/\s*(?:g|kg|ml|l|piece|unit|item)|rs\.?\s*\/\s*(?:g|kg|ml|l|piece|unit|item))", re.I)

# Schedule II Standard Pack Sizes (Commodity -> permitted sizes in standard SI units: g, ml, etc.)
SCHEDULE_II_STANDARDS: dict[str, dict[str, Any]] = {
    "tea": {"unit": "g", "sizes": {25, 50, 75, 100, 125, 150, 200, 250, 500, 1000}},
    "coffee": {"unit": "g", "sizes": {25, 50, 75, 100, 150, 200, 500, 1000}},
    "biscuit": {"unit": "g", "sizes": {25, 50, 60, 75, 100, 120, 150, 200, 250, 300, 500, 1000}},
    "biscuits": {"unit": "g", "sizes": {25, 50, 60, 75, 100, 120, 150, 200, 250, 300, 500, 1000}},
    "baby food": {"unit": "g", "sizes": {200, 400, 500, 1000}},
    "weaning food": {"unit": "g", "sizes": {200, 400, 500, 1000}},
    "salt": {"unit": "g", "sizes": {100, 200, 500, 1000, 2000, 5000}},
    "atta": {"unit": "g", "sizes": {100, 200, 500, 1000, 2000, 5000, 10000}},
    "wheat flour": {"unit": "g", "sizes": {100, 200, 500, 1000, 2000, 5000, 10000}},
    "rice": {"unit": "g", "sizes": {100, 200, 500, 1000, 2000, 5000, 10000}},
    "pulses": {"unit": "g", "sizes": {100, 200, 500, 1000, 2000, 5000}},
    "edible oil": {"unit": "ml", "sizes": {50, 100, 200, 500, 1000, 2000, 3000, 5000}},
    "vanaspati": {"unit": "ml", "sizes": {50, 100, 200, 500, 1000, 2000, 3000, 5000}},
}

AGRICULTURAL_OR_COMMODITY_PRODUCE = {
    "cement", "fertilizer", "fertiliser", "urea", "potash", "paddy", "rice",
    "wheat", "grain", "seed", "flour", "atta", "maida", "suji", "sugar", "pulses"
}


@dataclass(frozen=True)
class Finding:
    rule_id: str
    outcome: str
    message: str
    observed: Any = None


def present(value: Any) -> bool:
    return value is not None and str(value).strip() != "" and str(value).strip().lower() != "none"


def party_complete(value: Any) -> bool:
    return isinstance(value, dict) and present(value.get("name")) and present(value.get("address"))


def parse_quantity(value: Any) -> tuple[float, str] | None:
    match = QTY_RE.match(str(value or ""))
    if not match:
        return None
    amount = float(match.group(1))
    unit = match.group(2).lower()
    unit_map = {
        "gm": "g", "gms": "g",
        "kgs": "kg",
        "ltr": "l", "litre": "l", "litres": "l", "liter": "l", "liters": "l",
        "meter": "m", "metre": "m",
        "pc": "count", "pcs": "count", "piece": "count", "pieces": "count",
        "no": "count", "nos": "count",
    }
    return amount, unit_map.get(unit, unit)


def to_base_unit(amount: float, unit: str) -> tuple[float, str]:
    if unit == "kg":
        return amount * 1000.0, "g"
    if unit == "l":
        return amount * 1000.0, "ml"
    if unit == "m":
        return amount * 100.0, "cm"
    return amount, unit


def finding(rule_id: str, ok: bool, message: str, observed: Any = None) -> Finding:
    return Finding(
        rule_id,
        PASS if ok else REVIEW,
        message if ok else f"Cannot verify: {message}",
        observed,
    )


class RuleEngine:
    """
    Legal Metrology (Packaged Commodities) Rules, 2011 Compliance Engine.
    Only emits POSSIBLE_VIOLATION when evidence positively violates statutory provisions.
    """

    def evaluate(self, data: dict[str, Any]) -> dict[str, Any]:
        exemptions = self._exemptions(data)
        if exemptions:
            return self._report(exemptions, [])

        mandatory_findings = list(self._mandatory(data))
        format_findings = list(self._declaration_format(data))
        typography_findings = list(self._typography_and_placement(data))

        results = mandatory_findings + format_findings + typography_findings
        skipped = self._skipped_rules(data)

        return self._report(results, skipped)

    def _exemptions(self, d: dict[str, Any]) -> list[Finding]:
        q = parse_quantity(d.get("net_quantity"))
        gen_name = str(d.get("generic_name") or "").lower()

        # Rule 3(a): > 25 kg or 25 L (Excluding cement, fertilizer, agricultural produce up to 50kg)
        if q and ((q[1] == "kg" and q[0] > 25) or (q[1] == "l" and q[0] > 25)):
            is_agri_or_cement = any(word in gen_name for word in AGRICULTURAL_OR_COMMODITY_PRODUCE)
            if is_agri_or_cement and q[0] <= 50:
                # Not exempt under proviso to Rule 3(a)
                pass
            elif q[0] > 50 or not is_agri_or_cement:
                return [Finding("EX-01", EXEMPT, f"Large package (>25 kg/L) exempt under Rule 3(a): {d.get('net_quantity')}", d.get("net_quantity"))]

        # Rule 3(b): Institutional / Industrial consumers
        if d.get("not_for_retail_sale") is True and (d.get("industrial_or_institutional_only") is True or d.get("bulk_package") is True):
            return [Finding("EX-03", EXEMPT, "Exempt under Rule 3(b): Packaged for industrial/institutional consumers (not for retail sale).")]

        # Rule 3(c): Fast food packed by restaurant or hotel
        if d.get("fast_food_packed_by_restaurant_or_hotel") is True:
            return [Finding("EX-04", EXEMPT, "Exempt under Rule 3(c): Fast food packed by restaurant or hotel.")]

        # Rule 3(d): DPCO Drug formulation
        if d.get("drug_formulation_under_dpc") is True and d.get("medical_device_declared_as_drug") is False:
            return [Finding("EX-04", EXEMPT, "Exempt under Rule 3(d): Scheduled drug formulation under DPCO.")]

        return []

    def _mandatory(self, d: dict[str, Any]) -> Iterable[Finding]:
        # MD-01: Rule 6(1)(a) - Manufacturer / Packer
        mfg = d.get("manufacturer") or d.get("packer")
        yield finding("MD-01", party_complete(mfg), "Manufacturer/Packer name and complete postal address", mfg)

        # MD-02: Rule 6(1)(a) & (b) - Importer & Country of Origin
        if d.get("is_imported") is True:
            yield finding(
                "MD-02",
                party_complete(d.get("importer")) and present(d.get("country_of_origin")),
                "Importer name/address and country of origin for imported goods",
                {"importer": d.get("importer"), "country_of_origin": d.get("country_of_origin")},
            )

        # MD-03: Rule 6(1)(b) - Generic Name
        yield finding("MD-03", present(d.get("generic_name")), "Common or generic commodity name", d.get("generic_name"))

        # MD-04: Rule 6(1)(c) - Standard Net Quantity
        q = parse_quantity(d.get("net_quantity"))
        yield finding(
            "MD-04",
            q is not None and q[1] not in {"dozen", "score", "gross"},
            "Net quantity declared in a recognized standard unit",
            d.get("net_quantity"),
        )

        # MD-05: Rule 6(1)(d) - Month & Year of Manufacture / Packing
        if d.get("manufacture_date_exempt") is True:
            yield Finding("MD-05", EXEMPT, "Manufacture date exemption recognized (Rule 6(1)(d) proviso).")
        else:
            yield finding(
                "MD-05",
                bool(DATE_RE.search(str(d.get("manufacture_month_year") or ""))),
                "Manufacture/pre-pack/import month and year",
                d.get("manufacture_month_year"),
            )

        # MD-06: Rule 6(1)(d) Proviso - Best Before / Expiry
        if d.get("may_become_unfit_for_consumption") is True or present(d.get("best_before_or_use_by")):
            yield finding(
                "MD-06",
                bool(DATE_RE.search(str(d.get("best_before_or_use_by") or ""))),
                "Best-before / use-by date declaration",
                d.get("best_before_or_use_by"),
            )

        # MD-07: Rule 6(1)(e) - MRP Inclusive of all taxes
        mrp = str(d.get("mrp_declaration") or "")
        has_mrp = bool(MRP_RE.search(mrp))
        has_tax = bool(TAX_RE.search(mrp))
        yield finding(
            "MD-07",
            has_mrp and has_tax,
            "MRP amount declared with 'inclusive of all taxes'",
            d.get("mrp_declaration"),
        )

        # MD-08: Rule 6(1)(f) - Consumer Care
        care = d.get("consumer_care") or {}
        care_ok = party_complete(care) and bool(PHONE_RE.search(str(care.get("phone") or ""))) and bool(EMAIL_RE.match(str(care.get("email") or "")))
        yield finding("MD-08", care_ok, "Consumer care details (Designated name, postal address, phone, email)", care)

        # MD-09: Rule 9(1) - Declaration Language
        languages = set(d.get("language_codes") or [])
        yield finding("MD-09", bool(languages & {"en", "hi-Deva", "hi"}), "Declarations in English or Hindi (Devanagari)", sorted(languages))

        # MD-10: Rule 6(1)(g) - Unit Sale Price (USP)
        full_text = str(d.get("full_text") or "")
        usp_declared = bool(USP_RE.search(mrp)) or bool(USP_RE.search(full_text)) or present(d.get("unit_sale_price"))
        if q and ((q[1] in {"kg", "l"} and q[0] > 1) or (q[1] in {"g", "ml"} and q[0] > 1000) or (q[1] == "count" and q[0] > 1)):
            yield finding("MD-10", usp_declared, "Unit Sale Price (USP) declared for multi-unit/bulk retail commodity", d.get("unit_sale_price") or mrp)

    def _declaration_format(self, d: dict[str, Any]) -> Iterable[Finding]:
        text = str(d.get("full_text") or "")
        q = parse_quantity(d.get("net_quantity"))

        # VIO-01: Prohibited Count Units (dozen, gross, score)
        bad_unit = q and q[1] in {"dozen", "score", "gross"}
        yield Finding(
            "VIO-01",
            FAIL if bad_unit else PASS,
            "Non-standard count unit detected." if bad_unit else "No prohibited count unit detected.",
            d.get("net_quantity"),
        )

        # VIO-02: Sub-threshold Unit Escalation (<1 kg in kg, <1 L in L)
        if q:
            number, unit = q
            wrong = (unit == "kg" and number < 1.0) or (unit == "m" and number < 1.0) or (unit == "l" and number < 1.0)
            yield Finding(
                "VIO-02",
                FAIL if wrong else PASS,
                "Sub-threshold quantity expressed in larger unit (< 1 kg/L/m must use g/ml/cm)." if wrong else "Unit threshold check passed.",
                d.get("net_quantity"),
            )
        else:
            yield Finding("VIO-02", REVIEW, "Cannot verify unit threshold without readable net quantity.")

        # VIO-03: Misleading Net Quantity Modifiers
        phrase = re.search(r"\b(?:minimum|not\s+less\s+than|average|about|approximately|when\s+packed|net\s+weight\s+when\s+packed)\b", text, re.I)
        yield Finding(
            "VIO-03",
            FAIL if phrase else PASS,
            f"Misleading quantity qualifier detected: '{phrase.group(0)}'." if phrase else "No prohibited quantity modifier detected.",
            phrase.group(0) if phrase else None,
        )

        # VIO-04: Rule 18(2) Sticker Overwriting / MRP Tampering
        if d.get("mrp_sticker_covers_printed_mrp") is True:
            yield Finding("VIO-04", FAIL, "Sticker overlay detected over original printed MRP (Rule 18(2) violation).", True)
        elif d.get("mrp_sticker_covers_printed_mrp") is False:
            yield Finding("VIO-04", PASS, "No sticker alteration detected over MRP declaration.", False)
        else:
            yield Finding("VIO-04", REVIEW, "Visual sticker overlay status not confirmed from image evidence.", None)

        # VIO-05: Schedule II Pack Sizes
        gen_name = str(d.get("generic_name") or "").lower().strip()
        matched_sched = None
        for item_key, cfg in SCHEDULE_II_STANDARDS.items():
            if item_key in gen_name:
                matched_sched = (item_key, cfg)
                break

        if matched_sched and q:
            item_name, cfg = matched_sched
            base_amount, base_unit = to_base_unit(q[0], q[1])
            if base_unit == cfg["unit"]:
                if base_amount in cfg["sizes"] or (base_amount > max(cfg["sizes"]) and base_amount % 1000 == 0):
                    yield Finding("VIO-05", PASS, f"Schedule II standard pack size verified for {item_name.title()}.", d.get("net_quantity"))
                else:
                    yield Finding(
                        "VIO-05",
                        FAIL,
                        f"Non-standard pack size for {item_name.title()} under Schedule II (Permitted: {sorted(cfg['sizes'])} {cfg['unit']}).",
                        d.get("net_quantity"),
                    )
            else:
                yield Finding("VIO-05", REVIEW, f"Schedule II pack size requires unit '{cfg['unit']}', observed '{q[1]}'.", d.get("net_quantity"))
        elif matched_sched and not q:
            yield Finding("VIO-05", REVIEW, "Commodity falls under Schedule II rationalized sizing, but net quantity is unreadable.")
        else:
            yield Finding("VIO-05", PASS, "Commodity is not subject to Schedule II rationalized pack size restrictions.")

    def _typography_and_placement(self, d: dict[str, Any]) -> Iterable[Finding]:
        evidence = d.get("evidence") or []
        boxes = [e.get("box_2d") for e in evidence if isinstance(e.get("box_2d"), list) and len(e.get("box_2d")) == 4]

        # TYP-01: Rule 7 - Declarations on Principal Display Panel
        if boxes:
            all_within_panel = all(0 <= b[0] <= 1000 and 0 <= b[1] <= 1000 and 0 <= b[2] <= 1000 and 0 <= b[3] <= 1000 for b in boxes)
            yield Finding("TYP-01", PASS if all_within_panel else REVIEW, "Mandatory declarations positioned on Principal Display Panel.", len(boxes))
        else:
            yield Finding("TYP-01", REVIEW, "Principal Display Panel boundary geometry could not be measured without evidence coordinates.")

        # TYP-02: Rule 7 / Schedule I - Proportional Numeral Height Heuristic
        qty_boxes = [e["box_2d"] for e in evidence if "quant" in str(e.get("field", "")).lower() and len(e.get("box_2d", [])) == 4]
        if qty_boxes:
            box = qty_boxes[0]
            height_ratio = (box[2] - box[0]) / 1000.0  # Height normalized 0..1
            if height_ratio >= 0.015:  # At least 1.5% of display height
                yield Finding("TYP-02", PASS, f"Quantity numeral font height meets proportional display threshold ({height_ratio*100:.1f}% PDP height).", box)
            elif height_ratio < 0.008:
                yield Finding("TYP-02", FAIL, f"Quantity numeral font appears undersized relative to display panel ({height_ratio*100:.1f}% PDP height).", box)
            else:
                yield Finding("TYP-02", REVIEW, f"Quantity numeral font size is borderline ({height_ratio*100:.1f}% PDP height); physical gauge verification recommended.", box)
        else:
            yield Finding("TYP-02", REVIEW, "Net quantity bounding box unavailable for font height measurement.")

        # TYP-03: Rule 8 - Letter & Numeral Aspect Ratio (Width >= 1/3 Height)
        if qty_boxes:
            box = qty_boxes[0]
            box_h = max(1, box[2] - box[0])
            box_w = max(1, box[3] - box[1])
            aspect = box_w / box_h
            # Single characters need width >= 0.33 of height; whole declaration boxes should be wider than height
            yield Finding("TYP-03", PASS if aspect >= 0.33 else FAIL, "Numeral aspect ratio complies with Rule 8 (Width >= 1/3 Height)." if aspect >= 0.33 else "Numeral appears compressed (Width < 1/3 Height).", {"aspect_ratio": round(aspect, 2)})
        else:
            yield Finding("TYP-03", REVIEW, "Cannot compute numeral aspect ratio without glyph/declaration bounding box.")

        # TYP-04: Rule 9(2) - Visual Contrast & Plain Legibility
        low_confidence_fields = [e.get("field") for e in evidence if str(e.get("confidence", "")).upper() in {"LOW", "UNCERTAIN"}]
        if low_confidence_fields:
            yield Finding("TYP-04", REVIEW, f"Low contrast or unreadable lettering detected on: {', '.join(low_confidence_fields)}.", low_confidence_fields)
        elif evidence:
            yield Finding("TYP-04", PASS, "Mandatory declarations exhibit distinct contrast and plain legibility.", "HIGH_CONFIDENCE")
        else:
            yield Finding("TYP-04", REVIEW, "Legibility contrast requires visual evidence validation.")

        # TYP-05: Rule 9(3) - Surrounding Clear Space (No Heavy Overlap)
        if len(boxes) >= 2 and qty_boxes:
            q_box = qty_boxes[0]
            overlapping = False
            for b in boxes:
                if b == q_box:
                    continue
                # Calculate simple intersection area
                yi1, xi1, yi2, xi2 = max(q_box[0], b[0]), max(q_box[1], b[1]), min(q_box[2], b[2]), min(q_box[3], b[3])
                if yi2 > yi1 and xi2 > xi1:
                    overlap_area = (yi2 - yi1) * (xi2 - xi1)
                    q_area = (q_box[2] - q_box[0]) * (q_box[3] - q_box[1])
                    if q_area > 0 and (overlap_area / q_area) > 0.4:
                        overlapping = True
                        break
            yield Finding("TYP-05", FAIL if overlapping else PASS, "Clear space surrounding net quantity numerals is maintained." if not overlapping else "Net quantity numeral obstructed by overlapping print.", q_box)
        else:
            yield Finding("TYP-05", PASS, "No obstructing overlays detected around net quantity declaration.")

    def _skipped_rules(self, d: dict[str, Any]) -> list[Finding]:
        # Rules that require external legal certification or physical laboratory equipment
        return [
            Finding("EX-02", SKIPPED, "Bulk exemption for specialized industrial wholesale requires distributor consignment invoice review."),
        ]

    @staticmethod
    def _report(results: list[Finding], skipped: list[Finding]) -> dict[str, Any]:
        all_findings = results + skipped
        counts = {status: sum(f.outcome == status for f in all_findings) for status in (PASS, FAIL, REVIEW, EXEMPT, SKIPPED)}
        outcome = FAIL if counts[FAIL] else REVIEW if counts[REVIEW] else EXEMPT if counts[EXEMPT] else PASS
        return {"outcome": outcome, "counts": counts, "findings": [asdict(f) for f in all_findings]}
