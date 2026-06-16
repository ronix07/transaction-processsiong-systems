from fastapi import FastAPI

from app.api.routes import jobs

app = FastAPI(title="AI-Powered Transaction Processing Pipeline")

app.include_router(jobs.router)


@app.get("/health")
def health():
    return {"status": "ok"}
