import json
import os
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.emailer import EmailRequest, build_report_email_body, send_report_email
from app.jobs import run_due_schedules
from app.reports import (
    build_report_from_csv,
    build_report_from_orders,
    save_report_snapshot,
)
from app.scheduler import ScheduleRequest, create_schedule, list_schedules
from app.shopify import ShopifyCredentials, fetch_shopify_orders


app = FastAPI(title="Sales Dashboard")
JOB_RUN_TOKEN = os.getenv("JOB_RUN_TOKEN")

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
OUTPUT_DIR = BASE_DIR / "output" / "reports"
DATABASE_DIR = BASE_DIR / "database"
DATABASE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def healthcheck() -> dict:
    return {"status": "ok"}


@app.post("/reports/csv")
async def generate_csv_report(file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file.")

    csv_path = OUTPUT_DIR / file.filename
    content = await file.read()
    csv_path.write_bytes(content)

    try:
        report = build_report_from_csv(csv_path, source_label=file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    save_report_snapshot(report, OUTPUT_DIR)
    return {"source": "csv", "report": report}


@app.post("/reports/shopify")
def generate_shopify_report(
    store_url: str = Form(...),
    api_key: str = Form(...),
    period: str = Form(default="weekly"),
) -> dict:
    credentials = ShopifyCredentials(store_url=store_url, api_key=api_key)
    orders = fetch_shopify_orders(credentials, period=period)
    if not orders:
        raise HTTPException(status_code=400, detail="Store URL and API key are required.")

    try:
        report = build_report_from_orders(orders, source_label=store_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    save_report_snapshot(report, OUTPUT_DIR)
    return {"source": "shopify", "report": report}


@app.post("/email/send")
def email_report(request: EmailRequest) -> dict:
    try:
        result = send_report_email(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@app.post("/email/send-report")
def email_generated_report(
    recipient: str = Form(...),
    report_payload: str = Form(...),
) -> dict:
    report = json.loads(report_payload)
    email_request = EmailRequest(
        recipient=recipient,
        subject=f"{report['headline']} report is ready",
        body=build_report_email_body(report),
    )
    try:
        return send_report_email(email_request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/schedules")
def schedule_report(request: ScheduleRequest) -> dict:
    payload = request.model_copy(deep=True)
    if payload.csv_path:
        payload.csv_path = str((BASE_DIR / payload.csv_path).resolve())
    schedule_id = create_schedule(payload)
    return {"status": "scheduled", "schedule_id": schedule_id}


@app.get("/schedules")
def get_schedules() -> dict:
    return {"schedules": list_schedules()}


@app.post("/jobs/run-schedules")
def run_schedules(x_job_token: str | None = Header(default=None)) -> dict:
    if JOB_RUN_TOKEN and x_job_token != JOB_RUN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid job token.")
    return run_due_schedules(output_dir=OUTPUT_DIR)
