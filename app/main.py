import json
import os
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

from app.emailer import EmailRequest, build_report_email_body, send_report_email
from app.jobs import run_due_schedules
from app.reports import (
    build_report_from_csv,
    build_report_from_orders,
    save_report_snapshot,
)
from app.scheduler import ScheduleRequest, create_schedule, list_schedules
from app.shopify import (
    ShopifyCredentials,
    consume_oauth_state,
    exchange_code_for_token,
    fetch_shopify_orders,
    generate_oauth_state,
    get_install_url,
    get_shop_connection,
    normalize_shop_domain,
    store_oauth_state,
    store_shop_connection,
    validate_oauth_hmac,
)


app = FastAPI(title="Sales Dashboard")
JOB_RUN_TOKEN = os.getenv("JOB_RUN_TOKEN")
APP_ADMIN_TOKEN = os.getenv("APP_ADMIN_TOKEN")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("APP_DATA_DIR") or str(BASE_DIR)).resolve()
STATIC_DIR = BASE_DIR / "static"
OUTPUT_DIR = DATA_DIR / "output" / "reports"
DATABASE_DIR = DATA_DIR / "database"
DATABASE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def require_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    if not APP_ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="APP_ADMIN_TOKEN is not configured.")
    if x_admin_token != APP_ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin token.")


def resolve_reports_csv_path(csv_path: str) -> Path:
    candidate = Path(csv_path)
    resolved = candidate.resolve() if candidate.is_absolute() else (BASE_DIR / candidate).resolve()
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


@app.post("/reports/csv")
async def generate_csv_report(
    file: UploadFile = File(...),
    _: None = Depends(require_admin_token),
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
    return {"source": "csv", "report": report}


@app.post("/reports/shopify")
def generate_shopify_report(
    store_url: str = Form(...),
    period: str = Form(default="weekly"),
    _: None = Depends(require_admin_token),
) -> dict:
    connection = get_shop_connection(store_url)
    if not connection:
        raise HTTPException(status_code=400, detail="Shopify store is not connected yet. Use Shopify login first.")

    credentials = ShopifyCredentials(store_url=store_url, access_token=connection["access_token"])
    orders = fetch_shopify_orders(credentials, period=period)
    if not orders:
        raise HTTPException(status_code=400, detail="Shopify store returned no orders for that period.")

    try:
        report = build_report_from_orders(orders, source_label=store_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    save_report_snapshot(report, OUTPUT_DIR)
    return {"source": "shopify", "report": report}


@app.post("/email/send")
def email_report(request: EmailRequest, _: None = Depends(require_admin_token)) -> dict:
    try:
        result = send_report_email(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@app.post("/email/send-report")
def email_generated_report(
    recipient: str = Form(...),
    report_payload: str = Form(...),
    _: None = Depends(require_admin_token),
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
def schedule_report(request: ScheduleRequest, _: None = Depends(require_admin_token)) -> dict:
    payload = request.model_copy(deep=True)
    if payload.csv_path:
        payload.csv_path = str(resolve_reports_csv_path(payload.csv_path))
    schedule_id = create_schedule(payload)
    return {"status": "scheduled", "schedule_id": schedule_id}


@app.get("/schedules")
def get_schedules(_: None = Depends(require_admin_token)) -> dict:
    return {"schedules": list_schedules()}


@app.post("/auth/shopify/start")
def start_shopify_auth(
    response: Response,
    shop: str = Form(...),
    _: None = Depends(require_admin_token),
) -> dict:
    try:
        state = generate_oauth_state()
        install_url = get_install_url(shop, state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    store_oauth_state(state)
    response.set_cookie(
        key="shopify_oauth_state",
        value=state,
        httponly=True,
        samesite="lax",
        secure=os.getenv("APP_BASE_URL", "").startswith("https://"),
        max_age=600,
    )
    return {"install_url": install_url}


@app.get("/auth/shopify/callback")
def shopify_auth_callback(request: Request) -> RedirectResponse:
    params = {key: value for key, value in request.query_params.items()}
    if not validate_oauth_hmac(params):
        raise HTTPException(status_code=400, detail="Invalid Shopify OAuth signature.")

    expected_state = request.cookies.get("shopify_oauth_state")
    returned_state = params.get("state")
    if not expected_state or expected_state != returned_state:
        raise HTTPException(status_code=400, detail="Invalid Shopify OAuth state.")
    if not consume_oauth_state(returned_state):
        raise HTTPException(status_code=400, detail="Shopify OAuth state has expired or was not issued by this app.")

    try:
        shop = normalize_shop_domain(params.get("shop", ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    code = params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Shopify OAuth callback is missing the authorization code.")

    try:
        token_payload = exchange_code_for_token(shop, code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    store_shop_connection(shop, token_payload["access_token"], token_payload.get("scope", ""))

    response = RedirectResponse(url=f"/?shopify=connected&shop={shop}", status_code=302)
    response.delete_cookie("shopify_oauth_state")
    return response


@app.post("/jobs/run-schedules")
def run_schedules(x_job_token: str | None = Header(default=None)) -> dict:
    if JOB_RUN_TOKEN and x_job_token != JOB_RUN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid job token.")
    return run_due_schedules(output_dir=OUTPUT_DIR)
