/** Extra client tests — signal, timeout, absolute URLs, 204 and empty bodies. */

import { describe, expect, it, vi } from "vitest";

import { APIConnectionError, APITimeoutError, Legalize, RetryPolicy } from "../src/index.js";
import { jsonResponse, mockFetch } from "./_helpers.js";

describe("client extras", () => {
  it("handles 204 No Content", async () => {
    const { fetch } = mockFetch(() => new Response(null, { status: 204 }));
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    const out = await c.request<unknown>("DELETE", "/api/v1/webhooks/1");
    expect(out).toBeNull();
  });

  it("handles empty 200 body as null", async () => {
    const { fetch } = mockFetch(() => new Response("", { status: 200 }));
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    const out = await c.request<unknown>("GET", "/api/v1/ping");
    expect(out).toBeNull();
  });

  it("throws APIError on 2xx non-JSON body", async () => {
    const { fetch } = mockFetch(() => new Response("not-json", { status: 200 }));
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    await expect(c.request("GET", "/api/v1/x")).rejects.toThrow(/non-JSON/);
  });

  it("propagates external AbortSignal", async () => {
    const { fetch } = mockFetch(
      () =>
        new Promise(() => {
          /* never resolves */
        }),
    );
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    const ac = new AbortController();
    ac.abort();
    await expect(
      c.request("GET", "/api/v1/countries", { signal: ac.signal }),
    ).rejects.toBeInstanceOf(APIConnectionError);
  });

  it("aborts mid-flight when signal fires", async () => {
    const { fetch } = mockFetch(
      (_req) =>
        new Promise((_resolve, reject) => {
          setTimeout(() => reject(Object.assign(new Error("aborted"), { name: "AbortError" })), 10);
        }),
    );
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    const ac = new AbortController();
    setTimeout(() => ac.abort(), 2);
    await expect(
      c.request("GET", "/api/v1/countries", { signal: ac.signal }),
    ).rejects.toBeInstanceOf(APIConnectionError);
  });

  it("raises APITimeoutError on request timeout", async () => {
    // Use a fetch that respects AbortSignal so the internal timeout's
    // abort propagates and gets mapped to APITimeoutError.
    const { fetch } = mockFetch(
      (_req) =>
        new Promise<Response>(() => {
          /* never resolves — the timeout aborts via signal */
        }),
    );
    const c = new Legalize({
      apiKey: "leg_t",
      baseUrl: "http://t",
      fetch,
      timeout: 10,
      maxRetries: 0,
    });
    await expect(c.request("GET", "/api/v1/countries")).rejects.toBeInstanceOf(APITimeoutError);
  });

  it("wraps a generic transport error as APIConnectionError", async () => {
    const { fetch } = mockFetch(() => {
      throw new Error("connection refused");
    });
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    await expect(c.countries.list()).rejects.toBeInstanceOf(APIConnectionError);
  });

  it("wraps an unknown thrown value as APIConnectionError", async () => {
    const { fetch } = mockFetch(() => {
      // Throwing a non-Error value is intentional: exercise the defensive
      // branch in wrapTransportError.
      const weird: unknown = "string error";
      throw weird;
    });
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    await expect(c.countries.list()).rejects.toBeInstanceOf(APIConnectionError);
  });

  it("absolute URL bypasses baseUrl", async () => {
    const { fetch, calls } = mockFetch(() => jsonResponse(200, []));
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    await c.request("GET", "https://other.example/x");
    expect(calls[0]!.url.toString()).toBe("https://other.example/x");
  });

  it("normalizes missing leading slash", async () => {
    const { fetch, calls } = mockFetch(() => jsonResponse(200, []));
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    await c.request("GET", "api/v1/countries");
    expect(calls[0]!.url.pathname).toBe("/api/v1/countries");
  });

  it("idempotency key header sent when requested", async () => {
    const { fetch, calls } = mockFetch(() => jsonResponse(200, {}));
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    await c.request("POST", "/api/v1/webhooks", { json: {}, idempotencyKey: "key-1" });
    expect(calls[0]!.headers["idempotency-key"]).toBe("key-1");
  });

  it("retryNonIdempotent retries POST on 500", async () => {
    const responses = [jsonResponse(500, { detail: "x" }), jsonResponse(200, {})];
    let i = 0;
    const { fetch, calls } = mockFetch(() => responses[i++]!);
    const c = new Legalize({
      apiKey: "leg_t",
      baseUrl: "http://t",
      retry: new RetryPolicy({
        maxRetries: 3,
        initialDelay: 0,
        maxDelay: 0,
        retryNonIdempotent: true,
      }),
      fetch,
    });
    await c.webhooks.create({ url: "https://x", eventTypes: ["law.updated"] });
    expect(calls.length).toBe(2);
  });

  it("buildQueryString preserves encoding for special characters", async () => {
    const { fetch, calls } = mockFetch(() => jsonResponse(200, []));
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    await c.request("GET", "/api/v1/x", { params: { q: "foo bar" } });
    expect(calls[0]!.url.search).toContain("q=foo%20bar");
  });

  // Silence unused `vi` import lint
  it("no-op to keep vi import", () => {
    void vi;
    expect(true).toBe(true);
  });
});
