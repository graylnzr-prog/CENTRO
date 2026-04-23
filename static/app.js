const state = {
  report: null,
  source: null,
  csvPath: null,
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
  const file = formData.get("file");
  state.csvPath = file && file.name ? `output/reports/${file.name}` : null;
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

document.getElementById("shopify-login-button").addEventListener("click", () => {
  const storeInput = document.querySelector('#shopify-form input[name="store_url"]');
  const shop = storeInput.value.trim();
  if (!shop) {
    showToast("Enter your Shopify store URL first.");
    return;
  }

  window.location.href = `/auth/shopify/start?shop=${encodeURIComponent(shop)}`;
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
  if (!state.report || !state.source) {
    showToast("Generate a report before saving a schedule.");
    return;
  }

  const formData = new FormData(event.currentTarget);
  const payload = {
    email: formData.get("email"),
    frequency: formData.get("frequency"),
    source_type: state.source,
    source_label: state.report.source_label,
  };

  if (state.source === "csv") {
    payload.csv_path = state.csvPath;
  }

  if (state.source === "shopify") {
    const shopifyData = new FormData(document.getElementById("shopify-form"));
    payload.shopify_store_url = shopifyData.get("store_url");
  }

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

document.getElementById("job-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  const token = formData.get("job_token");

  const response = await fetch("/jobs/run-schedules", {
    method: "POST",
    headers: {
      "X-Job-Token": token,
    },
  });
  const payload = await response.json();
  if (!response.ok) {
    showToast(payload.detail || "Unable to run schedules.");
    return;
  }

  renderJobResult(payload);
  await loadSchedules();
  showToast(`Processed ${payload.processed} due schedule(s).`);
});

async function handleReportResponse(response, successMessage) {
  const payload = await response.json();
  if (!response.ok) {
    showToast(payload.detail || "Something went wrong.");
    return;
  }

  state.report = payload.report;
  state.source = payload.source;
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

function renderJobResult(payload) {
  const container = document.getElementById("job-result");
  container.classList.remove("hidden");

  if (!payload.results.length) {
    container.innerHTML = listItem("No due schedules", "Nothing was ready to send right now.");
    return;
  }

  container.innerHTML = payload.results
    .map((item) => {
      if (item.status === "sent") {
        return listItem(`Schedule ${item.schedule_id}`, `Sent via ${item.provider}`);
      }
      return listItem(`Schedule ${item.schedule_id}`, `Failed: ${item.error}`);
    })
    .join("");
}

async function loadSchedules() {
  const response = await fetch("/schedules");
  const payload = await response.json();
  const container = document.getElementById("schedule-list");
  container.innerHTML = payload.schedules.length
    ? payload.schedules
        .map((item) => {
          const nextRun = item.next_run_at ? `next ${formatDateTime(item.next_run_at)}` : "pending";
          return listItem(`${item.frequency} -> ${item.email}`, `${item.source_type} - ${nextRun}`);
        })
        .join("")
    : listItem("No schedules yet", "Save a daily or weekly delivery to keep the loop going.");
}

function formatDateTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

loadSchedules();
hydrateShopifyConnectionState();

function hydrateShopifyConnectionState() {
  const params = new URLSearchParams(window.location.search);
  if (params.get("shopify") === "connected" && params.get("shop")) {
    const shop = params.get("shop");
    const storeInput = document.querySelector('#shopify-form input[name="store_url"]');
    if (storeInput) {
      storeInput.value = shop;
    }
    showToast(`Shopify connected for ${shop}`);
    window.history.replaceState({}, "", window.location.pathname);
  }
}
