/**
 * k6 load test script — mixed CRUD pattern against the TuneFlow service.
 * Env vars (set via k6 -e flag):
 *   SERVICE_URL   base URL of the service (default: http://localhost:8000)
 *   VUS           virtual users (default: 100)
 *   DURATION      test duration in seconds (default: 30)
 */
import http from "k6/http";
import { check, sleep } from "k6";
import { Counter, Rate, Trend } from "k6/metrics";

const BASE_URL = __ENV.SERVICE_URL || "http://localhost:8000";

// Custom metrics
const errorRate = new Rate("error_rate");
const dbErrors = new Counter("db_errors");
const orderLatency = new Trend("order_latency", true);
const userLatency = new Trend("user_latency", true);
const searchLatency = new Trend("search_latency", true);

// Seed data identifiers — populated in setup()
let USER_IDS = [];
let PRODUCT_IDS = [];
let ORDER_IDS = [];

export function setup() {
  // Fetch a sample of valid IDs for use in tests
  const userRes = http.get(`${BASE_URL}/users/sample-ids?limit=50`);
  const productRes = http.get(`${BASE_URL}/products/sample-ids?limit=50`);
  const orderRes = http.get(`${BASE_URL}/orders/sample-ids?limit=50`);

  let userIds = [];
  let productIds = [];
  let orderIds = [];

  if (userRes.status === 200) {
    try { userIds = JSON.parse(userRes.body); } catch (_) {}
  }
  if (productRes.status === 200) {
    try { productIds = JSON.parse(productRes.body); } catch (_) {}
  }
  if (orderRes.status === 200) {
    try { orderIds = JSON.parse(orderRes.body); } catch (_) {}
  }
  return { userIds, productIds, orderIds };
}

export let options = {
  vus: parseInt(__ENV.VUS || "100"),
  duration: `${parseInt(__ENV.DURATION || "30")}s`,
  thresholds: {
    http_req_duration: ["p(95)<2000", "p(99)<5000"],
    error_rate: ["rate<0.05"],
  },
  // k6's default summary export only includes avg/min/med/max/p(90)/p(95).
  // p(99) is checked in thresholds above but was never being exported, so
  // runner.py's p99_latency_ms always silently read as 0.0. Explicitly
  // request it here so the real value actually reaches the summary JSON.
  summaryTrendStats: ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)"],
};

// Realistic query terms
const SEARCH_TERMS = [
  "electronics", "wireless", "premium", "sport", "book",
  "pro", "ultra", "smart", "eco", "classic",
];

const CATEGORIES = ["electronics", "clothing", "books", "home", "sports", "food", "toys", "beauty"];

export default function (data) {
  const { userIds, productIds, orderIds } = data;

  if (userIds.length === 0 || productIds.length === 0) {
    // Fallback: just hit health if no seed data yet
    http.get(`${BASE_URL}/health`);
    sleep(0.1);
    return;
  }

  const roll = Math.random();

  if (roll < 0.40) {
    // 40% — product search (cache-sensitive, read-heavy)
    const term = SEARCH_TERMS[Math.floor(Math.random() * SEARCH_TERMS.length)];
    const cat = Math.random() < 0.5
      ? `&category=${CATEGORIES[Math.floor(Math.random() * CATEGORIES.length)]}`
      : "";
    const start = Date.now();
    const res = http.get(`${BASE_URL}/products/search?q=${term}${cat}&limit=20`);
    searchLatency.add(Date.now() - start);
    const ok = check(res, { "search 2xx": (r) => r.status >= 200 && r.status < 300 });
    errorRate.add(!ok);
    if (res.status === 500) dbErrors.add(1);

  } else if (roll < 0.65) {
    // 25% — get user (point lookup)
    const uid = userIds[Math.floor(Math.random() * userIds.length)];
    const start = Date.now();
    const res = http.get(`${BASE_URL}/users/${uid}`);
    userLatency.add(Date.now() - start);
    const ok = check(res, { "user 2xx": (r) => r.status === 200 || r.status === 404 });
    errorRate.add(!ok);
    if (res.status === 500) dbErrors.add(1);

  } else if (roll < 0.85) {
    // 20% — create order (write with batch product lookup)
    const uid = userIds[Math.floor(Math.random() * userIds.length)];
    const numItems = Math.floor(Math.random() * 3) + 1;
    const items = Array.from({ length: numItems }, () => ({
      product_id: productIds[Math.floor(Math.random() * productIds.length)],
      quantity: Math.floor(Math.random() * 3) + 1,
    }));
    const payload = JSON.stringify({ user_id: uid, items });
    const start = Date.now();
    const res = http.post(`${BASE_URL}/orders/`, payload, {
      headers: { "Content-Type": "application/json" },
    });
    orderLatency.add(Date.now() - start);
    const ok = check(res, { "order 201": (r) => r.status === 201 || r.status === 404 });
    errorRate.add(!ok);
    if (res.status === 500) dbErrors.add(1);

  } else {
    // 15% — get order (read with join)
    if (orderIds.length > 0) {
      const oid = orderIds[Math.floor(Math.random() * orderIds.length)];
      const res = http.get(`${BASE_URL}/orders/${oid}`);
      const ok = check(res, { "order get 2xx/404": (r) => r.status === 200 || r.status === 404 });
      errorRate.add(!ok);
      if (res.status === 500) dbErrors.add(1);
    } else {
      // Fallback if no orders exist yet (e.g. fresh DB before seeding)
      const uid = userIds[Math.floor(Math.random() * userIds.length)];
      const res = http.get(`${BASE_URL}/users/${uid}`);
      const ok = check(res, { "fallback 2xx": (r) => r.status < 500 });
      errorRate.add(!ok);
    }
  }

  sleep(0.05 + Math.random() * 0.1);
}
