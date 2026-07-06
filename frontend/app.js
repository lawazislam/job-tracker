/* Job Application Tracker frontend.
   Plain JS, no frameworks. Talks to the FastAPI backend at /api/*. */

const API = "/api";
const STATUSES = ["saved", "applied", "screening", "interview", "offer", "rejected", "withdrawn", "ghosted"];

const state = { apps: [], filter: null, search: "" };

const $ = (sel) => document.querySelector(sel);

/* ---------- API helpers ---------- */

async function api(path, options = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data.detail === "string"
      ? data.detail
      : (data.detail?.[0]?.msg || "Request failed");
    throw new Error(detail);
  }
  return data;
}

/* ---------- Rendering ---------- */

function statusColor(s) {
  return getComputedStyle(document.documentElement).getPropertyValue(`--st-${s}`).trim();
}

function fmtDate(d) {
  return d ? d : "–";
}

function render() {
  const tbody = $("#apps-body");
  tbody.innerHTML = "";
  const visible = state.apps.filter((a) => {
    if (state.filter && a.status !== state.filter) return false;
    if (state.search && !a.company.toLowerCase().includes(state.search)) return false;
    return true;
  });

  $("#empty-state").hidden = visible.length > 0;

  for (const app of visible) {
    const tr = document.createElement("tr");

    const cells = [
      ["Company", `<span class="cell-company">${esc(app.company)}</span>`],
      ["Role", `<span class="cell-role">${esc(app.role)}</span>`],
      ["Status", statusSelectHTML(app)],
      ["Applied", `<span class="cell-date">${fmtDate(app.date_applied)}</span>`],
      ["Follow-up", `<span class="cell-date">${fmtDate(app.follow_up_date)}</span>`],
      ["Resume", `<span class="cell-date">${esc(app.resume_version || "–")}</span>`],
      ["Source", `<span class="cell-date">${esc(app.source || "–")}</span>`],
      ["", `<button class="btn-delete" data-del="${app.id}" title="Delete" aria-label="Delete application at ${esc(app.company)}">✕</button>`],
    ];
    tr.innerHTML = cells
      .map(([label, html]) => `<td${label ? ` data-label="${label}"` : ""}>${html}</td>`)
      .join("");
    tbody.appendChild(tr);
  }
}

function statusSelectHTML(app) {
  const color = statusColor(app.status);
  const opts = STATUSES.map(
    (s) => `<option value="${s}" ${s === app.status ? "selected" : ""}>${s}</option>`
  ).join("");
  return `<select class="status-select" data-id="${app.id}"
            style="color:${color}; border-color:${color}">${opts}</select>`;
}

function renderStats(stats) {
  const el = $("#stats");
  const parts = [`<div class="stat"><div class="stat__n">${stats.total}</div><div class="stat__label">total</div></div>`];
  for (const s of STATUSES) {
    const n = stats.by_status[s];
    if (n) {
      parts.push(`<div class="stat"><div class="stat__n" style="color:${statusColor(s)}">${n}</div><div class="stat__label">${s}</div></div>`);
    }
  }
  el.innerHTML = parts.join("");
}

function renderFilterPills() {
  const el = $("#status-filters");
  const present = new Set(state.apps.map((a) => a.status));
  const pills = [`<button class="pill ${state.filter === null ? "is-active" : ""}" data-filter="">all</button>`];
  for (const s of STATUSES) {
    if (present.has(s)) {
      pills.push(`<button class="pill ${state.filter === s ? "is-active" : ""}" data-filter="${s}">${s}</button>`);
    }
  }
  el.innerHTML = pills.join("");
}

function esc(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

/* ---------- Data loading ---------- */

async function refresh() {
  const [apps, stats] = await Promise.all([api("/applications"), api("/stats")]);
  state.apps = apps;
  render();
  renderStats(stats);
  renderFilterPills();
}

/* ---------- Toast ---------- */

let toastTimer;
function toast(msg, isError = false) {
  const el = $("#toast");
  el.textContent = msg;
  el.className = "toast" + (isError ? " toast--error" : "");
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), 4200);
}

/* ---------- Events ---------- */

$("#btn-toggle-form").addEventListener("click", () => {
  const form = $("#add-form");
  form.hidden = !form.hidden;
  if (!form.hidden) form.querySelector("input[name=company]").focus();
});

$("#btn-cancel").addEventListener("click", () => {
  $("#add-form").hidden = true;
  $("#add-form").reset();
});

$("#add-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const data = Object.fromEntries(new FormData(form).entries());
  for (const k of Object.keys(data)) if (data[k] === "") data[k] = null;

  try {
    await api("/applications", { method: "POST", body: JSON.stringify(data) });
    form.reset();
    form.hidden = true;
    toast(`Saved: ${data.company} – ${data.role}`);
    await refresh();
  } catch (err) {
    toast(err.message, true);
  }
});

document.addEventListener("change", async (e) => {
  if (e.target.matches(".status-select")) {
    const id = e.target.dataset.id;
    try {
      await api(`/applications/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: e.target.value }),
      });
      toast(`Status updated to ${e.target.value}`);
      await refresh();
    } catch (err) {
      toast(err.message, true);
      await refresh();
    }
  }
});

document.addEventListener("click", async (e) => {
  if (e.target.matches("[data-del]")) {
    const id = e.target.dataset.del;
    const app = state.apps.find((a) => String(a.id) === id);
    if (!confirm(`Delete the application for ${app.role} at ${app.company}? This also removes its history.`)) return;
    try {
      await api(`/applications/${id}`, { method: "DELETE" });
      toast("Application deleted");
      await refresh();
    } catch (err) {
      toast(err.message, true);
    }
  }
  if (e.target.matches("[data-filter]") || e.target.closest("[data-filter]")) {
    const btn = e.target.closest("[data-filter]");
    state.filter = btn.dataset.filter || null;
    render();
    renderFilterPills();
  }
});

$("#search").addEventListener("input", (e) => {
  state.search = e.target.value.trim().toLowerCase();
  render();
});

/* ---------- Init ---------- */

refresh().catch((err) => toast("Could not load applications: " + err.message, true));
