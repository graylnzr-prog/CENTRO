import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import requests


DEFAULT_API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2026-04")

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
    api_key: str


def fetch_shopify_orders(
    credentials: ShopifyCredentials,
    period: str = "weekly",
) -> list[dict]:
    if not credentials.store_url or not credentials.api_key:
        return []

    domain = normalize_shop_domain(credentials.store_url)
    endpoint = f"https://{domain}/admin/api/{DEFAULT_API_VERSION}/graphql.json"

    try:
        response = requests.post(
            endpoint,
            headers={
                "Content-Type": "application/json",
                "X-Shopify-Access-Token": credentials.api_key,
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
