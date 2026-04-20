/**
 * Retry policy — unit tests for the policy itself, end-to-end integration
 * via the mock fetch, and the `Retry-After` parser (integer + HTTP-date).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  APIError,
  APITimeoutError,
  Legalize,
  RETRY_STATUSES,
  RateLimitError,
  RetryPolicy,
  parseRetryAfter,
} from "../src/index.js";
import { jsonResponse, mockFetch } from "./_helpers.js";

describe("parseRetryAfter", () => {
  it("integer seconds", () => {
    expect(parseRetryAfter("30")).toBe(30);
  });
  it("zero", () => {
    expect(parseRetryAfter("0")).toBe(0);
  });
  it("negative clamps to zero", () => {
    expect(parseRetryAfter("-5")).toBe(0);
  });
  it("null/undefined", () => {
    expect(parseRetryAfter(null)).toBeUndefined();
    expect(parseRetryAfter(undefined)).toBeUndefined();
  });
  it("empty string", () => {
    expect(parseRetryAfter("")).toBeUndefined();
  });
  it("junk", () => {
    expect(parseRetryAfter("later please")).toBeUndefined();
  });
  it("HTTP-date in the future", () => {
    const futureMs = Date.now() + 60_000;
    const header = new Date(futureMs).toUTCString();
    const parsed = parseRetryAfter(header)!;
    expect(parsed).toBeGreaterThan(55);
    expect(parsed).toBeLessThan(65);
  });
  it("HTTP-date in the past clamps to zero", () => {
    const pastMs = Date.now() - 600_000;
    const header = new Date(pastMs).toUTCString();
    expect(parseRetryAfter(header)).toBe(0);
  });
});

describe("RetryPolicy.shouldRetry", () => {
  it.each([429, 500, 502, 503, 504])("retries %d", (status) => {
    const p = new RetryPolicy({ maxRetries: 3 });
    expect(p.shouldRetry(0, { status, method: "GET" })).toBe(true);
  });

  it.each([400, 401, 403, 404, 409, 422])("does not retry %d", (status) => {
    const p = new RetryPolicy({ maxRetries: 3 });
    expect(p.shouldRetry(0, { status, method: "GET" })).toBe(false);
  });

  it("retries transport errors (status undefined)", () => {
    const p = new RetryPolicy({ maxRetries: 3 });
    expect(p.shouldRetry(0, { method: "GET" })).toBe(true);
  });

  it("stops at maxRetries", () => {
    const p = new RetryPolicy({ maxRetries: 2 });
    expect(p.shouldRetry(0, { status: 500, method: "GET" })).toBe(true);
    expect(p.shouldRetry(1, { status: 500, method: "GET" })).toBe(true);
    expect(p.shouldRetry(2, { status: 500, method: "GET" })).toBe(false);
  });

  it("POST not retried on 5xx by default", () => {
    const p = new RetryPolicy({ maxRetries: 3 });
    expect(p.shouldRetry(0, { status: 500, method: "POST" })).toBe(false);
    expect(p.shouldRetry(0, { status: 503, method: "PATCH" })).toBe(false);
  });

  it("POST retries on transport error regardless", () => {
    const p = new RetryPolicy({ maxRetries: 3 });
    expect(p.shouldRetry(0, { method: "POST" })).toBe(true);
  });

  it("retryNonIdempotent opts POST/PATCH into retries", () => {
    const p = new RetryPolicy({ maxRetries: 3, retryNonIdempotent: true });
    expect(p.shouldRetry(0, { status: 500, method: "POST" })).toBe(true);
    expect(p.shouldRetry(0, { status: 500, method: "PATCH" })).toBe(true);
  });

  it("RETRY_STATUSES constant is unchanged", () => {
    expect([...RETRY_STATUSES].sort()).toEqual([429, 500, 502, 503, 504]);
  });
});

describe("RetryPolicy.computeDelay", () => {
  let mathRandomSpy: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    // Default: jitter picks the MAX (we pass 0..capped, we take capped).
    mathRandomSpy = vi.spyOn(Math, "random").mockReturnValue(0.999999);
  });
  afterEach(() => {
    mathRandomSpy.mockRestore();
  });

  it("Retry-After wins", () => {
    const p = new RetryPolicy({ maxDelay: 60 });
    expect(p.computeDelay(0, { retryAfter: 10 })).toBe(10);
  });

  it("Retry-After capped by maxDelay", () => {
    const p = new RetryPolicy({ maxDelay: 5 });
    expect(p.computeDelay(0, { retryAfter: 999 })).toBe(5);
  });

  it("exponential backoff without Retry-After", () => {
    const p = new RetryPolicy({ initialDelay: 1, backoffFactor: 2, maxDelay: 100 });
    // With Math.random = 0.999...: delay ≈ capped
    expect(p.computeDelay(0, {})).toBeCloseTo(1, 2);
    expect(p.computeDelay(1, {})).toBeCloseTo(2, 2);
    expect(p.computeDelay(2, {})).toBeCloseTo(4, 2);
  });

  it("backoff capped by maxDelay", () => {
    const p = new RetryPolicy({ initialDelay: 10, backoffFactor: 10, maxDelay: 5 });
    expect(p.computeDelay(5, {})).toBeCloseTo(5, 2);
  });

  it("jitter stays within bounds", () => {
    mathRandomSpy.mockRestore();
    const p = new RetryPolicy({ initialDelay: 1, backoffFactor: 2, maxDelay: 100 });
    for (let attempt = 0; attempt < 5; attempt++) {
      for (let i = 0; i < 50; i++) {
        const d = p.computeDelay(attempt, {});
        expect(d).toBeGreaterThanOrEqual(0);
        expect(d).toBeLessThanOrEqual(Math.min(100, Math.pow(2, attempt)));
      }
    }
  });
});

// ---- end-to-end retry behavior ----------------------------------------

describe("integration: retry loop", () => {
  it("retries on 500 then succeeds", async () => {
    const responses = [
      jsonResponse(500, { detail: "err" }),
      jsonResponse(500, { detail: "err" }),
      jsonResponse(200, []),
    ];
    let i = 0;
    const { fetch, calls } = mockFetch(() => responses[i++]!);
    const c = new Legalize({
      apiKey: "leg_t",
      baseUrl: "http://t",
      retry: new RetryPolicy({ maxRetries: 3, initialDelay: 0, maxDelay: 0 }),
      fetch,
    });
    const out = await c.countries.list();
    expect(out).toEqual([]);
    expect(calls.length).toBe(3);
  });

  it("gives up after maxRetries", async () => {
    const { fetch, calls } = mockFetch(() => jsonResponse(500, { detail: "nope" }));
    const c = new Legalize({
      apiKey: "leg_t",
      baseUrl: "http://t",
      retry: new RetryPolicy({ maxRetries: 2, initialDelay: 0, maxDelay: 0 }),
      fetch,
    });
    await expect(c.countries.list()).rejects.toBeInstanceOf(APIError);
    expect(calls.length).toBe(3);
  });

  it("does not retry 404", async () => {
    let count = 0;
    const { fetch } = mockFetch(() => {
      count++;
      return jsonResponse(404, { detail: "not found" });
    });
    const c = new Legalize({
      apiKey: "leg_t",
      baseUrl: "http://t",
      retry: new RetryPolicy({ maxRetries: 3, initialDelay: 0, maxDelay: 0 }),
      fetch,
    });
    await expect(c.countries.list()).rejects.toBeInstanceOf(APIError);
    expect(count).toBe(1);
  });

  it("429 respects Retry-After header", async () => {
    const responses = [
      new Response(JSON.stringify({ detail: "too many" }), {
        status: 429,
        headers: { "content-type": "application/json", "retry-after": "2" },
      }),
      jsonResponse(200, []),
    ];
    let i = 0;
    const { fetch, calls } = mockFetch(() => responses[i++]!);
    const c = new Legalize({
      apiKey: "leg_t",
      baseUrl: "http://t",
      retry: new RetryPolicy({ maxRetries: 3, initialDelay: 0, maxDelay: 60 }),
      fetch,
    });
    // Patch setTimeout via the sleep helper: we can't easily spy sleep
    // import; instead we use vitest fake timers.
    vi.useFakeTimers();
    const promise = c.countries.list();
    // Run timers to completion — the retry sleep is ~2s.
    await vi.runAllTimersAsync();
    await promise;
    vi.useRealTimers();
    expect(calls.length).toBe(2);
  });

  it("server Retry-After capped at maxDelay", async () => {
    const responses = [
      new Response("", {
        status: 429,
        headers: { "retry-after": "36000" },
      }),
      jsonResponse(200, []),
    ];
    let i = 0;
    const { fetch, calls } = mockFetch(() => responses[i++]!);
    const c = new Legalize({
      apiKey: "leg_t",
      baseUrl: "http://t",
      retry: new RetryPolicy({ maxRetries: 3, initialDelay: 0, maxDelay: 5 }),
      fetch,
    });
    vi.useFakeTimers();
    const promise = c.countries.list();
    await vi.runAllTimersAsync();
    await promise;
    vi.useRealTimers();
    expect(calls.length).toBe(2);
  });

  it("transport error retries then raises timeout", async () => {
    let count = 0;
    const { fetch } = mockFetch(() => {
      count++;
      const e = new Error("timed out");
      e.name = "AbortError";
      throw e;
    });
    const c = new Legalize({
      apiKey: "leg_t",
      baseUrl: "http://t",
      retry: new RetryPolicy({ maxRetries: 1, initialDelay: 0, maxDelay: 0 }),
      fetch,
    });
    await expect(c.countries.list()).rejects.toBeInstanceOf(APITimeoutError);
    expect(count).toBe(2);
  });

  it("raised error is RateLimitError with retryAfter", async () => {
    const { fetch } = mockFetch(() =>
      jsonResponse(429, {
        detail: { error: "rate", message: "slow", retry_after: 42 },
      }),
    );
    const c = new Legalize({
      apiKey: "leg_t",
      baseUrl: "http://t",
      maxRetries: 0,
      fetch,
    });
    const err = await c.countries.list().catch((e) => e);
    expect(err).toBeInstanceOf(RateLimitError);
    expect((err as unknown as Record<string, unknown>).retryAfter).toBe(42);
  });

  it("POST is NOT retried on 500 by default", async () => {
    let count = 0;
    const { fetch } = mockFetch(() => {
      count++;
      return jsonResponse(500, { detail: "boom" });
    });
    const c = new Legalize({
      apiKey: "leg_t",
      baseUrl: "http://t",
      retry: new RetryPolicy({ maxRetries: 3, initialDelay: 0, maxDelay: 0 }),
      fetch,
    });
    await expect(
      c.webhooks.create({
        url: "https://example.test/hook",
        eventTypes: ["law.updated"],
      }),
    ).rejects.toBeInstanceOf(APIError);
    expect(count).toBe(1);
  });

  it("GET IS retried on 500", async () => {
    const responses = [jsonResponse(500, { detail: "x" }), jsonResponse(200, [])];
    let i = 0;
    const { fetch, calls } = mockFetch(() => responses[i++]!);
    const c = new Legalize({
      apiKey: "leg_t",
      baseUrl: "http://t",
      retry: new RetryPolicy({ maxRetries: 3, initialDelay: 0, maxDelay: 0 }),
      fetch,
    });
    await c.countries.list();
    expect(calls.length).toBe(2);
  });

  it("zero retries fires once", async () => {
    let count = 0;
    const { fetch } = mockFetch(() => {
      count++;
      return jsonResponse(500, { detail: "boom" });
    });
    const c = new Legalize({
      apiKey: "leg_t",
      baseUrl: "http://t",
      maxRetries: 0,
      fetch,
    });
    await expect(c.countries.list()).rejects.toBeInstanceOf(APIError);
    expect(count).toBe(1);
  });

  it("honors HTTP-date Retry-After from server", async () => {
    const futureMs = Date.now() + 2_000;
    const retryAfter = new Date(futureMs).toUTCString();
    const responses = [
      new Response("", { status: 429, headers: { "retry-after": retryAfter } }),
      jsonResponse(200, []),
    ];
    let i = 0;
    const { fetch, calls } = mockFetch(() => responses[i++]!);
    const c = new Legalize({
      apiKey: "leg_t",
      baseUrl: "http://t",
      retry: new RetryPolicy({ maxRetries: 1, initialDelay: 0, maxDelay: 30 }),
      fetch,
    });
    vi.useFakeTimers();
    const promise = c.countries.list();
    await vi.runAllTimersAsync();
    await promise;
    vi.useRealTimers();
    expect(calls.length).toBe(2);
  });
});
