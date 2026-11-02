// Network Ops Insights UI: chat with a trace panel, and an observability page.
// Plain JavaScript, no build step. All model output is inserted with textContent (never innerHTML).

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
};

async function api(path, options = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
  return body;
}

// ---------------------------------------------------------------- identity
async function loadWho() {
  try {
    const who = await api("/api/whoami");
    const box = $("#who");
    box.textContent = "";
    box.append(`${who.user} · ${who.role} · `);
    box.append(el("span", "badge", who.agent.split(".").pop()));
  } catch (err) {
    $("#who").textContent = `Not connected: ${err.message}`;
  }
}

// ---------------------------------------------------------------- tabs
document.querySelectorAll(".tab").forEach((btn) =>
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b === btn));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("active", p.id === `tab-${btn.dataset.tab}`));
    if (btn.dataset.tab === "obs") loadObservability();
  })
);

// ---------------------------------------------------------------- chat
function addMessage(kind, text, meta) {
  const msg = el("div", `msg ${kind}`, text);
  if (meta) msg.append(el("span", "meta", meta));
  $("#messages").append(msg);
  msg.scrollIntoView({ behavior: "smooth", block: "end" });
  return msg;
}

function renderTrace(result) {
  const parts = [`${(result.latency_ms / 1000).toFixed(1)} s`];
  if (result.tools && result.tools.length) parts.push(`tools: ${result.tools.join(", ")}`);
  if (result.usage) parts.push(`usage: ${JSON.stringify(result.usage)}`);
  $("#trace-summary").textContent = parts.join(" · ");

  const list = $("#trace-steps");
  list.textContent = "";
  (result.steps || []).forEach((step) => {
    const li = el("li");
    if (step.kind === "thinking") {
      li.append(el("div", "step-kind", "Planning"), el("pre", null, step.text));
    } else if (step.kind === "tool_use") {
      li.append(el("div", "step-kind", "Tool call"), el("div", "step-title", step.tool));
      if (step.sql) li.append(el("pre", null, step.sql));
      else if (step.query) li.append(el("pre", null, `search: ${step.query}`));
      else if (step.input) li.append(el("pre", null, step.input));
    } else if (step.kind === "tool_result") {
      li.append(el("div", "step-kind", `Result${step.status ? " · " + step.status : ""}`), el("div", "step-title", step.tool));
      if (step.sql) li.append(el("pre", null, step.sql));
      if (step.content) li.append(el("pre", null, step.content));
    }
    list.append(li);
  });
}

async function ask(question) {
  addMessage("user", question);
  const pending = addMessage("agent", "Thinking…");
  $("#send").disabled = true;
  try {
    const result = await api("/api/chat", { method: "POST", body: JSON.stringify({ question }) });
    pending.textContent = result.answer || "(no answer)";
    pending.append(el("span", "meta", `${result.agent.split(".").pop()} · ${(result.latency_ms / 1000).toFixed(1)} s`));
    renderTrace(result);
  } catch (err) {
    pending.textContent = err.message;
    pending.classList.add("error");
  } finally {
    $("#send").disabled = false;
  }
}

$("#ask").addEventListener("submit", (e) => {
  e.preventDefault();
  const q = $("#question").value.trim();
  if (!q) return;
  $("#question").value = "";
  document.querySelector(".hint")?.remove();
  ask(q);
});
document.querySelectorAll(".suggest").forEach((b) => b.addEventListener("click", () => {
  document.querySelector(".hint")?.remove();
  ask(b.textContent);
}));

// ---------------------------------------------------------------- observability
function fillTable(table, columns, rows, onClick) {
  table.textContent = "";
  const head = el("tr");
  columns.forEach(([label]) => head.append(el("th", null, label)));
  table.append(head);
  if (!rows.length) {
    const tr = el("tr");
    const td = el("td", "muted", "No data yet");
    td.colSpan = columns.length;
    tr.append(td);
    table.append(tr);
    return;
  }
  rows.forEach((row) => {
    const tr = el("tr", onClick ? "clickable" : null);
    columns.forEach(([, render]) => {
      const value = render(row);
      const td = el("td");
      if (value instanceof Node) td.append(value); else td.textContent = value ?? "";
      tr.append(td);
    });
    if (onClick) tr.addEventListener("click", () => onClick(row));
    table.append(tr);
  });
}

function renderCostChart(costRows) {
  const byDay = {};
  costRows.forEach((r) => {
    const day = String(r.USAGE_DATE).slice(0, 10);
    byDay[day] = byDay[day] || { agent: 0, search: 0, warehouse: 0 };
    byDay[day][r.COST_CATEGORY] = (byDay[day][r.COST_CATEGORY] || 0) + Number(r.CREDITS || 0);
  });
  const days = Object.keys(byDay).sort();
  const max = Math.max(0.0001, ...days.map((d) => byDay[d].agent + byDay[d].search + byDay[d].warehouse));
  const chart = $("#cost-chart");
  chart.textContent = "";
  days.forEach((day) => {
    const bar = el("div", "bar");
    const total = byDay[day].agent + byDay[day].search + byDay[day].warehouse;
    bar.title = `${day}: ${total.toFixed(3)} credits`;
    ["agent", "search", "warehouse"].forEach((cat) => {
      const seg = el("div", `seg ${cat}`);
      seg.style.height = `${(byDay[day][cat] / max) * 100}%`;
      bar.append(seg);
    });
    bar.append(el("div", "bar-label", day.slice(5)));
    chart.append(bar);
  });
  return days.reduce((sum, d) => sum + byDay[d].agent + byDay[d].search + byDay[d].warehouse, 0);
}

async function showRequest(row) {
  try {
    const detail = await api(`/api/requests/${row.REQUEST_ID}`);
    document.querySelector('.tab[data-tab="chat"]').click();
    addMessage("user", detail.question);
    addMessage("agent", detail.answer || "(no answer)", `${detail.user} · ${detail.role} · from history`);
    renderTrace(detail);
  } catch (err) {
    alertBox(err.message);
  }
}

function alertBox(message) {
  const box = $("#obs-error");
  box.textContent = message;
  box.hidden = false;
}

async function loadObservability() {
  $("#obs-error").hidden = true;
  try {
    const data = await api("/api/observability");
    $("#obs").hidden = false;
    const latest = data.eval_runs[0];
    $("#k-eval").textContent = latest ? `${latest.FULLY_CORRECT}/${latest.QUESTIONS}` : "–";
    const today = data.agent_daily[0];
    $("#k-cpr").textContent = today && today.CREDITS_PER_REQUEST != null ? Number(today.CREDITS_PER_REQUEST).toFixed(4) : "–";
    $("#k-req").textContent = data.agent_daily.reduce((s, r) => s + Number(r.REQUESTS || 0), 0);
    $("#k-credits").textContent = renderCostChart(data.cost_daily).toFixed(3);

    fillTable($("#t-evals"), [
      ["When", (r) => String(r.RUN_AT).slice(0, 16)],
      ["Agent", (r) => String(r.AGENT_NAME).split(".").pop()],
      ["Correct", (r) => el("span", r.FULLY_CORRECT === r.QUESTIONS ? "ok" : "bad", `${r.FULLY_CORRECT}/${r.QUESTIONS}`)],
      ["Avg s", (r) => r.AVG_LATENCY_S],
    ], data.eval_runs);

    fillTable($("#t-requests"), [
      ["When", (r) => String(r.REQUESTED_AT).slice(0, 16)],
      ["Role", (r) => r.ROLE_NAME],
      ["Question", (r) => String(r.QUESTION || "").slice(0, 60)],
      ["ms", (r) => (r.ERROR ? el("span", "bad", "error") : r.LATENCY_MS)],
    ], data.recent_requests, showRequest);
  } catch (err) {
    $("#obs").hidden = true;
    alertBox(err.message);
  }
}

loadWho();
