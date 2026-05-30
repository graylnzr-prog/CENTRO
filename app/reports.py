import json
from datetime import datetime
from pathlib import Path

import pandas as pd


COLUMN_ALIASES = {
    "date": ["date", "day", "created_at", "ordered_at"],
    "sales": [
        "sales",
        "total sales",
        "total_sales",
        "amount",
        "revenue",
        "total_price",
        "payout",
        "payouts",
        "total released amount",
        "total_released_amount",
        "net payout",
        "net_payout",
        "settlement amount",
        "settlement_amount",
    ],
    "product": ["product", "product_title", "title", "item_name", "name"],
}


def build_report_from_csv(csv_path: Path, source_label: str) -> dict:
    dataframe = pd.read_csv(csv_path)
    return build_report_from_dataframe(dataframe, source_label=source_label)


def build_report_from_orders(orders: list[dict], source_label: str) -> dict:
    dataframe = pd.DataFrame(orders)
    return build_report_from_dataframe(dataframe, source_label=source_label)


def build_report_from_dataframe(dataframe: pd.DataFrame, source_label: str) -> dict:
    normalized = normalize_dataframe(dataframe.copy())
    if "sales" not in normalized.columns:
        raise ValueError(
            "A sales column is required. Try sales, total sales, payouts, net payout, or settlement amount."
        )

    normalized["sales"] = parse_amount_series(normalized["sales"])

    if "date" in normalized.columns:
        normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
        normalized = normalized.dropna(subset=["date"]).sort_values("date")

    total_sales = float(normalized["sales"].sum())
    order_count = int(len(normalized))
    average_order_value = float(total_sales / order_count) if order_count else 0.0

    daily_sales = build_daily_sales(normalized)
    weekly_sales = build_weekly_sales(normalized)
    comparison = build_week_comparison(weekly_sales)
    top_products = build_top_products(normalized)
    chart_svg = build_chart_svg(daily_sales or weekly_sales)

    return {
        "source_label": source_label,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "headline": "Weekly" if daily_sales else "Sales",
        "metrics": {
            "total_sales": round(total_sales, 2),
            "order_count": order_count,
            "average_order_value": round(average_order_value, 2),
        },
        "daily_sales": daily_sales,
        "weekly_sales": weekly_sales,
        "comparison": comparison,
        "top_products": top_products,
        "chart_svg": chart_svg,
        "insights": build_insights(total_sales, comparison, top_products),
    }


def normalize_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    dataframe.columns = [str(column).strip().lower() for column in dataframe.columns]

    rename_map = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in dataframe.columns:
                rename_map[alias] = canonical
                break

    return dataframe.rename(columns=rename_map)


def parse_amount_series(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.strip()
        .str.replace(r"^\((.*)\)$", r"-\1", regex=True)
        .str.replace(r"[$,]", "", regex=True)
    )
    return pd.to_numeric(cleaned, errors="coerce").fillna(0.0)


def build_daily_sales(dataframe: pd.DataFrame) -> list[dict]:
    if "date" not in dataframe.columns or dataframe.empty:
        return []

    grouped = dataframe.groupby(dataframe["date"].dt.date)["sales"].sum().tail(14)
    return [
        {"label": day.isoformat(), "value": round(float(value), 2)}
        for day, value in grouped.items()
    ]


def build_weekly_sales(dataframe: pd.DataFrame) -> list[dict]:
    if "date" not in dataframe.columns or dataframe.empty:
        return []

    weekly_periods = dataframe["date"].dt.to_period("W-MON")
    grouped = dataframe.groupby(weekly_periods)["sales"].sum().tail(8)
    return [
        {
            "label": str(period.start_time.date()),
            "value": round(float(value), 2),
        }
        for period, value in grouped.items()
    ]


def build_week_comparison(weekly_sales: list[dict]) -> dict:
    if len(weekly_sales) < 2:
        current_value = weekly_sales[-1]["value"] if weekly_sales else 0.0
        return {
            "current_week": current_value,
            "previous_week": 0.0,
            "change": current_value,
            "change_percent": None,
        }

    current_week = weekly_sales[-1]["value"]
    previous_week = weekly_sales[-2]["value"]
    change = round(current_week - previous_week, 2)
    if previous_week == 0:
        change_percent = None
    else:
        change_percent = round((change / previous_week) * 100, 1)

    return {
        "current_week": current_week,
        "previous_week": previous_week,
        "change": change,
        "change_percent": change_percent,
    }


def build_top_products(dataframe: pd.DataFrame) -> list[dict]:
    if "product" not in dataframe.columns:
        return []

    grouped = (
        dataframe.groupby("product", dropna=False)["sales"]
        .sum()
        .sort_values(ascending=False)
        .head(5)
    )
    return [
        {"product": str(name), "sales": round(float(value), 2)}
        for name, value in grouped.items()
    ]


def build_chart_svg(points: list[dict]) -> str:
    if not points:
        return ""

    width = 640
    height = 240
    padding = 28
    values = [max(float(point["value"]), 0.0) for point in points]
    max_value = max(values) if values else 1.0
    step = (width - (padding * 2)) / max(len(points) - 1, 1)

    coordinates = []
    for index, value in enumerate(values):
        x = padding + (index * step)
        y = height - padding - ((value / max_value) * (height - padding * 2)) if max_value else height / 2
        coordinates.append((round(x, 1), round(y, 1)))

    polyline = " ".join(f"{x},{y}" for x, y in coordinates)
    circles = "".join(
        f'<circle cx="{x}" cy="{y}" r="4" fill="#ff6b35" />'
        for x, y in coordinates
    )
    labels = "".join(
        f'<text x="{x}" y="{height - 8}" text-anchor="middle" font-size="11" fill="#57606a">{point["label"][5:]}</text>'
        for point, (x, _) in zip(points, coordinates)
    )
    grid = "".join(
        f'<line x1="{padding}" y1="{y}" x2="{width - padding}" y2="{y}" stroke="#d8dee4" stroke-dasharray="3 6" />'
        for y in (padding, height / 2, height - padding)
    )

    return (
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Sales trend chart">'
        '<rect width="100%" height="100%" rx="24" fill="#fffaf5" />'
        f"{grid}"
        f'<polyline fill="none" stroke="#0f172a" stroke-width="4" points="{polyline}" />'
        f"{circles}"
        f"{labels}"
        "</svg>"
    )


def build_insights(total_sales: float, comparison: dict, top_products: list[dict]) -> list[str]:
    insights = [f"Total captured sales reached ${total_sales:,.2f} in this report window."]

    change_percent = comparison.get("change_percent")
    if change_percent is None:
        insights.append("Week-over-week movement will get sharper once two full weeks of dated data are available.")
    elif change_percent >= 0:
        insights.append(f"Sales are up {change_percent:.1f}% versus the prior week.")
    else:
        insights.append(f"Sales are down {abs(change_percent):.1f}% versus the prior week.")

    if top_products:
        insights.append(f"Top product right now: {top_products[0]['product']} at ${top_products[0]['sales']:,.2f}.")

    return insights


def save_report_snapshot(report: dict, output_dir: Path) -> Path:
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    slug = slugify(report["source_label"])
    destination = output_dir / f"{timestamp}-{slug}-report.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return destination


def slugify(value: str) -> str:
    cleaned = "".join(character.lower() if character.isalnum() else "-" for character in value)
    collapsed = "-".join(part for part in cleaned.split("-") if part)
    return collapsed[:50] or "report"
