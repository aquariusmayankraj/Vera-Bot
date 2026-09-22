import {VeraApi, ApiError} from "./api.js";
import {BUSINESSES, createScenario, freshBundle, validateBundle, contextRequests} from "./demo.js";
import {initialBaseUrl, normalizeBaseUrl, parseJsonObject, formatJson, endpointPath} from "./utils.js";

const $ = id => document.getElementById(id);
const all = selector => [...document.querySelectorAll(selector)];
const config = window.VERA_CONFIG || {};
const STORAGE_KEY = "vera-studio.backend-override.v2";
const getSavedUrl = () => { try { return localStorage.getItem(STORAGE_KEY) || ""; } catch { return ""; } };
const state = {busy: false, connecting: false, connected: false, logs: [], messages: [], session: null,
  bundle: null, editor: {}, scope: "category", pendingReply: null, lastRationale: null};
let connectPromise = null; let toastTimer = null;
const api = new VeraApi({baseUrl: initialBaseUrl(config, location, getSavedUrl()),
  requestTimeout: Number(config.REQUEST_TIMEOUT_MS) || 30000,
  healthTimeout: Number(config.HEALTH_TIMEOUT_MS) || 90000,
  onRequest: recordRequest});

function element(tag, className = "", text = null) {
  const el = document.createElement(tag); if (className) el.className = className;
  if (text !== null) el.textContent = String(text); return el;
}
function icon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS(svg.namespaceURI, "use"); use.setAttribute("href", `#i-${name}`);
  svg.append(use); return svg;
}
function toast(message) {
  clearTimeout(toastTimer); $("toast").textContent = message; $("toast").hidden = false;
  toastTimer = setTimeout(() => { $("toast").hidden = true; }, 4500);
}
function error(message, target = "global-error") {
  $(target).textContent = message || ""; $(target).hidden = !message;
}
function timeLabel(iso) {
  return new Date(iso).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});
}
function scrollChat() {
  const timeline = $("chat-timeline");
  requestAnimationFrame(() => { timeline.scrollTop = timeline.scrollHeight; });
}
function setBusy(busy) {
  state.busy = busy; updateControls();
}
function updateControls() {
  const locked = state.busy || state.connecting;
  for (const id of ["start-demo", "new-session", "apply-context", "send-api", "business-select", "trigger-select", "language-select", "reset-context", "import-context", "api-mode", "api-endpoint"]) {
    const el = $(id); if (el) el.disabled = locked;
  }
  $("send-api").disabled = locked;
  $("save-settings").disabled = locked;
  $("reset-settings").disabled = locked;
  const canReply = !!state.session && !state.session.ended && !locked && !state.pendingReply;
  $("message-input").disabled = !canReply;
  $("send-reply").disabled = !canReply || !$("message-input").value.trim();
  all("[data-reply]").forEach(b => { b.disabled = !canReply; });
  $("quick-replies").hidden = !state.session || state.session.ended;
  $("pending-retry").hidden = !state.pendingReply || state.busy;
  $("retry-reply").disabled = locked;
  $("export-chat").disabled = state.messages.length === 0;
  $("message-input").placeholder = state.session?.ended ? "This conversation has ended. Start a new session." : state.session ? "Reply as the merchant…" : "Start a conversation to reply…";
  if (state.session?.cid) $("message-input").placeholder = state.session.ended ? "This conversation has ended. Start a new session." : "Reply as the customer…";
  all("[data-open-settings]").forEach(b => { b.disabled = state.busy; });
}
function connectionStatus(status, detail = "") {
  state.connected = status === "online";
  const labels = {online: "Backend connected", connecting: "Connecting…", offline: "Connection needed"};
  all("[data-status-label]").forEach(el => { el.textContent = labels[status]; });
  all("[data-status-dot]").forEach(el => { el.className = `status-dot ${status}`; });
  $("connect-button-text").textContent = status === "online" ? "Connected" : status === "connecting" ? "Connecting…" : "Connect backend";
  $("connection-banner").hidden = status === "online";
  $("connection-hint").textContent = detail || "Connect your Render URL to start testing real bot responses.";
  try { $("sidebar-host").textContent = api.baseUrl ? new URL(api.baseUrl).host : "Connect your Render backend"; }
  catch { $("sidebar-host").textContent = "Check your backend URL"; }
  updateRequestUrl();
}
async function checkConnection() {
  if (connectPromise) return connectPromise;
  connectPromise = (async () => {
    normalizeBaseUrl(api.baseUrl, location.protocol);
    state.connecting = true; updateControls(); connectionStatus("connecting", "Checking your backend. A sleeping Render service can take longer to respond.");
    const wakeTimer = setTimeout(() => { $("connection-hint").textContent = "Still connecting. The backend may be waking up; check Render logs if this continues."; }, 6000);
    try {
      const health = await api.request("healthz", {mode: "judge"});
      if (health.status !== "ok" || !health.contexts_loaded) throw new ApiError("This URL does not return the expected Vera health response.");
      const metadata = await api.request("metadata", {mode: "judge"});
      if (!metadata.model) throw new ApiError("Backend metadata is missing. Use the backend included in this ZIP.");
      connectionStatus("online"); error(""); error("", "settings-error");
      return true;
    } catch (e) {
      connectionStatus("offline", e.message); throw e;
    } finally { clearTimeout(wakeTimer); state.connecting = false; updateControls(); }
  })();
  try { return await connectPromise; } finally { connectPromise = null; }
}
function openSettings() {
  if (state.busy) return;
  $("backend-url").value = api.baseUrl; $("api-token").value = api.token;
  error("", "settings-error"); $("settings-dialog").showModal();
}
function closeSettings() { $("settings-dialog").close(); }
function clearConversation() {
  state.session = null; state.pendingReply = null; state.messages = []; state.lastRationale = null;
  const timeline = $("chat-timeline"); timeline.replaceChildren(makeEmptyState());
  $("message-input").value = ""; $("chat-status").textContent = "Ready to begin";
  $("chat-status").className = "chip neutral"; $("chat-subtitle").textContent = "Merchant growth assistant";
  $("rationale-text").textContent = "After Vera responds, the engine’s decision rationale appears here. No hidden reasoning is exposed.";
  $("decision-tags").replaceChildren(); updateControls();
}
function makeEmptyState() {
  const box = element("div", "chat-empty"); box.id = "chat-empty";
  const mark = element("div", "empty-mark"); mark.append(icon("spark"));
  const title = element("h2", "", "Good conversations start with good context.");
  const button = element("button", "button button-primary", "Start demo conversation"); button.id = "start-demo";
  button.append(icon("arrow")); button.addEventListener("click", () => startSession());
  box.append(mark, element("span", "eyebrow", "LET’S MAKE IT RELEVANT"), title,
    element("p", "", "Choose a business and a trigger. Vera will prepare a message you can reply to."), button,
    element("span", "subtle-caption", "Synthetic data · Nothing is sent to real customers")); return box;
}
function scenarioOptions() {
  return {category: $("business-select").value, kind: $("trigger-select").value, language: $("language-select").value};
}
function updatePreview(bundle) {
  const m = bundle.merchant; const identity = m.identity || {}; const b = BUSINESSES[m.category_slug];
  $("merchant-name").textContent = identity.name || "Untitled merchant";
  $("merchant-category").textContent = `${b?.label || m.category_slug} · ${state.session ? "Current session" : "Sample business"}`;
  $("merchant-avatar").textContent = (identity.name || "Merchant").split(/\s+/).slice(0, 2).map(x => x[0]).join("").toUpperCase();
  $("metric-calls").textContent = m.performance?.calls ?? "—";
  $("metric-views").textContent = m.performance?.views ?? "—";
  const days = m.performance?.window_days || "unspecified";
  const metricLabels = all(".metrics span");
  metricLabels[0].textContent = `Calls / ${days} days`; metricLabels[1].textContent = `Views / ${days} days`;
  $("offer-value").textContent = (m.offers || []).find(o => o.status === "active")?.title || "No active offer supplied";
}
function setRationale(response) {
  state.lastRationale = response;
  $("rationale-text").textContent = response.rationale || "No decision rationale was included in this response.";
  const tags = $("decision-tags"); tags.replaceChildren();
  if (response.cta) tags.append(element("span", "chip neutral", `CTA: ${response.cta}`));
  if (response.send_as) tags.append(element("span", "chip neutral", response.send_as));
  if (response.action) tags.append(element("span", "chip neutral", response.action));
}
async function copy(text) {
  try { await navigator.clipboard.writeText(text); toast("Copied."); }
  catch { toast("Copy is unavailable in this browser. Select the text and copy it manually."); }
}
function appendMessage(role, text, meta = {}) {
  $("chat-empty")?.remove();
  const stamp = new Date().toISOString(); state.messages.push({role, body: text, timestamp: stamp, ...meta});
  const wrapper = element("div", `message ${role === "user" ? "user" : "bot"}`);
  const avatar = element("div", "message-avatar", role === "user" ? "Y" : "v");
  const main = element("div", "message-main"); const label = element("div", "message-label");
  label.append(element("strong", "", role === "user" ? "You" : "Vera"));
  const time = element("time", "", timeLabel(stamp)); time.dateTime = stamp; label.append(time);
  const body = element("div", "message-body", text);
  const tools = element("div", "message-tools");
  if (role !== "user") {
    const copyButton = element("button", "icon-button"); copyButton.setAttribute("aria-label", "Copy message");
    copyButton.title = "Copy message"; copyButton.append(icon("copy")); copyButton.addEventListener("click", () => copy(text));
    tools.append(copyButton);
    if (meta.template_name) tools.append(element("span", "chip neutral", "Template-shaped draft"));
  }
  main.append(label, body, tools); wrapper.append(avatar, main); $("chat-timeline").append(wrapper); scrollChat(); updateControls();
}
function appendSystem(text, isError = false) {
  $("chat-empty")?.remove();
  state.messages.push({role: "system", body: text, timestamp: new Date().toISOString()});
  $("chat-timeline").append(element("div", `system-message${isError ? " error" : ""}`, text)); scrollChat(); updateControls();
}
function showTyping(text = "Vera is preparing a response…") {
  $("typing")?.remove(); const row = element("div", "typing"); row.id = "typing";
  const dots = element("div", "dots"); for (let i = 0; i < 3; i++) dots.append(element("i"));
  row.append(dots, element("span", "", text)); $("chat-timeline").append(row); scrollChat();
}
async function startSession(custom = null) {
  if (state.busy || state.connecting) return;
  error("");
  if (!api.baseUrl) { openSettings(); return; }
  try { if (!state.connected) await checkConnection(); } catch (e) { error(e.message); openSettings(); return; }
  let bundle;
  try { bundle = freshBundle(custom || createScenario(scenarioOptions())); } catch (e) { error(e.message); return; }
  clearConversation(); setBusy(true); state.bundle = bundle;
  $("chat-empty")?.remove(); showTyping("Loading category, merchant, and trigger context…");
  $("chat-status").textContent = "Preparing"; $("chat-status").className = "chip warning";
  updatePreview(bundle);
  try {
    for (const context of contextRequests(bundle)) {
      const ack = await api.request("context", {body: context});
      if (ack.accepted !== true) throw new ApiError("The backend did not accept the context.");
    }
    showTyping("Choosing a relevant message…");
    const result = await api.request("tick", {body: {now: new Date().toISOString(), available_triggers: [bundle.trigger.id]}});
    if (!Array.isArray(result.actions)) throw new ApiError("Backend /tick did not return an actions array.");
    const action = result.actions.find(a => a.merchant_id === bundle.merchant.merchant_id);
    if (!action) {
      $("chat-status").textContent = "Suppressed"; $("chat-status").className = "chip warning";
      appendSystem("No outbound message was returned. The engine may suppress expired triggers, missing facts, absent purpose-specific consent, duplicate messages, or opted-out recipients. This is not a network error. Inspect the context in Context editor.");
      $("rationale-text").textContent = "The /tick endpoint returned no matching action. It does not return per-trigger suppression reasons; no specific reason is assumed here.";
    } else {
      if (!action.conversation_id || typeof action.body !== "string") throw new ApiError("The returned action is missing conversation_id or message body.");
      state.session = {id: action.conversation_id, mid: action.merchant_id, cid: action.customer_id || null, nextTurn: 1, ended: false};
      appendMessage("bot", action.body, action); setRationale(action);
      $("chat-status").textContent = "Conversation open"; $("chat-status").className = "chip success";
      $("chat-subtitle").textContent = `${bundle.merchant.identity?.name || "Merchant"} · Sandbox`;
      $("composer-note").textContent = state.session.cid ? "You play the customer. No booking or delivery is performed." : "You play the merchant. Vera drafts; it does not publish or book.";
    }
    loadEditor(bundle); updatePreview(bundle);
  } catch (e) {
    appendSystem(e.message + " No response is being simulated locally. Use New session after correcting the backend settings.", true);
    $("chat-status").textContent = "Request failed"; $("chat-status").className = "chip error";
    if (!e.status) connectionStatus("offline", e.message);
    error(e.status === 404 ? "Sandbox endpoints were not found. Deploy the updated backend from this ZIP and leave DEMO_ENABLED=true." : e.message);
  } finally { $("typing")?.remove(); setBusy(false); scrollChat(); if (state.session) $("message-input").focus(); }
}
async function sendReply(retry = false) {
  if (state.busy || state.connecting || !state.session || state.session.ended) return;
  const session = state.session; let pending = state.pendingReply;
  if (!retry) {
    if (pending) return;
    const message = $("message-input").value.trim(); if (!message) return;
    pending = {conversation_id: session.id, merchant_id: session.mid, customer_id: session.cid,
      from_role: session.cid ? "customer" : "merchant", message, received_at: new Date().toISOString(), turn_number: session.nextTurn};
    appendMessage("user", message); $("message-input").value = "";
  }
  if (!pending) return;
  state.pendingReply = pending; setBusy(true); error(""); showTyping();
  try {
    const result = await api.request("reply", {body: pending});
    if (!["send", "wait", "end"].includes(result.action)) throw new ApiError("Backend reply action is not recognized.", 0, result, true);
    if (result.action === "send" && typeof result.body !== "string") throw new ApiError("Backend reply has no message body.", 0, result, true);
    session.nextTurn = pending.turn_number + 1; state.pendingReply = null;
    setRationale(result);
    if (result.action === "send") {
      appendMessage("bot", result.body, result);
      $("chat-status").textContent = "Conversation open"; $("chat-status").className = "chip success";
    }
    else if (result.action === "wait") {
      appendSystem(`Conversation paused. ${result.rationale || "The engine chose not to send a message now."}${result.wait_seconds ? ` Suggested wait: ${result.wait_seconds} seconds.` : ""} No browser timer or scheduled outbound delivery has been created.`);
      $("chat-status").textContent = "Paused"; $("chat-status").className = "chip warning";
    } else {
      session.ended = true; $("chat-status").textContent = "Conversation ended"; $("chat-status").className = "chip neutral";
      appendSystem(result.rationale || "Conversation ended. No further message was sent.");
    }
  } catch (e) {
    appendSystem(e.message, true); error(e.message);
    // Keep the exact request, including timestamp and turn number, for safe retry.
    // New sessions are still available if the backend has lost its state.
    if (e.status === 409) {
      state.pendingReply = null; session.ended = true;
      $("chat-status").textContent = "Turn conflict"; $("chat-status").className = "chip error";
      appendSystem("The server rejected the turn ordering or content. Start a new session instead of silently changing a sent turn.", true);
    }
  } finally { $("typing")?.remove(); setBusy(false); scrollChat(); if (!state.pendingReply && !session.ended) $("message-input").focus(); }
}

const descriptions = {
  category: "The business vertical, its voice, and category-level benchmarks. Use real supplied facts for non-demo data.",
  merchant: "Business identity, latest metrics, active offers, and existing conversation history.",
  trigger: "The event prompting this message. Expiry and suppression rules are preserved when you test custom JSON.",
  customer: "Optional. Use null for merchant-facing messages. Customer outreach needs a customer-scoped trigger and purpose-specific consent.",
};
function loadEditor(bundle) {
  for (const scope of ["category", "merchant", "trigger", "customer"]) state.editor[scope] = formatJson(bundle[scope] ?? null);
  $("context-json").value = state.editor[state.scope]; error("", "context-error");
}
function stashEditor() { state.editor[state.scope] = $("context-json").value; }
function getEditorBundle() {
  stashEditor(); const bundle = {};
  for (const scope of ["category", "merchant", "trigger", "customer"]) bundle[scope] = parseJsonObject(state.editor[scope], scope, scope === "customer");
  return validateBundle(bundle);
}
function setScope(scope) {
  stashEditor(); state.scope = scope;
  all("[data-scope]").forEach(b => { const active = b.dataset.scope === scope; b.classList.toggle("active", active); b.setAttribute("aria-selected", String(active)); });
  $("context-json").value = state.editor[scope]; $("context-description").textContent = descriptions[scope];
}
function exportFile(data, filename) {
  const blob = new Blob([formatJson(data)], {type: "application/json;charset=utf-8"}); const url = URL.createObjectURL(blob);
  const link = element("a"); link.href = url; link.download = filename; document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function recordRequest(entry) {
  // In-memory log only; excludes all request headers and authentication tokens.
  state.logs.unshift(entry); state.logs = state.logs.slice(0, 80); renderLog();
}
function renderLog() {
  const body = $("request-history"); if (!body) return; body.replaceChildren();
  if (!state.logs.length) { const row = element("tr"); const cell = element("td", "", "No requests yet."); cell.colSpan = 5; row.append(cell); body.append(row); return; }
  for (const log of state.logs.slice(0, 30)) {
    const row = element("tr");
    for (const value of [log.method, log.path, log.status || "Network", `${log.duration} ms`, timeLabel(log.time)]) row.append(element("td", "", value));
    body.append(row);
  }
}
function updateRequestUrl() {
  const ep = $("api-endpoint").value; const mode = $("api-mode").value;
  $("request-url").textContent = api.baseUrl ? api.baseUrl.replace(/\/$/, "") + endpointPath(ep, mode) : "Set your backend URL in Settings.";
  $("api-mode-chip").textContent = mode === "demo" ? "Sandbox state" : "Challenge state";
  $("judge-warning").hidden = mode !== "judge";
}
function resetApiExample() {
  const ep = $("api-endpoint").value; const bundle = state.bundle || createScenario(scenarioOptions());
  const body = $("api-body"); body.disabled = ["healthz", "metadata"].includes(ep);
  if (body.disabled) body.value = "No body needed for this GET request.";
  else if (ep === "context") body.value = formatJson(contextRequests(bundle).find(c => c.scope === "merchant"));
  else if (ep === "tick") body.value = formatJson({now: new Date().toISOString(), available_triggers: [bundle.trigger.id]});
  else body.value = formatJson({conversation_id: state.session?.id || "START_A_DEMO_FIRST", merchant_id: state.session?.mid || bundle.merchant.merchant_id,
    customer_id: state.session?.cid || null, from_role: state.session?.cid ? "customer" : "merchant", message: "Yes, send the checklist",
    received_at: new Date().toISOString(), turn_number: state.session?.nextTurn || 1});
  updateRequestUrl();
}
function setView(name) {
  const names = {playground: "Playground", context: "Context editor", api: "API console", guide: "Setup guide"};
  if (!names[name]) name = "playground";
  all(".view").forEach(view => { view.hidden = view.id !== `view-${name}`; });
  all("[data-view]").forEach(button => { const active = button.dataset.view === name; button.classList.toggle("active", active); if (active) button.setAttribute("aria-current", "page"); else button.removeAttribute("aria-current"); });
  $("breadcrumb-view").textContent = names[name]; if (name === "api") resetApiExample();
  if (location.hash !== `#${name}`) history.replaceState(null, "", `#${name}`);
}

all("[data-open-settings]").forEach(b => b.addEventListener("click", openSettings));
$("close-settings").addEventListener("click", closeSettings);
$("settings-dialog").addEventListener("click", event => { if (event.target === $("settings-dialog")) { const r = event.target.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) closeSettings(); } });
// Never carry the previous backend's secret over to another origin.
$("backend-url").addEventListener("input", () => {
  if ($("backend-url").value.trim().replace(/\/$/, "") !== api.baseUrl) $("api-token").value = "";
});
$("settings-form").addEventListener("submit", async event => {
  event.preventDefault(); if (state.busy || state.connecting) return;
  try {
    const base = normalizeBaseUrl($("backend-url").value, location.protocol);
    const changed = base !== api.baseUrl;
    if (changed) { clearConversation(); state.logs = []; renderLog(); }
    api.configure(base, $("api-token").value); state.connected = false;
    try { localStorage.setItem(STORAGE_KEY, base); } catch { /* Private-mode storage may be unavailable. */ }
    await checkConnection(); closeSettings(); toast("Backend connected. Start a demo conversation.");
  } catch (e) { error(e.message, "settings-error"); }
});
$("reset-settings").addEventListener("click", async () => {
  if (state.busy || state.connecting) return;
  try { localStorage.removeItem(STORAGE_KEY); } catch { /* Nothing to clear. */ }
  api.baseUrl = initialBaseUrl(config, location); api.token = "";
  clearConversation(); state.logs = []; renderLog(); $("backend-url").value = api.baseUrl; $("api-token").value = "";
  connectionStatus("offline"); error("", "settings-error"); toast("Using the URL from config.js. Save & test to reconnect.");
});
all("[data-view]").forEach(b => b.addEventListener("click", () => setView(b.dataset.view)));
window.addEventListener("hashchange", () => setView(location.hash.slice(1)));
$("start-demo").addEventListener("click", () => startSession());
$("new-session").addEventListener("click", () => startSession());
$("reply-form").addEventListener("submit", event => { event.preventDefault(); sendReply(); });
$("message-input").addEventListener("input", updateControls);
$("message-input").addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); sendReply(); }
});
all("[data-reply]").forEach(b => b.addEventListener("click", () => { $("message-input").value = b.dataset.reply; sendReply(); }));
$("retry-reply").addEventListener("click", () => sendReply(true));
$("export-chat").addEventListener("click", () => exportFile({exported_at: new Date().toISOString(), session: state.session, context: state.bundle, messages: state.messages}, "vera-conversation.json"));
for (const id of ["business-select", "trigger-select", "language-select"]) $(id).addEventListener("change", () => {
  if (!state.session) { state.bundle = createScenario(scenarioOptions()); updatePreview(state.bundle); }
});
$("edit-context").addEventListener("click", () => { loadEditor(state.bundle || createScenario(scenarioOptions())); setView("context"); });
all("[data-scope]").forEach(b => b.addEventListener("click", () => setScope(b.dataset.scope)));
// Arrow-key navigation for the tablist.
all("[data-scope]").forEach((button, index, tabs) => button.addEventListener("keydown", event => {
  if (!["ArrowRight", "ArrowLeft"].includes(event.key)) return; event.preventDefault();
  const next = tabs[(index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length]; next.click(); next.focus();
}));
$("reset-context").addEventListener("click", () => { loadEditor(createScenario(scenarioOptions())); toast("Selected scenario loaded into the editor."); });
$("apply-context").addEventListener("click", async () => {
  try { const bundle = getEditorBundle(); error("", "context-error"); setView("playground"); await startSession(bundle); }
  catch (e) { error(e.message, "context-error"); }
});
$("export-context").addEventListener("click", () => {
  try { exportFile(getEditorBundle(), "vera-context.json"); error("", "context-error"); }
  catch (e) { error(e.message, "context-error"); }
});
$("import-context").addEventListener("change", async event => {
  const file = event.target.files?.[0]; if (!file) return;
  try {
    if (file.size > 450 * 1024) throw new Error("JSON file exceeds 450 KB.");
    loadEditor(validateBundle(parseJsonObject(await file.text(), "Imported scenario"))); toast("Context imported. Review it, then start a new conversation.");
  } catch (e) { error(e.message, "context-error"); }
  finally { event.target.value = ""; }
});
$("api-endpoint").addEventListener("change", resetApiExample);
$("api-mode").addEventListener("change", updateRequestUrl);
$("send-api").addEventListener("click", async () => {
  if (state.busy || state.connecting) return;
  if (!api.baseUrl) { openSettings(); return; }
  const endpoint = $("api-endpoint").value; const mode = $("api-mode").value;
  let body;
  try { if (!["healthz", "metadata"].includes(endpoint)) body = parseJsonObject($("api-body").value, "Request body"); }
  catch (e) { error(e.message); return; }
  if (mode === "judge" && body && !window.confirm("This writes to the real challenge API database. Continue?")) return;
  if (mode === "demo" && endpoint === "reply" && state.session?.id === body?.conversation_id) {
    error("This conversation is controlled by the chat composer. Send its reply in Playground to keep the turn number synchronized, or use a different conversation_id here."); return;
  }
  setBusy(true); error(""); $("response-status").textContent = "Sending…";
  const start = performance.now();
  try {
    const data = await api.request(endpoint, {mode, body});
    $("api-response").textContent = formatJson(data); $("response-status").textContent = `200 · ${Math.round(performance.now() - start)} ms`;
    $("response-status").className = "chip success";
  } catch (e) {
    $("api-response").textContent = e.data ? formatJson(e.data) : e.message;
    $("response-status").textContent = e.status || "Network error"; $("response-status").className = "chip error";
  } finally { setBusy(false); }
});
$("export-log").addEventListener("click", () => exportFile({exported_at: new Date().toISOString(), requests: state.logs}, "vera-api-log.json"));
$("clear-log").addEventListener("click", () => { state.logs = []; renderLog(); toast("This browser log was cleared. Backend data was not deleted."); });

if (config.APP_NAME) document.title = `${config.APP_NAME} · Merchant assistant`;
state.bundle = createScenario(scenarioOptions()); loadEditor(state.bundle); updatePreview(state.bundle);
setView(location.hash.slice(1) || "playground"); connectionStatus("offline"); updateControls();
if (location.protocol === "file:") error("Open this frontend through a web server, not by double-clicking index.html. Run: python3 -m http.server 5500 --directory frontend");
if (api.baseUrl && location.protocol !== "file:") checkConnection().catch(e => { error(e.message); });
