# Gemini package-label compliance prototype

This backend sends a label image to Gemini for **cautious extraction** and uses a
deterministic Python rule engine for the decision report. It is a review aid, not
legal advice and not proof of compliance.

## Run (command line)

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
export GEMINI_API_KEY='your key here'
.venv/bin/python app.py /absolute/path/to/label.jpg
```

The key stays in the environment; it is never written to a source file or report.
The output is `reports/report.json` and includes Gemini's raw structured
extraction, normalized evidence boxes (`[ymin, xmin, ymax, xmax]`, 0–1000), and
each rule result.

## Dashboard (FastAPI + React)

The dashboard provides a browser-based image upload, review summary, configurable
check results, and the raw cautious extraction data. It does not persist uploaded
images: the FastAPI service creates a temporary file only for the Gemini request,
then deletes it.

In one terminal, start the API:

```bash
python3 -m venv .venv-dashboard
.venv-dashboard/bin/pip install -r requirements.txt
export GEMINI_API_KEY='your key here'
.venv-dashboard/bin/uvicorn api:app --reload --port 8000
```

In another terminal, start the React app:

```bash
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite (normally `http://localhost:5173`). In local
development, Vite securely proxies `/api` requests to FastAPI on port 8000, so no
browser environment variable is required. Set `VITE_API_URL` only if the API is
deployed elsewhere.

## Implemented checks

- Scope exemptions: clear B2B marking, restaurant/hotel fast food, and DPCO drug
  formulation only when the image explicitly rules out a medical device.
- Manufacturer/packer/importer, origin, generic name, quantity, dates, MRP,
  consumer care, and language evidence.
- Non-SI count terms, sub-threshold large-unit declarations, and configured
  misleading quantity modifiers.

## Deliberately skipped, with a report entry

EX-01's large-package exemption is also not automatically granted: the
cement/fertilizer/agricultural-produce exception must be resolved by a human.
TYP-01 through TYP-05 are not evaluated because a normal photo has no known
physical scale, package geometry, or trustworthy per-glyph measurements.
VIO-04 is not evaluated because sticker-overlay detection needs multi-view human
inspection. VIO-05 is not evaluated until a current, versioned Schedule II
commodity/pack-size table is supplied. EX-02 is also not separately encoded: the
provided specification omits the exact bulk exemption conditions.

Do not treat `NEEDS_REVIEW` as a violation: it means the image/model did not supply
enough reliable evidence. A `POSSIBLE_VIOLATION` means the extracted declaration
positively matched the configured prohibited pattern and should be checked by a
human.

The current public rules and amendments must be reviewed by qualified counsel
before production use. The Department of Consumer Affairs publishes the packaged
commodities rules and amendments at https://consumeraffairs.nic.in/.
