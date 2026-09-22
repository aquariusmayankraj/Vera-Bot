import {endpointPath, normalizeBaseUrl, prettyError} from "./utils.js";

export class ApiError extends Error {
  constructor(message, status = 0, data = null, uncertain = false) {
    super(message); this.name = "ApiError"; this.status = status; this.data = data;
    // A write may have reached the server before a network/timeout failure.
    this.uncertain = uncertain;
  }
}
export class VeraApi {
  constructor({baseUrl = "", requestTimeout = 30000, healthTimeout = 90000, onRequest = () => {}} = {}) {
    this.baseUrl = baseUrl; this.token = ""; this.requestTimeout = requestTimeout;
    this.healthTimeout = healthTimeout; this.onRequest = onRequest;
  }
  configure(baseUrl, token = "", protocol = globalThis.location?.protocol || "http:") {
    this.baseUrl = normalizeBaseUrl(baseUrl, protocol); this.token = token.trim();
  }
  async request(endpoint, {mode = "demo", body, signal} = {}) {
    const base = normalizeBaseUrl(this.baseUrl, globalThis.location?.protocol || "http:");
    const path = endpointPath(endpoint, mode);
    const method = ["healthz", "metadata"].includes(endpoint) ? "GET" : "POST";
    const timeout = endpoint === "healthz" ? this.healthTimeout : this.requestTimeout;
    const controller = new AbortController();
    const abort = () => controller.abort();
    if (signal?.aborted) controller.abort();
    signal?.addEventListener("abort", abort, {once: true});
    const timer = setTimeout(abort, timeout);
    const start = performance.now(); let status = 0; let data = null; let errorText = "";
    const headers = {Accept: "application/json"};
    if (method === "POST") headers["Content-Type"] = "application/json";
    // Tokens are only sent to the configured backend and are never logged.
    if (this.token && method === "POST") headers.Authorization = `Bearer ${this.token}`;
    try {
      const response = await fetch(base + path, {
        method, headers, body: method === "POST" ? JSON.stringify(body ?? {}) : undefined,
        signal: controller.signal, credentials: "omit", cache: "no-store", redirect: "error",
      });
      status = response.status;
      const raw = await response.text();
      try { data = JSON.parse(raw); } catch {
        throw new ApiError("Backend returned HTML or non-JSON instead of an API response. Check the URL; a waking Render service may need another connection check.", status, null, method === "POST");
      }
      if (!response.ok) throw new ApiError(prettyError(data, status), status, data, status >= 500);
      if (!data || typeof data !== "object" || Array.isArray(data)) throw new ApiError("Unexpected API response shape.", status, data, method === "POST");
      return data;
    } catch (error) {
      let wrapped = error;
      if (!(error instanceof ApiError)) {
        const message = controller.signal.aborted
          ? "Request timed out or was cancelled. Check connection before trying again."
          : "Cannot reach backend. Check the Render URL, service status, and CORS_ORIGINS on Render.";
        wrapped = new ApiError(message, status, data, method === "POST");
      }
      errorText = wrapped.message; throw wrapped;
    } finally {
      clearTimeout(timer); signal?.removeEventListener("abort", abort);
      this.onRequest({method, path, status, duration: Math.round(performance.now() - start),
        time: new Date().toISOString(), request: body ?? null, response: data, error: errorText});
    }
  }
}
