import hashlib
import hmac
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from app.emailer import EmailRequest, build_report_email_body, send_report_email
from app.jobs import run_due_schedules
from app.reports import build_report_from_csv, save_report_snapshot
from app.scheduler import ScheduleRequest, create_schedule, list_schedules


app = FastAPI(title="Sales Dashboard")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SESSION_SECRET = os.getenv("APP_SESSION_SECRET") or f"{ADMIN_USERNAME}:{ADMIN_PASSWORD}"
SESSION_COOKIE_NAME = "sales_dashboard_session"
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "28800"))

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("APP_DATA_DIR") or str(BASE_DIR)).resolve()
STATIC_DIR = BASE_DIR / "static"
OUTPUT_DIR = DATA_DIR / "output" / "reports"
DATABASE_DIR = DATA_DIR / "database"
DATABASE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def get_current_admin(request: Request) -> str | None:
    cookie_value = request.cookies.get(SESSION_COOKIE_NAME)
    if not cookie_value or not ADMIN_USERNAME or not ADMIN_PASSWORD:
        return None

    try:
        username, expires_at_raw, signature = cookie_value.split("|")
    except ValueError:
        return None

    if username != ADMIN_USERNAME:
        return None

    try:
        expires_at = int(expires_at_raw)
    except ValueError:
        return None

    payload = f"{username}|{expires_at_raw}"
    expected_signature = hmac.new(
        SESSION_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        return None

    if expires_at < int(time.time()):
        return None

    return username


def require_admin_session(request: Request) -> str:
    if not ADMIN_USERNAME or not ADMIN_PASSWORD:
        raise HTTPException(status_code=503, detail="Admin login is not configured.")

    username = get_current_admin(request)
    if not username:
        raise HTTPException(status_code=401, detail="Please sign in with your admin login.")
    return username


def build_session_value(username: str) -> str:
    expires_at = int(time.time()) + SESSION_TTL_SECONDS
    payload = f"{username}|{expires_at}"
    signature = hmac.new(
        SESSION_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}|{signature}"


def set_session_cookie(response: Response, username: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=build_session_value(username),
        httponly=True,
        samesite="lax",
        secure=os.getenv("APP_BASE_URL", "").startswith("https://"),
        max_age=SESSION_TTL_SECONDS,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


def resolve_reports_csv_path(csv_path: str) -> Path:
    candidate = Path(csv_path)
    resolved = candidate.resolve() if candidate.is_absolute() else (DATA_DIR / candidate).resolve()
    reports_root = OUTPUT_DIR.resolve()

    if reports_root != resolved and reports_root not in resolved.parents:
        raise HTTPException(status_code=400, detail="CSV schedules must use files inside output/reports.")
    if not resolved.exists():
        raise HTTPException(status_code=400, detail="The selected CSV report source could not be found.")
    return resolved


@app.get("/")
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def healthcheck() -> dict:
    return {"status": "ok"}


@app.get("/auth/status")
def auth_status(request: Request) -> dict:
    username = get_current_admin(request)
    return {"authenticated": bool(username), "username": username}


@app.post("/auth/login")
def auth_login(
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
) -> dict:
    if not ADMIN_USERNAME or not ADMIN_PASSWORD:
        raise HTTPException(status_code=503, detail="Admin login is not configured.")

    if username != ADMIN_USERNAME or password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin login.")

    set_session_cookie(response, username)
    return {"status": "authenticated", "username": username}


@app.post("/auth/logout")
def auth_logout(response: Response) -> dict:
    clear_session_cookie(response)
    return {"status": "signed_out"}


@app.post("/reports/csv")
async def generate_csv_report(
    file: UploadFile = File(...),
    _: str = Depends(require_admin_session),
) -> dict:
    safe_filename = Path(file.filename or "").name
    if not safe_filename or not safe_filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file.")

    csv_path = OUTPUT_DIR / safe_filename
    content = await file.read()
    csv_path.write_bytes(content)

    try:
        report = build_report_from_csv(csv_path, source_label=safe_filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    save_report_snapshot(report, OUTPUT_DIR)
    return {"source": "csv", "report": report, "csv_path": str(csv_path)}


@app.post("/email/send")
def email_report(request: EmailRequest, _: str = Depends(require_admin_session)) -> dict:
    try:
        result = send_report_email(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@app.post("/email/send-report")
def email_generated_report(
    recipient: str = Form(...),
    report_payload: str = Form(...),
    _: str = Depends(require_admin_session),
) -> dict:
    try:
        report = json.loads(report_payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid report payload.") from exc

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
def schedule_report(request: ScheduleRequest, _: str = Depends(require_admin_session)) -> dict:
    payload = request.model_copy(deep=True)
    if payload.csv_path:
        payload.csv_path = str(resolve_reports_csv_path(payload.csv_path))
    schedule_id = create_schedule(payload)
    return {"status": "scheduled", "schedule_id": schedule_id}


@app.get("/schedules")
def get_schedules(_: str = Depends(require_admin_session)) -> dict:
    return {"schedules": list_schedules()}


@app.post("/jobs/run-schedules")
def run_schedules(_: str = Depends(require_admin_session)) -> dict:
    return run_due_schedules(output_dir=OUTPUT_DIR)
