const state = {
  report: null,
};

const tabs = document.querySelectorAll(".tab");
const panels = document.querySelectorAll(".panel");
const toast = document.getElementById("toast");

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach((item) => item.classList.remove("active"));
    panels.forEach((panel) => panel.classList.remove("active"));
    tab.classList.add("active");
    document.querySelector(`[data-panel="${tab.dataset.tab}"]`).classList.add("active");
  });
});

document.getElementById("csv-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  const response = await fetch("/reports/csv", {
    method: "POST",
    body: formData,
  });
  await handleReportResponse(response, "CSV report generated");
});

document.getElementById("shopify-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  const response = await fetch("/reports/shopify", {
    method: "POST",
    body: formData,
  });
  await handleReportResponse(response, "Shopify report generated");
});

document.getElementById("email-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.report) {
    showToast("Generate a report before trying to email it.");
    return;
  }

  const formData = new FormData(event.currentTarget);
  formData.append("report_payload", JSON.stringify(state.report));

  const response = await fetch("/email/send-report", {
    method: "POST",
    body: formData,
  });
  const payload = await response.json();
  if (!response.ok) {
    showToast(payload.detail || "Email send failed.");
    return;
  }

  const preview = document.getElementById("email-preview");
  if (payload.preview) {
    preview.textContent = payload.preview;
    preview.classList.remove("hidden");
  } else {
    preview.classList.add("hidden");
  }

  showToast(payload.message);
});

document.getElementById("schedule-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  const payload = {
    email: formData.get("email"),
    frequency: formData.get("frequency"),
    source_type: state.report ? state.report.source_label : "manual",
  };

  const response = await fetch("/schedules", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    showToast(data.detail || "Unable to save schedule.");
    return;
  }

  showToast(`Schedule saved: ${data.schedule_id}`);
  event.currentTarget.reset();
  await loadSchedules();
});

async function handleReportResponse(response, successMessage) {
  const payload = await response.json();
  if (!response.ok) {
    showToast(payload.detail || "Something went wrong.");
    return;
  }

  state.report = payload.report;
  renderReport(payload.report);
  showToast(successMessage);
}

function renderReport(report) {
  document.getElementById("empty-state").classList.add("hidden");
  document.getElementById("report-view").classList.remove("hidden");
  document.getElementById("report-source").textContent = report.source_label;

  const metricGrid = document.getElementById("metric-grid");
  const comparison = report.comparison;
  const changePercent = comparison.change_percent === null ? "Pending" : `${comparison.change_percent}%`;
  metricGrid.innerHTML = [
    metricCard("Total sales", currency(report.metrics.total_sales)),
    metricCard("Orders", report.metrics.order_count),
    metricCard("WoW change", changePercent),
  ].join("");

  document.getElementById("comparison-text").textContent =
    `This week ${currency(comparison.current_week)} vs last week ${currency(comparison.previous_week)}`;
  document.getElementById("chart-slot").innerHTML =
    report.chart_svg || '<div class="empty-state"><p>Add a dated sales column to unlock the trend chart.</p></div>';

  const topProducts = document.getElementById("top-products");
  topProducts.innerHTML = report.top_products.length
    ? report.top_products
        .map((item) => listItem(item.product, currency(item.sales)))
        .join("")
    : listItem("Top products unavailable", "Include a product column to rank best sellers.");

  const insights = document.getElementById("insights");
  insights.innerHTML = report.insights.map((item) => listItem("Insight", item)).join("");
}

function metricCard(label, value) {
  return `<article class="metric"><span>${label}</span><strong>${value}</strong></article>`;
}

function listItem(title, text) {
  return `<article class="list-item"><span>${title}</span><strong>${text}</strong></article>`;
}

function currency(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(value || 0);
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.remove("hidden");
  window.clearTimeout(showToast.timeoutId);
  showToast.timeoutId = window.setTimeout(() => {
    toast.classList.add("hidden");
  }, 2800);
}

async function loadSchedules() {
  const response = await fetch("/schedules");
  const payload = await response.json();
  const container = document.getElementById("schedule-list");
  container.innerHTML = payload.schedules.length
    ? payload.schedules
        .map((item) => listItem(`${item.frequency} -> ${item.email}`, item.source_type))
        .join("")
    : listItem("No schedules yet", "Save a daily or weekly delivery to keep the loop going.");
}

loadSchedules();
