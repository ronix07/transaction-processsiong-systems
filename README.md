# AI-Powered Transaction Processing Pipeline

A backend that ingests a CSV of raw financial transactions, processes it
asynchronously through a job queue, uses an LLM (Gemini Flash) to classify
transactions and produce a narrative summary, and exposes the results through a
polling API.

## Stack

- **API**: FastAPI
- **Database**: PostgreSQL
- **Job Queue**: Celery + Redis
- **LLM**: Google Gemini Flash (free tier, `gemini-2.0-flash`)
- **Containerisation**: Docker + Docker Compose

## Architecture

```
Client ──POST /jobs/upload──> FastAPI ──enqueue──> Redis ──dequeue──> Celery Worker ──> PostgreSQL
   ^                             |                                          |
   └────GET /status, /results───┘                                   Gemini Flash
                                                                  (batched LLM calls)
```

Worker pipeline (runs in order per job):

1. `clean_csv()` — normalise dates to ISO 8601, strip `$`, uppercase status, fill missing categories, drop exact duplicates
2. `detect_anomalies()` — flag amount > 3× account median, and USD on domestic-only merchants
3. `classify_categories()` — **one batched** LLM call for all uncategorised rows
4. bulk-save `Transaction` rows
5. `generate_narrative()` — single LLM call producing the JSON summary

LLM calls retry up to 3× with exponential backoff. On final failure the batch
is marked `llm_failed` and the job continues — it never fails the whole job.

## Quick start

```bash
# 1. Provide a Gemini API key (free tier).
cp .env.example .env
#   then edit .env and set GEMINI_API_KEY=...

# 2. Start everything (api, worker, redis, postgres) with one command.
docker compose up --build
```

The API is then available at `http://localhost:8000` (docs at `/docs`).
Migrations run automatically on startup.

> Without a `GEMINI_API_KEY`, the pipeline still runs end-to-end: LLM steps are
> marked `llm_failed` and a fallback narrative is stored.

## API endpoints

### Upload a CSV

```bash
curl -F "file=@transactions.csv" http://localhost:8000/jobs/upload
# -> {"job_id": 1, "status": "pending"}
```

### Poll job status

```bash
curl http://localhost:8000/jobs/1/status
# -> {"id":1,"status":"completed","row_count_raw":95,"row_count_clean":88,"summary":{...}}
```

### Get full results

```bash
curl http://localhost:8000/jobs/1/results
# -> cleaned transactions, flagged anomalies, per-category breakdown, narrative summary
```

### List jobs (filter by status)

```bash
curl http://localhost:8000/jobs
curl "http://localhost:8000/jobs?status=completed"
```

## Data model

- **Job** — `id, filename, status, row_count_raw, row_count_clean, created_at, completed_at, error_message`
- **Transaction** — `id, job_id, txn_id, date, merchant, amount, currency, status, category, account_id, notes, is_anomaly, anomaly_reason, llm_category, llm_raw_response, llm_failed`
- **JobSummary** — `id, job_id, total_spend_inr, total_spend_usd, top_merchants (JSON), anomaly_count, narrative, risk_level`

## Project layout

```
app/
  main.py            FastAPI entry, registers routes
  config.py          env-var settings
  api/
    schemas.py       Pydantic request/response models
    routes/jobs.py   the 4 endpoints
  db/
    base.py          SQLAlchemy engine + session
    models.py        ORM models
  services/
    cleaner.py       CSV cleaning
    anomaly.py       anomaly detection
    llm.py           Gemini calls (batched classify + narrative, retry)
  worker/
    celery_app.py    Celery instance
    tasks.py         process_job — orchestrates the 5 pipeline steps
alembic/             database migrations
```

A sample `transactions.csv` is included for testing.
