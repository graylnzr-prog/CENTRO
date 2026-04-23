from pathlib import Path

from app.emailer import EmailRequest, build_report_email_body, send_report_email
from app.reports import (
    build_report_from_csv,
    build_report_from_orders,
    save_report_snapshot,
)
from app.scheduler import get_due_schedules, mark_schedule_run
from app.shopify import ShopifyCredentials, fetch_shopify_orders


def run_due_schedules(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    schedules = get_due_schedules()
    results = []

    for schedule in schedules:
        try:
            report = generate_scheduled_report(schedule)
            save_report_snapshot(report, output_dir)
            email_request = EmailRequest(
                recipient=schedule["email"],
                subject=f"{report['headline']} report is ready",
                body=build_report_email_body(report),
            )
            delivery = send_report_email(email_request)
            mark_schedule_run(schedule["id"], schedule["frequency"])
            results.append(
                {
                    "schedule_id": schedule["id"],
                    "status": "sent",
                    "provider": delivery.get("provider", delivery["status"]),
                }
            )
        except Exception as exc:
            results.append(
                {
                    "schedule_id": schedule["id"],
                    "status": "failed",
                    "error": str(exc),
                }
            )

    return {
        "processed": len(schedules),
        "results": results,
    }


def generate_scheduled_report(schedule: dict) -> dict:
    source_type = schedule["source_type"]
    if source_type == "csv":
        csv_path = schedule.get("csv_path")
        if not csv_path:
            raise ValueError("Scheduled CSV report is missing its source file path.")

        path = Path(csv_path)
        if not path.exists():
            raise ValueError(f"Scheduled CSV source not found: {csv_path}")

        return build_report_from_csv(path, source_label=schedule["source_label"])

    if source_type == "shopify":
        store_url = schedule.get("shopify_store_url")
        api_key = schedule.get("shopify_api_key")
        if not store_url or not api_key:
            raise ValueError("Scheduled Shopify report is missing store credentials.")

        orders = fetch_shopify_orders(
            ShopifyCredentials(store_url=store_url, api_key=api_key),
            period=schedule["frequency"],
        )
        return build_report_from_orders(orders, source_label=schedule["source_label"])

    raise ValueError(f"Unsupported schedule source type: {source_type}")
