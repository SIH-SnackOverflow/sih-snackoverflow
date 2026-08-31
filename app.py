"""Run: GEMINI_API_KEY=... python app.py path/to/package.jpg"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from gemini_extractor import extract_label
from rule_engine import RuleEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="Gemini-assisted package-label review")
    parser.add_argument("image", help="front/PDP image of a package label")
    parser.add_argument("--output", default="reports/report.json", help="where to write the audit report")
    args = parser.parse_args()
    extraction = extract_label(args.image)
    report = RuleEngine().evaluate(extraction)
    report["extraction"] = extraction
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"outcome": report["outcome"], "counts": report["counts"], "report": str(destination)}, indent=2))


if __name__ == "__main__":
    main()
