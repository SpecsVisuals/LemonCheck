# LemonCheck — API Reference

> FastAPI endpoint documentation.

## Endpoints

### `GET /demo`
Returns a pre-computed DealReport. No auth required. Designed for demo/recruiter access.

### `POST /analyze`
Runs a full analysis. Requires: `Authorization: Bearer <supabase_jwt>`.

**Request body:**
```json
{ "listing_url": "https://..." }
```
OR
```json
{ "vin": "1HGCM82633A123456" }
```

**Response:** DealReport JSON (see `analysis_schema.json`)

**Error codes:**
- `401` — missing or invalid auth token
- `402` — monthly usage limit reached
- `422` — invalid input (bad URL or VIN format)
