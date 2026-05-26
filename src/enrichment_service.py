from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import uuid
from typing import Any

import requests as http_client
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__, template_folder="templates")
# app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


# @app.after_request
# def disable_static_cache(response):
#     if request.path.startswith("/static/"):
#         response.headers["Cache-Control"] = "no-store"
#     return response

# ---------------------------------------------------------------------------
# Upload-flow configuration
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}

N8N_WEBHOOK_ANALYZE_URL: str = os.environ.get(
    "N8N_WEBHOOK_ANALYZE_URL",
    "http://n8n:5678/webhook-test/document-intake",
)
N8N_WEBHOOK_QUERY_URL: str = os.environ.get(
    "N8N_WEBHOOK_QUERY_URL",
    "http://n8n:5678/webhook-test/query-document",
)
N8N_WEBHOOK_ALL_FILENAMES_URL: str = os.environ.get(
    "N8N_WEBHOOK_ALL_FILENAMES_URL",
    "http://n8n:5678/webhook-test/all-filenames",
)
N8N_TIMEOUT: int = int(os.environ.get("N8N_TIMEOUT", "60"))
INCOMING_DOCS_DIR: str = os.environ.get("INCOMING_DOCS_DIR", "/home/node/incoming_docs")
OUTPUT_DOCS_DIR: str = os.environ.get("OUTPUT_DOCS_DIR", "/home/node/output_docs")
FLASK_HOST: str = os.environ.get("FLASK_HOST", "0.0.0.0")
FLASK_PORT: int = int(os.environ.get("FLASK_PORT", "8000"))

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

    routing_tag = None
    if sensitivity == "confidential":
        routing_tag = "escalate"
    if confidence_adjustment < 0 or not classification:
        routing_tag = "needs-review"
    else:
        routing_tag = "auto-approved"       

    return {
            "metadata": {
            "document_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "category": classification,
            "department": _department_for_classification(classification),
            "sensitivity": sensitivity,
            "routing_tag": routing_tag,
            "confidence_adjustment": confidence_adjustment,
        },
    }


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/categories")
def categories():
    return jsonify({"categories": CATEGORIES})


@app.get("/all-filenames")
def all_filenames():
    try:
        webhook_response = http_client.get(
            N8N_WEBHOOK_ALL_FILENAMES_URL,
            timeout=N8N_TIMEOUT,
        )
        webhook_response.raise_for_status()
    except http_client.exceptions.Timeout:
        return jsonify({"error": "n8n webhook timed out"}), 504
    except http_client.exceptions.RequestException:
        return jsonify({"error": "Webhook request failed"}), 502

    response_content_type = webhook_response.headers.get("Content-Type", "")
    if "application/json" in response_content_type:
        try:
            return jsonify(webhook_response.json())
        except ValueError:
            pass

    return jsonify({"error": "Unexpected response from webhook", "content_type": response_content_type}), 502


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


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/upload-file")
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    email = (request.form.get("email") or "").strip()
    if not email:
        return jsonify({"error": "Email is required"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "No file selected"}), 400

    filename = secure_filename(f.filename)
    if not filename:
        return jsonify({"error": "Invalid filename"}), 400

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type: {ext}"}), 415

    os.makedirs(INCOMING_DOCS_DIR, exist_ok=True)
    saved_path = os.path.join(INCOMING_DOCS_DIR, filename)
    f.save(saved_path)

    try:
        webhook_response = http_client.post(
            N8N_WEBHOOK_ANALYZE_URL,
            json={"filename": filename, "email": email},
            timeout=N8N_TIMEOUT,
        )
        webhook_response.raise_for_status()
    except http_client.exceptions.Timeout:
        return jsonify({"error": "n8n webhook timed out"}), 504
    except http_client.exceptions.RequestException as exc:
        return jsonify({"error": "Webhook request failed", "details": str(exc)}), 502

    response_content_type = webhook_response.headers.get("Content-Type", "")
    if "application/json" in response_content_type:
        try:
            return jsonify(
                {
                    "filename": filename,
                    "email": email,
                    "status": "ok",
                    "saved_path": saved_path,
                    "result": webhook_response.json(),
                }
            )
        except ValueError:
            pass

    return jsonify(
        {
            "filename": filename,
            "email": email,
            "status": "ok",
            "saved_path": saved_path,
            "result": webhook_response.text,
            "content_type": response_content_type,
        }
    )

@app.post("/reload-file")
def reload_file():
    filename = (request.form.get("filename") or "").strip()
    if not filename:
        return jsonify({"error": "Filename is required"}), 400

    safe_name = secure_filename(filename)
    if not safe_name:
        return jsonify({"error": "Invalid filename"}), 400

    base = os.path.splitext(safe_name)[0]
    output_filename = base + ".html"
    file_path = os.path.join(OUTPUT_DOCS_DIR, output_filename)

    if not os.path.isfile(file_path):
        return jsonify({"error": f"File not found: {output_filename}"}), 404

    with open(file_path, "r", encoding="utf-8") as fh:
        html_content = fh.read()

    return jsonify({"filename": safe_name, "status": "ok", "result": html_content})


@app.post("/document-query")
def document_query():
    filename = (request.form.get("filename") or "").strip()
    if not filename:
        return jsonify({"error": "Filename is required"}), 400
    
    query = (request.form.get("query") or "").strip()
    if not query:
        return jsonify({"error": "Query is required"}), 400

    company = (request.form.get("company") or "").strip()
    year = (request.form.get("year") or "").strip()

    try:
        webhook_response = http_client.post(
            N8N_WEBHOOK_QUERY_URL,
            json={"filename": filename, "query": query, "company": company, "year": year},
            timeout=N8N_TIMEOUT,
        )
        webhook_response.raise_for_status()
    except http_client.exceptions.Timeout:
        return jsonify({"error": "n8n webhook timed out"}), 504
    except http_client.exceptions.RequestException as exc:
        return jsonify({"error": "Webhook request failed", "details": str(exc)}), 502

    response_content_type = webhook_response.headers.get("Content-Type", "")
    if "application/json" in response_content_type:
        try:
            return jsonify(
                {
                    "query": query,
                    "status": "ok",
                    "result": webhook_response.json(),
                }
            )
        except ValueError:
            pass

    return jsonify(
        {
            "query": query,
            "status": "ok",
            "result": webhook_response.text,
            "content_type": response_content_type,
        }
    )

@app.get("/download-file")
def download_file():
    filename = request.args.get("filename", "").strip()
    if not filename:
        return jsonify({"error": "filename is required"}), 400

    safe_name = secure_filename(filename)
    if not safe_name:
        return jsonify({"error": "Invalid filename"}), 400

    base = os.path.splitext(safe_name)[0]
    output_filename = base + ".html"

    file_path = os.path.join(OUTPUT_DOCS_DIR, output_filename)
    if not os.path.isfile(file_path):
        return jsonify({"error": f"File not found: {output_filename}"}), 404

    return send_file(file_path, as_attachment=True, download_name=output_filename)


if __name__ == "__main__":
    app.run(host=FLASK_HOST, port=FLASK_PORT)