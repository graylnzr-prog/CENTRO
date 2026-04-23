import os
import smtplib
from email.message import EmailMessage

import requests
from pydantic import BaseModel, EmailStr


class EmailRequest(BaseModel):
    recipient: EmailStr
    subject: str
    body: str


def build_report_email_body(report: dict) -> str:
    metrics = report["metrics"]
    comparison = report["comparison"]
    top_products = report["top_products"]

    lines = [
        f"{report['headline']} sales report",
        "",
        f"Source: {report['source_label']}",
        f"Generated: {report['generated_at']}",
        "",
        f"Total sales: ${metrics['total_sales']:,.2f}",
        f"Orders: {metrics['order_count']}",
        f"Average order value: ${metrics['average_order_value']:,.2f}",
        "",
        f"This week: ${comparison['current_week']:,.2f}",
        f"Last week: ${comparison['previous_week']:,.2f}",
    ]

    if comparison["change_percent"] is None:
        lines.append("Week-over-week change: not enough history yet")
    else:
        lines.append(f"Week-over-week change: {comparison['change_percent']:.1f}%")

    if top_products:
        lines.extend(["", "Top products:"])
        lines.extend(
            f"- {item['product']}: ${item['sales']:,.2f}"
            for item in top_products
        )

    if report["insights"]:
        lines.extend(["", "Highlights:"])
        lines.extend(f"- {insight}" for insight in report["insights"])

    return "\n".join(lines)


def send_report_email(request: EmailRequest) -> dict:
    resend_api_key = os.getenv("RESEND_API_KEY")
    resend_from = os.getenv("RESEND_FROM") or os.getenv("SMTP_FROM")
    if resend_api_key and resend_from:
        return send_via_resend(
            api_key=resend_api_key,
            sender=resend_from,
            request=request,
        )

    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM", smtp_user or "noreply@example.com")

    if not all([smtp_host, smtp_port, smtp_user, smtp_password]):
        return {
            "status": "preview",
            "message": "SMTP settings missing; returning preview body for MVP setup.",
            "preview": request.body,
        }

    message = EmailMessage()
    message["From"] = sender
    message["To"] = request.recipient
    message["Subject"] = request.subject
    message.set_content(request.body)

    with smtplib.SMTP(smtp_host, int(smtp_port), timeout=15) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(message)

    return {
        "status": "sent",
        "message": f"Email sent to {request.recipient}",
    }


def send_via_resend(api_key: str, sender: str, request: EmailRequest) -> dict:
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "from": sender,
            "to": [request.recipient],
            "subject": request.subject,
            "text": request.body,
        },
        timeout=20,
    )

    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if not response.ok:
        message = payload.get("message") or f"Resend request failed with status {response.status_code}."
        raise ValueError(message)

    return {
        "status": "sent",
        "message": f"Email sent to {request.recipient}",
        "provider": "resend",
        "email_id": payload.get("id"),
    }
