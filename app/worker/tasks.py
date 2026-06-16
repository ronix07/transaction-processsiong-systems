"""The async processing pipeline. One Celery task runs all five steps in order."""
from collections import defaultdict
from datetime import datetime, timezone

from app.db.base import SessionLocal
from app.db.models import Job, JobSummary, Transaction
from app.services import llm
from app.services.anomaly import detect_anomalies
from app.services.cleaner import clean_csv
from app.worker.celery_app import celery_app


def _final_category(row: dict) -> str:
    """LLM-assigned category wins; else the (possibly filled) original."""
    return row.get("llm_category") or row.get("category") or "Uncategorised"


@celery_app.task(name="process_job")
def process_job(job_id: int, csv_text: str) -> None:
    db = SessionLocal()
    job = db.get(Job, job_id)
    if job is None:
        db.close()
        return

    try:
        job.status = "processing"
        db.commit()

        # a) Clean
        rows, raw_count, clean_count = clean_csv(csv_text.encode("utf-8"))
        job.row_count_raw = raw_count
        job.row_count_clean = clean_count
        db.commit()

        # b) Anomaly detection
        detect_anomalies(rows)

        # c) LLM classification (batched) for rows still 'Uncategorised'
        to_classify = [
            {"id": i, "merchant": r.get("merchant"), "notes": r.get("notes")}
            for i, r in enumerate(rows)
            if r.get("category") == "Uncategorised"
        ]
        if to_classify:
            try:
                mapping, raw = llm.classify_categories(to_classify)
                for i, r in enumerate(rows):
                    if i in mapping:
                        r["llm_category"] = mapping[i]
                        r["llm_raw_response"] = raw
            except llm.LLMError:
                # Mark the batch as failed, keep going (do not fail the job).
                for item in to_classify:
                    rows[item["id"]]["llm_failed"] = True

        # d) Bulk save transactions
        db.add_all(
            Transaction(
                job_id=job.id,
                txn_id=r.get("txn_id"),
                date=r.get("date"),
                merchant=r.get("merchant"),
                amount=r.get("amount", 0.0),
                currency=r.get("currency"),
                status=r.get("status"),
                category=r.get("category"),
                account_id=r.get("account_id"),
                notes=r.get("notes"),
                is_anomaly=r.get("is_anomaly", False),
                anomaly_reason=r.get("anomaly_reason"),
                llm_category=r.get("llm_category"),
                llm_raw_response=r.get("llm_raw_response"),
                llm_failed=r.get("llm_failed", False),
            )
            for r in rows
        )
        db.commit()

        # Aggregate stats
        spend = defaultdict(float)
        merchant_spend = defaultdict(float)
        category_spend = defaultdict(float)
        anomaly_count = 0
        for r in rows:
            cur = r.get("currency") or "UNKNOWN"
            spend[cur] += r["amount"]
            if r.get("merchant"):
                merchant_spend[r["merchant"]] += r["amount"]
            category_spend[_final_category(r)] += r["amount"]
            if r.get("is_anomaly"):
                anomaly_count += 1

        top_merchants = [
            {"merchant": m, "total_spend": round(t, 2)}
            for m, t in sorted(merchant_spend.items(), key=lambda x: x[1], reverse=True)[:3]
        ]

        # e) LLM narrative (single call), degrade gracefully on failure
        stats = {
            "total_spend_inr": round(spend.get("INR", 0.0), 2),
            "total_spend_usd": round(spend.get("USD", 0.0), 2),
            "top_merchants": top_merchants,
            "anomaly_count": anomaly_count,
            "category_breakdown": {k: round(v, 2) for k, v in category_spend.items()},
        }
        try:
            narrative_out = llm.generate_narrative(stats)
            narrative = narrative_out["narrative"]
            risk_level = narrative_out["risk_level"]
        except llm.LLMError:
            narrative = "LLM narrative unavailable (llm_failed)."
            risk_level = "high" if anomaly_count > 5 else "medium"

        db.add(
            JobSummary(
                job_id=job.id,
                total_spend_inr=stats["total_spend_inr"],
                total_spend_usd=stats["total_spend_usd"],
                top_merchants=top_merchants,
                anomaly_count=anomaly_count,
                narrative=narrative,
                risk_level=risk_level,
            )
        )

        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as e:  # noqa: BLE001 - any pipeline error fails the job cleanly
        db.rollback()
        job.status = "failed"
        job.error_message = str(e)
        db.commit()
        raise
    finally:
        db.close()
