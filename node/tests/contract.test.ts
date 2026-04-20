/**
 * Contract test: every (method, path) in ../openapi-sdk.json has a
 * corresponding SDK method. Failing this test means someone added a spec
 * endpoint without exposing it on the client.
 */

import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { Legalize } from "../src/index.js";

interface OpenAPI {
  paths: Record<string, Record<string, unknown>>;
}

const here = dirname(fileURLToPath(import.meta.url));
const spec = JSON.parse(
  readFileSync(resolve(here, "..", "..", "openapi-sdk.json"), "utf8"),
) as OpenAPI;

/**
 * Map each (method, path) tuple to a probe that, when invoked on a
 * stub-fetching client, must land on that (method, path).
 *
 * Keys match how the spec encodes paths; we record the lowercased HTTP
 * method and the templated path literally.
 */
const EXPECTED: Array<[string, string]> = [];
for (const [path, ops] of Object.entries(spec.paths)) {
  for (const [method, op] of Object.entries(ops)) {
    if (!op) continue;
    if (!["get", "post", "patch", "delete", "put"].includes(method)) continue;
    EXPECTED.push([method.toUpperCase(), path]);
  }
}

// Contract: every (method, path) here maps to a single SDK call we
// expect a user would issue.
//
// Keys are `METHOD path` exactly as they appear in the spec. Values are
// async functions that issue the call on the client.
const PROBES: Record<string, (c: Legalize) => Promise<unknown>> = {
  "GET /api/health": () => Promise.resolve("not-exposed"), // intentionally skipped
  "GET /api/v1/countries": (c) => c.countries.list(),
  "GET /api/v1/{country}/jurisdictions": (c) => c.jurisdictions.list("es"),
  "GET /api/v1/{country}/law-types": (c) => c.lawTypes.list("es"),
  "GET /api/v1/{country}/laws": (c) => c.laws.list("es"),
  "GET /api/v1/{country}/laws/{law_id}": (c) => c.laws.retrieve("es", "x"),
  "GET /api/v1/{country}/laws/{law_id}/meta": (c) => c.laws.meta("es", "x"),
  "GET /api/v1/{country}/laws/{law_id}/commits": (c) => c.laws.commits("es", "x"),
  "GET /api/v1/{country}/laws/{law_id}/at/{sha}": (c) => c.laws.atCommit("es", "x", "abc"),
  "GET /api/v1/{country}/laws/{law_id}/reforms": (c) => c.reforms.list("es", "x"),
  "GET /api/v1/{country}/stats": (c) => c.stats.retrieve("es"),
  "POST /api/v1/webhooks": (c) =>
    c.webhooks.create({ url: "https://x", eventTypes: ["law.updated"] }),
  "GET /api/v1/webhooks": (c) => c.webhooks.list(),
  "GET /api/v1/webhooks/{endpoint_id}": (c) => c.webhooks.retrieve(1),
  "PATCH /api/v1/webhooks/{endpoint_id}": (c) => c.webhooks.update(1, { enabled: false }),
  "DELETE /api/v1/webhooks/{endpoint_id}": (c) => c.webhooks.delete(1),
  "GET /api/v1/webhooks/{endpoint_id}/deliveries": (c) => c.webhooks.deliveries(1),
  "POST /api/v1/webhooks/{endpoint_id}/deliveries/{delivery_id}/retry": (c) =>
    c.webhooks.retry(1, 2),
  "POST /api/v1/webhooks/{endpoint_id}/test": (c) => c.webhooks.test(1),
};

function templatedPath(actual: string): string {
  // Convert an actual URL path like /api/v1/es/laws/x to the templated
  // form /api/v1/{country}/laws/{law_id} for comparison. Since we don't
  // have the spec mapping at this point, we use simple substitutions
  // based on the known literals we passed in the probes.
  return actual
    .replace("/es/laws/x/at/abc", "/{country}/laws/{law_id}/at/{sha}")
    .replace("/es/laws/x/meta", "/{country}/laws/{law_id}/meta")
    .replace("/es/laws/x/commits", "/{country}/laws/{law_id}/commits")
    .replace("/es/laws/x/reforms", "/{country}/laws/{law_id}/reforms")
    .replace("/es/laws/x", "/{country}/laws/{law_id}")
    .replace("/es/jurisdictions", "/{country}/jurisdictions")
    .replace("/es/law-types", "/{country}/law-types")
    .replace("/es/laws", "/{country}/laws")
    .replace("/es/stats", "/{country}/stats")
    .replace("/webhooks/1/deliveries/2/retry", "/webhooks/{endpoint_id}/deliveries/{delivery_id}/retry")
    .replace("/webhooks/1/deliveries", "/webhooks/{endpoint_id}/deliveries")
    .replace("/webhooks/1/test", "/webhooks/{endpoint_id}/test")
    .replace("/webhooks/1", "/webhooks/{endpoint_id}");
}

describe("SDK covers every (method, path) in openapi-sdk.json", () => {
  for (const [method, path] of EXPECTED) {
    const key = `${method} ${path}`;
    // `/api/health` is a monitoring endpoint; PARITY.md calls it out as
    // intentionally not exposed on the SDK surface.
    if (path === "/api/health") {
      it.skip(`${key} (monitoring endpoint, not exposed)`, () => {
        /* no-op */
      });
      continue;
    }
    it(key, async () => {
      const probe = PROBES[key];
      expect(probe, `no probe registered for ${key}`).toBeDefined();
      let captured: { method: string; path: string } | undefined;
      const fetchImpl: typeof fetch = async (input, init) => {
        const u = new URL(
          typeof input === "string" || input instanceof URL ? String(input) : input.url,
        );
        captured = {
          method: (init?.method ?? "GET").toUpperCase(),
          path: templatedPath(u.pathname),
        };
        return new Response("{}", {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      };
      const c = new Legalize({
        apiKey: "leg_t",
        baseUrl: "http://t",
        maxRetries: 0,
        fetch: fetchImpl,
      });
      await probe!(c);
      expect(captured).toBeDefined();
      expect(captured!.method).toBe(method);
      expect(captured!.path).toBe(path);
    });
  }
});
