# SnapForge API

Screenshot & PDF generation API powered by Playwright. Self-hosted, async-first, Docker-native.

## Quick Start

```bash
git clone https://github.com/NamorNimash/snapforge-api.git
cd snapforge-api
docker compose up -d
```

API available at `http://localhost:8000`.

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/screenshot` | Create screenshot job |
| POST | `/pdf` | Create PDF job |
| GET | `/jobs/{job_id}` | Check job status |
| GET | `/files/{filename}` | Download result |
| GET | `/health` | Health check |

## Example

```bash
# 1. Submit job
curl -X POST http://localhost:8000/screenshot \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "format": "png", "full_page": true}'

# Response: {"id":"abc-123","status":"pending", ...}

# 2. Check status
curl http://localhost:8000/jobs/abc-123

# 3. Download when done
curl -o screenshot.png http://localhost:8000/files/abc-123.png
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `STORAGE_PATH` | `/data` | Where screenshots/PDFs are stored |
| `MAX_CONCURRENT` | `2` | Max parallel browser instances |
| `RENDER_TIMEOUT` | `30` | Max render time in seconds |
| `WEBHOOK_SECRET` | `` | Optional webhook HMAC secret |

## Docker Compose

```yaml
services:
  snapforge:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/data
    environment:
      - STORAGE_PATH=/data
      - MAX_CONCURRENT=2
      - RENDER_TIMEOUT=30
```

## Rate Limits

Demo endpoint (Cloudflare Tunnel): 5 requests/day per IP. Join [waitlist](https://namornimash.github.io/snapforge-landing/) for full access.

## Architecture

- **FastAPI** — request handling
- **Playwright + Chromium** — fresh browser context per job
- **Async background tasks** — submit & poll, never wait for render
- **Webhook callbacks** — get notified when job completes

## License

MIT
