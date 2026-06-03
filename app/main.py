from fastapi import FastAPI, HTTPException
from app.models import RecordIn, RecordOut
from app.store import store
import uuid, os

app = FastAPI(
    title="MediFlow",
    description="Clinical data ingestion and validation API",
    version="1.0.0",
)


@app.post("/records", response_model=RecordOut, status_code=201)
def create_record(payload: RecordIn):
    record_id = str(uuid.uuid4())
    record = RecordOut(id=record_id, **payload.model_dump())
    store[record_id] = record
    return record


@app.get("/records/{record_id}", response_model=RecordOut)
def get_record(record_id: str):
    record = store.get(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


@app.get("/health")
def health():
    return {"status": "ok", "version": os.getenv("APP_VERSION", "1.0.0")}
