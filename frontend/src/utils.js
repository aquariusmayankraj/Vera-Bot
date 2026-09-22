/** Shared browser/Node helpers. Never render untrusted text with innerHTML. */
export function normalizeBaseUrl(raw, pageProtocol = "http:") {
  const value = String(raw ?? "").trim();
  if (!value) throw new Error("Enter your Render backend base URL first.");
  let url;
  try { url = new URL(value); } catch { throw new Error("Enter a full URL, such as https://your-service.onrender.com."); }
  if (!["http:", "https:"].includes(url.protocol) || !url.hostname || url.username || url.password) {
    throw new Error("Use an HTTP or HTTPS URL without a username or password.");
  }
  if (url.search || url.hash || (url.pathname !== "/" && url.pathname !== "")) {
    throw new Error("Use the base URL only. Remove /v1, /demo, /docs, query parameters, and fragments.");
  }
  if (pageProtocol === "https:" && url.protocol !== "https:") {
    throw new Error("Your HTTPS website needs the HTTPS Render backend URL, not an HTTP address.");
  }
  if (url.hostname.includes("your-service") || url.hostname.includes("your-render") || url.hostname.includes("example.com")) {
    throw new Error("Replace the example address with your actual Render service URL.");
  }
  return url.origin;
}
export function initialBaseUrl(config, location, override = "") {
  if (override) return override;
  if (String(config.API_BASE_URL || "").trim()) return String(config.API_BASE_URL).trim();
  return ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname) ? "http://localhost:8080" : "";
}
export function parseJsonObject(text, label = "JSON", allowNull = false) {
  let value;
  try { value = JSON.parse(text); } catch (error) { throw new Error(`${label}: ${error.message}`); }
  if (allowNull && value === null) return null;
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} must be a JSON object${allowNull ? " or null" : ""}.`);
  return value;
}
export function formatJson(value) { return JSON.stringify(value, null, 2); }
export function endpointPath(endpoint, mode = "demo") {
  if (!["context", "tick", "reply", "healthz", "metadata"].includes(endpoint)) throw new Error("Unsupported endpoint.");
  if (!["demo", "judge"].includes(mode)) throw new Error("Unsupported API mode.");
  return `${mode === "demo" ? "/demo" : ""}/v1/${endpoint}`;
}
export function prettyError(data, status) {
  if (data && typeof data === "object") {
    let details = data.details;
    if (Array.isArray(details)) details = details.map(x => `${x.field || "field"}: ${x.message || "invalid"}`).join("; ");
    return [data.reason || data.detail || `HTTP ${status}`, typeof details === "string" ? details : ""].filter(Boolean).join(" — ");
  }
  return `HTTP ${status}. The response is not valid API JSON. Check the backend URL and Render logs.`;
}
