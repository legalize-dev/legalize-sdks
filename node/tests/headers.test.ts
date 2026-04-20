/** Identifying headers on every request. */

import { describe, expect, it } from "vitest";

import { DEFAULT_API_VERSION, Legalize, SDK_VERSION } from "../src/index.js";
import { jsonResponse, mockFetch } from "./_helpers.js";

describe("outgoing headers", () => {
  it("User-Agent has the expected shape", async () => {
    const { fetch, calls } = mockFetch(() => jsonResponse(200, []));
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    await c.countries.list();
    const ua = calls[0]!.headers["user-agent"]!;
    expect(ua.startsWith(`legalize-node/${SDK_VERSION} `)).toBe(true);
    expect(ua.includes(" node/")).toBe(true);
  });

  it("Legalize-API-Version on every request", async () => {
    const { fetch, calls } = mockFetch(() => jsonResponse(200, []));
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    await c.countries.list();
    await c.countries.list();
    await c.countries.list();
    expect(calls.length).toBe(3);
    for (const call of calls) {
      expect(call.headers["legalize-api-version"]).toBe(DEFAULT_API_VERSION);
    }
  });

  it("Legalize-API-Version override propagates", async () => {
    const { fetch, calls } = mockFetch(() => jsonResponse(200, []));
    const c = new Legalize({
      apiKey: "leg_t",
      baseUrl: "http://t",
      apiVersion: "v2",
      fetch,
      maxRetries: 0,
    });
    await c.countries.list();
    expect(calls[0]!.headers["legalize-api-version"]).toBe("v2");
  });

  it("Authorization is Bearer <key>", async () => {
    const { fetch, calls } = mockFetch(() => jsonResponse(200, []));
    const c = new Legalize({
      apiKey: "leg_specific",
      baseUrl: "http://t",
      fetch,
      maxRetries: 0,
    });
    await c.countries.list();
    expect(calls[0]!.headers.authorization).toBe("Bearer leg_specific");
  });

  it("Accept: application/json", async () => {
    const { fetch, calls } = mockFetch(() => jsonResponse(200, []));
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    await c.countries.list();
    expect(calls[0]!.headers.accept).toBe("application/json");
  });

  it("defaultHeaders merge in", async () => {
    const { fetch, calls } = mockFetch(() => jsonResponse(200, []));
    const c = new Legalize({
      apiKey: "leg_t",
      baseUrl: "http://t",
      defaultHeaders: { "X-Correlation-Id": "abc" },
      fetch,
      maxRetries: 0,
    });
    await c.countries.list();
    expect(calls[0]!.headers["x-correlation-id"]).toBe("abc");
  });

  it("extraHeaders on a single request merge on top", async () => {
    const { fetch, calls } = mockFetch(() => jsonResponse(200, []));
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    await c.request("GET", "/api/v1/countries", { extraHeaders: { "X-Request-Tag": "one-off" } });
    expect(calls[0]!.headers["x-request-tag"]).toBe("one-off");
  });

  it("Content-Type set on JSON body", async () => {
    const { fetch, calls } = mockFetch(() => jsonResponse(200, { id: 1 }));
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    await c.webhooks.create({ url: "https://x", eventTypes: ["law.updated"] });
    expect(calls[0]!.headers["content-type"]).toBe("application/json");
  });
});
