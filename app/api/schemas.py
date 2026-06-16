from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    status: str
    row_count_raw: int
    created_at: datetime


class SummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_spend_inr: float
    total_spend_usd: float
    top_merchants: list
    anomaly_count: int
    narrative: str | None
    risk_level: str | None


class JobStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    filename: str
    row_count_raw: int
    row_count_clean: int
    error_message: str | None = None
    summary: SummaryOut | None = None


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    txn_id: str | None
    date: str | None
    merchant: str | None
    amount: float
    currency: str | None
    status: str | None
    category: str | None
    account_id: str | None
    is_anomaly: bool
    anomaly_reason: str | None
    llm_category: str | None
    llm_failed: bool


class ResultsOut(BaseModel):
    job_id: int
    status: str
    transactions: list[TransactionOut]
    anomalies: list[TransactionOut]
    category_breakdown: dict[str, float]
    summary: SummaryOut | None
