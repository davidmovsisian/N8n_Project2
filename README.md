# N8N Project 2

## Enrichment microservice

A lightweight Python service is available at `src/enrichment_service.py`.

### Endpoints
- `POST /enrich` — enriches Gemini/LLM JSON output with metadata
- `GET /health` — returns exactly `{"status": "ok"}`
- `GET /categories` — returns available document categories
- `POST /sensitivity` — returns `public`, `internal`, or `confidential`

### Run locally
```bash
pip install -r requirements.txt
python src/enrichment_service.py
```

Service URL defaults to `http://localhost:8000`.

### Sample payload
A realistic payload fixture is included at:
- `tests/fixtures/enrich_input_example.json`

## n8n integration

The workflow (`N8N_Project.json`) now contains an HTTP Request node named exactly **`Enrich analysys`**.

- It calls `POST /enrich` on the enrichment service.
- It uses environment variable `ENRICH_SERVICE_BASE_URL` with fallback to `http://enrichment-service:8000`.

`docker-compose.yaml` now includes an `enrichment-service` container and sets:
- `ENRICH_SERVICE_BASE_URL=http://enrichment-service:8000`

## Tests

Run the microservice tests:
```bash
python -m unittest discover -s tests -p "test_*.py"
```
