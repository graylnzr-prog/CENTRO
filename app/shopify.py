import hashlib
import hmac
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse

import requests


DEFAULT_API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2026-04")
SHOPIFY_CLIENT_ID = os.getenv("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET = os.getenv("SHOPIFY_CLIENT_SECRET", "")
SHOPIFY_SCOPES = os.getenv("SHOPIFY_SCOPES", "read_orders")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
DATABASE_PATH = Path(__file__).resolve().parent.parent / "database" / "db.sqlite"

ORDERS_QUERY = """
query GetRecentOrders($first: Int!) {
  orders(first: $first, reverse: true, sortKey: CREATED_AT) {
    edges {
      node {
        id
        name
        createdAt
        totalPriceSet {
          shopMoney {
            amount
            currencyCode
          }
        }
        lineItems(first: 25) {
          edges {
            node {
              name
              quantity
            }
          }
        }
      }
    }
  }
}
"""


@dataclass
class ShopifyCredentials:
    store_url: str
    access_token: str


def get_install_url(shop: str, state: str) -> str:
    normalized_shop = normalize_shop_domain(shop)
    if not SHOPIFY_CLIENT_ID or not SHOPIFY_CLIENT_SECRET:
        raise ValueError("Shopify OAuth is not configured. Set SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET.")

    params = {
        "client_id": SHOPIFY_CLIENT_ID,
        "scope": SHOPIFY_SCOPES,
        "redirect_uri": f"{APP_BASE_URL}/auth/shopify/callback",
        "state": state,
    }
    return f"https://{normalized_shop}/admin/oauth/authorize?{urlencode(params)}"


def generate_oauth_state() -> str:
    return secrets.token_urlsafe(24)


def exchange_code_for_token(shop: str, code: str) -> dict:
    normalized_shop = normalize_shop_domain(shop)
    try:
        response = requests.post(
            f"https://{normalized_shop}/admin/oauth/access_token",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            data={
                "client_id": SHOPIFY_CLIENT_ID,
                "client_secret": SHOPIFY_CLIENT_SECRET,
                "code": code,
            },
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f"Shopify token exchange failed: {exc}") from exc

    payload = response.json()
    if "access_token" not in payload:
        raise ValueError("Shopify token exchange did not return an access token.")
    return payload


def store_shop_connection(shop: str, access_token: str, scopes: str) -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    try:
        ensure_shopify_tables(connection)
        connection.execute(
            """
            INSERT INTO shopify_connections (shop_domain, access_token, scopes, installed_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(shop_domain) DO UPDATE SET
                access_token = excluded.access_token,
                scopes = excluded.scopes,
                installed_at = excluded.installed_at
            """,
            (
                normalize_shop_domain(shop),
                access_token,
                scopes,
                datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            ),
        )
        connection.commit()
    finally:
        connection.close()


def get_shop_connection(shop: str) -> dict | None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        ensure_shopify_tables(connection)
        row = connection.execute(
            """
            SELECT shop_domain, access_token, scopes, installed_at
            FROM shopify_connections
            WHERE shop_domain = ?
            """,
            (normalize_shop_domain(shop),),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def fetch_shopify_orders(
    credentials: ShopifyCredentials,
    period: str = "weekly",
) -> list[dict]:
    if not credentials.store_url or not credentials.access_token:
        return []

    domain = normalize_shop_domain(credentials.store_url)
    endpoint = f"https://{domain}/admin/api/{DEFAULT_API_VERSION}/graphql.json"

    try:
        response = requests.post(
            endpoint,
            headers={
                "Content-Type": "application/json",
                "X-Shopify-Access-Token": credentials.access_token,
            },
            json={
                "query": ORDERS_QUERY,
                "variables": {"first": 50},
            },
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f"Shopify request failed: {exc}") from exc

    payload = response.json()
    if payload.get("errors"):
        message = payload["errors"][0].get("message", "Unknown Shopify API error.")
        raise ValueError(f"Shopify API error: {message}")

    orders = payload.get("data", {}).get("orders", {}).get("edges", [])
    if not orders:
        return []

    cutoff = resolve_cutoff(period)
    normalized_orders = []
    for edge in orders:
        node = edge["node"]
        created_at = parse_shopify_datetime(node["createdAt"])
        if cutoff and created_at < cutoff:
            continue

        total_amount = float(node["totalPriceSet"]["shopMoney"]["amount"])
        items = node.get("lineItems", {}).get("edges", [])
        total_quantity = sum(max(int(item["node"].get("quantity", 0)), 0) for item in items) or 1

        if not items:
            normalized_orders.append(
                {
                    "order_id": node["id"],
                    "date": created_at.date().isoformat(),
                    "sales": round(total_amount, 2),
                    "product_title": "Order total",
                }
            )
            continue

        for item in items:
            line_item = item["node"]
            quantity = max(int(line_item.get("quantity", 0)), 0) or 1
            allocated_sales = total_amount * (quantity / total_quantity)
            normalized_orders.append(
                {
                    "order_id": node["id"],
                    "date": created_at.date().isoformat(),
                    "sales": round(allocated_sales, 2),
                    "product_title": line_item.get("name") or "Untitled product",
                }
            )

    if not normalized_orders:
        raise ValueError("No Shopify orders were returned for the selected period.")

    return normalized_orders


def validate_oauth_hmac(params: dict[str, str]) -> bool:
    received_hmac = params.get("hmac", "")
    if not received_hmac or not SHOPIFY_CLIENT_SECRET:
        return False

    filtered = {key: value for key, value in params.items() if key != "hmac"}
    message = "&".join(f"{key}={filtered[key]}" for key in sorted(filtered))
    digest = hmac.new(
        SHOPIFY_CLIENT_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(digest, received_hmac)


def ensure_shopify_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS shopify_connections (
            shop_domain TEXT PRIMARY KEY,
            access_token TEXT NOT NULL,
            scopes TEXT,
            installed_at TEXT
        )
        """
    )


def normalize_shop_domain(store_url: str) -> str:
    candidate = store_url.strip()
    if "://" not in candidate:
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    domain = parsed.netloc or parsed.path
    domain = domain.strip("/").lower()

    if not domain.endswith(".myshopify.com"):
        raise ValueError("Use a valid Shopify store domain, like acme-store.myshopify.com.")

    return domain


def resolve_cutoff(period: str) -> datetime | None:
    now = datetime.now(timezone.utc)
    if period == "daily":
        return now - timedelta(days=1)
    if period == "weekly":
        return now - timedelta(days=7)
    return None


def parse_shopify_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
