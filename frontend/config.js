/**
 * CHANGE THE BACKEND URL HERE — this is the only deployment URL in the frontend.
 * Example: API_BASE_URL: "https://your-service.onrender.com"
 * Use the base URL only. Do NOT append /v1, /demo, /docs or /healthz.
 *
 * Blank on localhost => http://localhost:8080.
 * Blank on Netlify => the interface opens with a Connect backend prompt.
 * All values in this file are PUBLIC. NEVER add an API key/password here.
 */
window.VERA_CONFIG = Object.freeze({
  API_BASE_URL: "",
  APP_NAME: "Vera Studio",
  REQUEST_TIMEOUT_MS: 30000,
  HEALTH_TIMEOUT_MS: 90000,
});
