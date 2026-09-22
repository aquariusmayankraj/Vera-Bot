// Synthetic examples for UI testing, authored for this package. Not real businesses.
export const BUSINESSES = Object.freeze({
  restaurants: {name: "Garden Table Café", owner: "Asha", label: "Restaurant", offer: "Lunch Thali @ ₹149", initials: "GC"},
  salons: {name: "Bloom Hair Studio", owner: "Riya", label: "Salon", offer: "Haircut @ ₹199", initials: "BH"},
  gyms: {name: "Everyday Fitness", owner: "Arjun", label: "Gym & fitness", offer: "Trial Session @ ₹99", initials: "EF"},
  dentists: {name: "Meera Dental Studio", owner: "Meera", label: "Dental clinic", offer: "Dental Check-up @ ₹299", initials: "MD"},
  pharmacies: {name: "Neighbourhood Pharmacy", owner: "Kiran", label: "Pharmacy", offer: "", initials: "NP"},
});
export function sessionId() {
  return globalThis.crypto?.randomUUID?.() || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 14)}`;
}
export function createScenario({category = "restaurants", kind = "perf_dip", language = "en", now = new Date()} = {}) {
  const business = BUSINESSES[category];
  if (!business) throw new Error("Choose a supported business type.");
  const id = sessionId(); const mid = `demo_m_${id}`; const tid = `demo_t_${id}`;
  const payloads = {
    perf_dip: {metric: "calls", delta_pct: -0.4, window: "7-day comparison"},
    perf_spike: {metric: "views", delta_pct: 0.28, window: "7-day comparison"},
    milestone_reached: {metric: "reviews", value_now: 105, milestone_value: 100},
    curious_ask_due: {cadence: "weekly"},
  };
  if (!payloads[kind]) throw new Error("Choose a supported trigger.");
  return {
    category: {slug: category, voice: {tone: category === "dentists" || category === "pharmacies" ? "clinical_peer" : "warm_busy_practical"}, peer_stats: {avg_ctr: 0.03}, digest: []},
    merchant: {merchant_id: mid, category_slug: category,
      identity: {name: business.name, owner_first_name: business.owner, languages: [language], verified: true},
      performance: {window_days: 30, calls: 20, views: 800, ctr: 0.025, delta_7d: {calls_pct: -0.4, views_pct: 0.28}},
      offers: business.offer ? [{id: `offer_${id}`, title: business.offer, status: "active"}] : [],
      conversation_history: []},
    trigger: {id: tid, merchant_id: mid, scope: "merchant", kind, source: "internal", urgency: 3,
      suppression_key: `demo:${id}:${kind}`, payload: payloads[kind],
      expires_at: new Date(now.getTime() + 86400000).toISOString()},
    customer: null,
  };
}
export function validateBundle(bundle) {
  if (!bundle || typeof bundle !== "object" || Array.isArray(bundle)) throw new Error("Import a JSON object with category, merchant, trigger, and optional customer.");
  for (const scope of ["category", "merchant", "trigger"]) {
    if (!bundle[scope] || typeof bundle[scope] !== "object" || Array.isArray(bundle[scope])) throw new Error(`${scope} must be an object.`);
  }
  if (!bundle.category.slug || bundle.merchant.category_slug !== bundle.category.slug) throw new Error("merchant.category_slug must match category.slug.");
  if (!bundle.trigger.kind) throw new Error("trigger.kind is required.");
  const c = bundle.customer;
  if (c != null && (typeof c !== "object" || Array.isArray(c))) throw new Error("customer must be an object or null.");
  if (bundle.trigger.scope === "customer" && !c) throw new Error("Customer-scoped triggers need customer context, including valid consent.");
  if (bundle.trigger.scope !== "customer" && c) throw new Error("Use trigger.scope = customer when supplying customer context.");
  if (c && !c.consent) throw new Error("Customer context needs purpose-specific consent. No consent is invented.");
  const bytes = new TextEncoder().encode(JSON.stringify(bundle)).length;
  if (bytes > 450 * 1024) throw new Error("Scenario is too large. Keep the complete scenario below 450 KB.");
  return bundle;
}
export function freshBundle(source) {
  validateBundle(source);
  const b = JSON.parse(JSON.stringify(source)); const id = sessionId();
  const mid = `demo_m_${id}`; const tid = `demo_t_${id}`; const cid = b.customer ? `demo_c_${id}` : null;
  b.merchant.merchant_id = mid; b.trigger.id = tid; b.trigger.merchant_id = mid;
  b.trigger.suppression_key = `demo:${id}:${b.trigger.kind}`;
  b.trigger.payload = b.trigger.payload || {};
  if ("merchant_id" in b.trigger.payload) b.trigger.payload.merchant_id = mid;
  if (cid) {
    b.customer.customer_id = cid; b.customer.merchant_id = mid; b.trigger.customer_id = cid;
    if ("customer_id" in b.trigger.payload) b.trigger.payload.customer_id = cid;
  } else {
    delete b.trigger.customer_id; delete b.trigger.payload.customer_id;
  }
  // Expiry, consent and conversation history are deliberately NOT rewritten:
  // custom scenarios can test expiry/opt-out suppression accurately.
  return b;
}
export function contextRequests(bundle, now = new Date().toISOString(), version = 1) {
  validateBundle(bundle);
  return ["category", "merchant", "customer", "trigger"].filter(scope => bundle[scope]).map(scope => ({
    scope, context_id: bundle[scope][{category: "slug", merchant: "merchant_id", customer: "customer_id", trigger: "id"}[scope]],
    // The demo category may be edited multiple times across sessions.
    version: scope === "category" ? Math.max(version, Date.now()) : version,
    payload: bundle[scope], delivered_at: now,
  }));
}
