import test from "node:test";
import assert from "node:assert/strict";
import {normalizeBaseUrl, initialBaseUrl, parseJsonObject, endpointPath, prettyError} from "../frontend/src/utils.js";
import {createScenario, freshBundle, contextRequests, validateBundle, BUSINESSES} from "../frontend/src/demo.js";
import {VeraApi, ApiError} from "../frontend/src/api.js";

test("base URL is centralized and normalized",()=>{
  assert.equal(normalizeBaseUrl(" https://vera-api.onrender.com/ ","https:"),"https://vera-api.onrender.com");
  assert.equal(normalizeBaseUrl("http://localhost:8080","http:"),"http://localhost:8080");
});
for (const bad of ["", "javascript:alert(1)", "https://vera-api.onrender.com/v1", "https://vera-api.onrender.com/docs", "https://u:s@vera-api.onrender.com", "https://vera-api.onrender.com/?x=1", "https://vera-api.onrender.com/#x", "https://your-service.onrender.com"]) {
  test(`reject invalid backend URL ${bad}`,()=>assert.throws(()=>normalizeBaseUrl(bad,"https:")));
}
test("HTTPS frontend rejects HTTP backend",()=>assert.throws(()=>normalizeBaseUrl("http://localhost:8080","https:")));
test("no localhost fallback on public website",()=>assert.equal(initialBaseUrl({}, {hostname:"studio.netlify.app"}),""));
test("local fallback and configured URL precedence",()=>{
  const loc={hostname:"localhost"};
  assert.equal(initialBaseUrl({},loc),"http://localhost:8080");
  assert.equal(initialBaseUrl({API_BASE_URL:"https://a.onrender.com"},loc),"https://a.onrender.com");
  assert.equal(initialBaseUrl({API_BASE_URL:"https://a.onrender.com"},loc,"https://b.onrender.com"),"https://b.onrender.com");
});
test("JSON objects only with explicit optional-null support",()=>{
  assert.deepEqual(parseJsonObject('{"x":1}'),{x:1});
  assert.equal(parseJsonObject("null","customer",true),null);
  for (const s of ["[]","null","true","not json","42"]) assert.throws(()=>parseJsonObject(s));
});
test("all five routes separated by mode",()=>{
  for (const name of ["context","tick","reply","healthz","metadata"]) {
    assert.equal(endpointPath(name),`/demo/v1/${name}`);
    assert.equal(endpointPath(name,"judge"),`/v1/${name}`);
  }
  assert.throws(()=>endpointPath("teardown")); assert.throws(()=>endpointPath("tick","wrong"));
});
test("schema details produce useful errors",()=>assert.match(prettyError({reason:"invalid",details:[{field:"message",message:"required"}]},400),/message: required/));
for (const category of Object.keys(BUSINESSES)) {
  for (const kind of ["perf_dip","perf_spike","milestone_reached","curious_ask_due"]) {
    test(`scenario ${category}/${kind} has fresh consistent IDs and expiry`,()=>{
      const b=createScenario({category,kind,now:new Date("2026-09-22T00:00:00Z")});
      assert.equal(validateBundle(b),b); assert.equal(b.trigger.merchant_id,b.merchant.merchant_id);
      assert.equal(b.trigger.expires_at,"2026-09-23T00:00:00.000Z");
      const requests=contextRequests(b); assert.equal(requests.length,3);
      assert.deepEqual(requests.map(x=>x.scope),["category","merchant","trigger"]);
      for (const r of requests) assert.ok(Number.isInteger(r.version)&&r.version>=1);
    });
  }
}
test("new session does not mutate source or refresh custom expiry",()=>{
  const b=createScenario(); b.trigger.expires_at="2020-01-01T00:00:00Z";
  b.merchant.conversation_history=[{role:"merchant",message:"STOP"}];
  const original=JSON.stringify(b); const c=freshBundle(b);
  assert.equal(JSON.stringify(b),original); assert.notEqual(c.merchant.merchant_id,b.merchant.merchant_id);
  assert.equal(c.trigger.expires_at,b.trigger.expires_at); assert.deepEqual(c.merchant.conversation_history,b.merchant.conversation_history);
});
test("customer references change together but consent is preserved",()=>{
  const b=createScenario(); b.trigger.scope="customer"; b.trigger.kind="recall_due";
  b.customer={customer_id:"c",merchant_id:b.merchant.merchant_id,consent:{scope:["recall_reminders"],opted_in_at:"2025-01-01"}};
  b.trigger.payload.customer_id="c"; b.trigger.payload.merchant_id=b.merchant.merchant_id;
  const fresh=freshBundle(b); assert.equal(fresh.customer.customer_id,fresh.trigger.customer_id);
  assert.equal(fresh.customer.customer_id,fresh.trigger.payload.customer_id);
  assert.equal(fresh.customer.merchant_id,fresh.merchant.merchant_id);
  assert.equal(fresh.trigger.payload.merchant_id,fresh.merchant.merchant_id);
  assert.deepEqual(fresh.customer.consent,b.customer.consent);
  assert.equal(contextRequests(fresh).length,4);
});
test("customer consent and scope are not invented",()=>{
  const b=createScenario(); b.trigger.scope="customer"; assert.throws(()=>validateBundle(b));
  b.customer={}; assert.throws(()=>validateBundle(b));
  b.customer.consent={scope:[]}; assert.equal(validateBundle(b),b); // backend validates scope-specific consent.
  b.trigger.scope="merchant"; assert.throws(()=>validateBundle(b));
});
test("oversized custom input rejected",()=>{const b=createScenario(); b.merchant.extra="a".repeat(451*1024); assert.throws(()=>validateBundle(b));});
test("mismatched category rejected",()=>{const b=createScenario(); b.merchant.category_slug="wrong"; assert.throws(()=>validateBundle(b));});

test("API adds bearer only to POST and excludes it from request logs",async t=>{
  const calls=[]; const logs=[];
  t.mock.method(globalThis,"fetch",async(url,options)=>{calls.push({url,options});return new Response('{"accepted":true}',{status:200});});
  const api=new VeraApi({baseUrl:"https://vera-api.onrender.com",onRequest:x=>logs.push(x)});
  api.configure(api.baseUrl,"super-private"); await api.request("context",{body:{x:1}}); await api.request("metadata",{mode:"judge"});
  assert.equal(calls[0].url,"https://vera-api.onrender.com/demo/v1/context");
  assert.equal(calls[0].options.headers.Authorization,"Bearer super-private");
  assert.equal(calls[1].options.headers.Authorization,undefined);
  assert.equal(calls[0].options.credentials,"omit"); assert.equal(calls[0].options.redirect,"error");
  assert.ok(!JSON.stringify(logs).includes("super-private"));
});
test("API exposes 401 rather than fake chat",async t=>{
  t.mock.method(globalThis,"fetch",async()=>new Response('{"reason":"unauthorized"}',{status:401}));
  await assert.rejects(new VeraApi({baseUrl:"https://vera-api.onrender.com"}).request("reply",{body:{}}),e=>e instanceof ApiError&&e.status===401);
});
test("non JSON successful response is rejected",async t=>{
  t.mock.method(globalThis,"fetch",async()=>new Response("<html>Wrong host</html>",{status:200}));
  await assert.rejects(new VeraApi({baseUrl:"https://vera-api.onrender.com"}).request("context",{body:{}}),e=>e.uncertain&&/non-JSON/.test(e.message));
});
test("POST is not automatically retried after lost response",async t=>{
  let calls=0;t.mock.method(globalThis,"fetch",async()=>{calls++;throw new TypeError("Network");});
  await assert.rejects(new VeraApi({baseUrl:"https://vera-api.onrender.com"}).request("reply",{body:{turn_number:1}}),e=>e.uncertain===true);
  assert.equal(calls,1);
});
test("timeout marks an ambiguous write",async t=>{
  t.mock.method(globalThis,"fetch",async(url,{signal})=>new Promise((resolve,reject)=>signal.addEventListener("abort",()=>reject(new Error("aborted")),{once:true})));
  await assert.rejects(new VeraApi({baseUrl:"https://vera-api.onrender.com",requestTimeout:5}).request("reply",{body:{}}),e=>e.uncertain&&/timed out/.test(e.message));
});
