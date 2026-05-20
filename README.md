# N8N Project 2

## Document Analyzer — Upload UI

A web-based interface is available at `GET /` served by the Flask enrichment service.

### Flow
1. User drags and drops (or picks) a file in the browser.
2. The browser sends `POST /upload-file` (multipart/form-data) to Flask.
3. Flask validates the file, then forwards it to the configured n8n webhook.
4. Flask returns the n8n response as structured JSON.
5. The browser renders the result (HTML preview or JSON) in the preview panel.

### Supported file types
`.pdf`, `.docx`, `.txt`, `.png`, `.jpg`, `.jpeg`

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `N8N_WEBHOOK_URL` | `http://localhost:5678/webhook/document-intake` | Full URL of the n8n webhook endpoint |
| `N8N_TIMEOUT` | `60` | Seconds to wait for the n8n webhook response |

### Run locally
```bash
pip install -r requirements.txt
N8N_WEBHOOK_URL=http://localhost:5678/webhook/document-intake python src/enrichment_service.py
```

Then open `http://localhost:8000` in your browser.

---

## Enrichment microservice

A lightweight Python service is available at `src/enrichment_service.py`.

### Endpoints
- `GET /` — Document Analyzer web UI
- `POST /upload-file` — accepts a file upload, calls the n8n webhook, returns JSON result
- `POST /enrich` — enriches Gemini/LLM JSON output with metadata
- `GET /health` — returns exactly `{"status": "ok"}`
- `GET /categories` — returns available document categories
- `POST /sensitivity` — returns `public`, `internal`, or `confidential`

### Sample payload
A realistic payload fixture is included at:
- `tests/fixtures/enrich_input_example.json`

## n8n integration

The workflow (`N8N_Project.json`) now contains an HTTP Request node named exactly **`Enrich analysys`**.

- It calls `POST /enrich` on the enrichment service.
- It uses environment variable `ENRICH_SERVICE_BASE_URL` with fallback to `http://enrichment-service:8000`.

`docker-compose.yaml` now includes an `enrichment-service` container and sets:
- `ENRICH_SERVICE_BASE_URL=http://enrichment-service:8000`
- The enrichment service container is built from `Dockerfile.enrichment`

Add `N8N_WEBHOOK_URL` to the `enrichment-service` environment block in `docker-compose.yaml` to point at the n8n container:
```yaml
environment:
  - N8N_WEBHOOK_URL=http://n8n:5678/webhook/document-intake
```

## Tests

Run the microservice tests:
```bash
python -m unittest discover -s tests -p "test_*.py"
```

