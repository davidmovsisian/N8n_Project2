from __future__ import annotations

from datetime import datetime, timezone
import os
import uuid
from typing import Any

import requests as http_client
from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename
import json

app = Flask(__name__, template_folder="templates")

# ---------------------------------------------------------------------------
# Upload-flow configuration
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg"}
INCOMING_DOCS_DIR: str = os.environ.get("INCOMING_DOCS_DIR", "/home/node/incoming_docs")
N8N_WEBHOOK_URL: str = os.environ.get(
    "N8N_WEBHOOK_URL",
    "http://localhost:5678/webhook/document-intake",
)
N8N_TIMEOUT: int = int(os.environ.get("N8N_TIMEOUT", "60"))

CATEGORY_DEPARTMENT_MAP = {
    "invoice": "Finance",
    "annual report on form 10-k": "Finance",
    "annual report": "Finance",
    "contract": "Legal",
    "employment agreement": "HR",
    "policy": "Compliance",
    "security incident": "Security",
}

CATEGORIES = sorted(set(CATEGORY_DEPARTMENT_MAP.keys()))

CONFIDENTIAL_KEYWORDS = {
    "password",
    "private key",
    "token",
    "salary",
    "ssn",
    "social security",
    "account number",
    "bank account",
    "acquisition",
    "m&a",
}

INTERNAL_KEYWORDS = {
    "forecast",
    "budget",
    "roadmap",
    "strategy",
    "debt",
    "cash flow",
    "margin",
}

EXPECTED_ENTITY_GROUPS = ("people", "monetary_values", "geographic_sales", "financial_ratios")


def _as_output(payload: dict[str, Any]) -> dict[str, Any]:
    output = payload.get("output")
    if isinstance(output, dict):
        return output
    return payload


def _flatten_values(data: Any) -> list[str]:
    values: list[str] = []
    if isinstance(data, dict):
        for value in data.values():
            values.extend(_flatten_values(value))
    elif isinstance(data, list):
        for value in data:
            values.extend(_flatten_values(value))
    elif isinstance(data, (str, int, float, bool)):
        values.append(str(data))
    return values


def classify_sensitivity(payload: dict[str, Any]) -> str:
    output = _as_output(payload)
    text_blob = " ".join(_flatten_values(output)).lower()

    if any(keyword in text_blob for keyword in CONFIDENTIAL_KEYWORDS):
        return "confidential"
    if any(keyword in text_blob for keyword in INTERNAL_KEYWORDS):
        return "internal"
    return "public"


def _department_for_classification(classification: str) -> str:
    normalized = classification.strip().lower()
    return CATEGORY_DEPARTMENT_MAP.get(normalized, "Operations")


def _confidence_adjustment(output: dict[str, Any]) -> float:
    entities = output.get("entities") or {}
    if not isinstance(entities, dict):
        return -0.1

    populated = sum(1 for key in EXPECTED_ENTITY_GROUPS if entities.get(key))
    completeness = populated / len(EXPECTED_ENTITY_GROUPS)

    if completeness >= 1:
        return 0.2
    if completeness >= 0.75:
        return 0.1
    if completeness >= 0.5:
        return 0.0
    return -0.1


def enrich_payload(payload: dict[str, Any]) -> dict[str, Any]:
    output = _as_output(payload)
    classification = str(output.get("classification", "")).strip()
    sensitivity = classify_sensitivity(payload)
    confidence_adjustment = _confidence_adjustment(output)

    routing_tags = []
    if sensitivity == "confidential":
        routing_tags.append("escalate")
    if confidence_adjustment < 0 or not classification:
        routing_tags.append("needs-review")
    else:
        routing_tags.append("auto-approved")

    return {
        "output": output,
        "metadata": {
            "document_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "category": classification,
            "department": _department_for_classification(classification),
            "sensitivity": sensitivity,
            "routing_tags": routing_tags,
            "confidence_adjustment": confidence_adjustment,
        },
    }


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/categories")
def categories():
    return jsonify({"categories": CATEGORIES})


@app.post("/sensitivity")
def sensitivity():
    payload = request.get_json(silent=True) or {}
    return jsonify({"sensitivity": classify_sensitivity(payload)})


@app.post("/enrich")
def enrich():
    payload = request.get_json(silent=True) or {}
    json_payload = json.dumps(payload, indent=2)
    print(f"Received payload:\n{json_payload}")
    return jsonify(enrich_payload(payload))


# ---------------------------------------------------------------------------
# UI + direct-upload flow
# ---------------------------------------------------------------------------

@app.get("/")
def index():
    return render_template("index.html")


@app.post("/upload-file")
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "No file selected"}), 400

    filename = secure_filename(f.filename)
    if not filename:
        return jsonify({"error": "Invalid file name"}), 400

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type: {ext}"}), 415

    os.makedirs(INCOMING_DOCS_DIR, exist_ok=True)
    save_path = os.path.join(INCOMING_DOCS_DIR, filename)

    try:
        f.save(save_path)
    except OSError:
        return jsonify({"error": "Failed to save uploaded file"}), 500

    try:
        webhook_response = http_client.post(
            N8N_WEBHOOK_URL,
            json={"filename": filename},
            timeout=N8N_TIMEOUT,
        )
        webhook_response.raise_for_status()
    except http_client.exceptions.Timeout:
        return jsonify({"error": "n8n webhook timed out"}), 504
    except http_client.exceptions.RequestException:
        return jsonify({"error": "Webhook request failed"}), 502

    resp_content_type = webhook_response.headers.get("Content-Type", "")
    if "application/json" in resp_content_type:
        try:
            data = webhook_response.json()
            return jsonify({"filename": filename, "status": "ok", "result": data})
        except ValueError:
            pass

    return jsonify(
        {
            "filename": filename,
            "status": "ok",
            "result": webhook_response.text,
            "content_type": resp_content_type,
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
