const state = {
  report: null,
  source: null,
  csvPath: null,
  authenticated: false,
  username: "",
};

const toast = document.getElementById("toast");
const authForm = document.getElementById("auth-form");
const authStatus = document.getElementById("auth-status");
const logoutButton = document.getElementById("logout-button");

authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  const response = await fetch("/auth/login", {
    method: "POST",
    body: formData,
  });
  const payload = await response.json();
  if (!response.ok) {
    showToast(payload.detail || "Unable to sign in.");
    return;
  }

  state.authenticated = true;
  state.username = payload.username || String(formData.get("username") || "");
  updateAuthUi();
  showToast(`Signed in as ${state.username}.`);
  await loadSchedules();
});

logoutButton.addEventListener("click", async () => {
  await fetch("/auth/logout", {
    method: "POST",
  });
  state.authenticated = false;
  state.username = "";
  updateAuthUi();
  showToast("Signed out.");
  await loadSchedules();
});

document.getElementById("csv-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!ensureAuthenticated()) {
    return;
  }

  const formData = new FormData(event.currentTarget);
  const file = formData.get("file");
  const safeName = file && file.name ? file.name.split(/[/\\]/).pop() : null;
  state.csvPath = safeName ? `output/reports/${safeName}` : null;

  const response = await apiFetch("/reports/csv", {
    method: "POST",
    body: formData,
  });
  await handleReportResponse(response, "CSV report generated");
});

document.getElementById("email-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!ensureAuthenticated()) {
    return;
  }
  if (!state.report) {
    showToast("Generate a report before trying to email it.");
    return;
  }

  const formData = new FormData(event.currentTarget);
  formData.append("report_payload", JSON.stringify(state.report));

  const response = await apiFetch("/email/send-report", {
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
  if (!ensureAuthenticated()) {
    return;
  }
  if (!state.report || !state.source) {
    showToast("Generate a report before saving a schedule.");
    return;
  }

  const formData = new FormData(event.currentTarget);
  const payload = {
    email: formData.get("email"),
    frequency: formData.get("frequency"),
    source_type: "csv",
    source_label: state.report.source_label,
    csv_path: state.csvPath,
  };

  const response = await apiFetch("/schedules", {
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
  if (!ensureAuthenticated()) {
    return;
  }

  const response = await apiFetch("/jobs/run-schedules", {
    method: "POST",
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

async function apiFetch(url, options = {}) {
  return fetch(url, {
    credentials: "same-origin",
    ...options,
  });
}

function ensureAuthenticated() {
  if (state.authenticated) {
    return true;
  }

  showToast("Sign in with your admin login before using this action.");
  return false;
}

async function handleReportResponse(response, successMessage) {
  const payload = await response.json();
  if (!response.ok) {
    if (response.status === 401) {
      state.authenticated = false;
      state.username = "";
      updateAuthUi();
    }
    showToast(payload.detail || "Something went wrong.");
    return;
  }

  state.report = payload.report;
  state.source = payload.source;
  state.csvPath = payload.csv_path || state.csvPath;
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
  const container = document.getElementById("schedule-list");
  if (!state.authenticated) {
    container.innerHTML = listItem("Dashboard locked", "Sign in with your admin login to view and save schedules.");
    return;
  }

  const response = await apiFetch("/schedules");
  const payload = await response.json();
  if (!response.ok) {
    container.innerHTML = listItem("Schedules unavailable", payload.detail || "Private access needs attention.");
    return;
  }

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

async function refreshAuthState() {
  const response = await apiFetch("/auth/status");
  const payload = await response.json();
  state.authenticated = Boolean(payload.authenticated);
  state.username = payload.username || "";
  updateAuthUi();
  await loadSchedules();
}

function updateAuthUi() {
  authStatus.textContent = state.authenticated
    ? `Signed in as ${state.username || "admin"}`
    : "Signed out";
  authStatus.classList.toggle("muted", !state.authenticated);
}

refreshAuthState();
