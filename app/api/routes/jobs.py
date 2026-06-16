from collections import defaultdict

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import (
    JobListItem,
    JobStatusOut,
    ResultsOut,
    TransactionOut,
)
from app.db.base import get_db
from app.db.models import Job, Transaction
from app.worker.tasks import process_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/upload", status_code=201)
def upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Only .csv files are accepted")

    raw = file.file.read()
    if not raw.strip():
        raise HTTPException(400, "Uploaded CSV is empty")
    try:
        csv_text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "CSV must be UTF-8 encoded")

    job = Job(filename=file.filename, status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)

    process_job.delay(job.id, csv_text)
    return {"job_id": job.id, "status": job.status, "message": "Job enqueued"}


@router.get("", response_model=list[JobListItem])
def list_jobs(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(Job).order_by(Job.created_at.desc())
    if status:
        stmt = stmt.where(Job.status == status)
    return db.scalars(stmt).all()


@router.get("/{job_id}/status", response_model=JobStatusOut)
def job_status(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return job


@router.get("/{job_id}/results", response_model=ResultsOut)
def job_results(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    if job.status != "completed":
        raise HTTPException(409, f"Job not completed (status={job.status})")

    txns = db.scalars(
        select(Transaction).where(Transaction.job_id == job_id)
    ).all()

    category_breakdown: dict[str, float] = defaultdict(float)
    for t in txns:
        cat = t.llm_category or t.category or "Uncategorised"
        category_breakdown[cat] += t.amount

    return ResultsOut(
        job_id=job.id,
        status=job.status,
        transactions=[TransactionOut.model_validate(t) for t in txns],
        anomalies=[TransactionOut.model_validate(t) for t in txns if t.is_anomaly],
        category_breakdown={k: round(v, 2) for k, v in category_breakdown.items()},
        summary=job.summary,
    )
