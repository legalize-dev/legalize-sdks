/**
 * Regression: `lastResponse` is populated on success AND error paths, so
 * callers can inspect rate-limit headers and X-Request-Id after a 4xx/5xx.
 */

import { describe, expect, it } from "vitest";

import {
  Legalize,
  NotFoundError,
  RateLimitError,
  RetryPolicy,
} from "../src/index.js";
import { jsonResponse, mockFetch } from "./_helpers.js";

describe("lastResponse", () => {
  it("populated on 404", async () => {
    const { fetch } = mockFetch(() =>
      jsonResponse(
        404,
        { detail: "not found" },
        { "x-request-id": "req_abc", "x-ratelimit-remaining": "9" },
      ),
    );
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    await expect(c.countries.list()).rejects.toBeInstanceOf(NotFoundError);
    expect(c.lastResponse).not.toBeNull();
    expect(c.lastResponse!.status).toBe(404);
    expect(c.lastResponse!.headers.get("x-request-id")).toBe("req_abc");
    expect(c.lastResponse!.headers.get("x-ratelimit-remaining")).toBe("9");
  });

  it("populated on exhausted 429", async () => {
    const { fetch } = mockFetch(() =>
      jsonResponse(
        429,
        { detail: { error: "quota_exceeded" } },
        { "retry-after": "0", "x-ratelimit-remaining": "0" },
      ),
    );
    const c = new Legalize({
      apiKey: "leg_t",
      baseUrl: "http://t",
      retry: new RetryPolicy({ maxRetries: 1, initialDelay: 0, maxDelay: 0 }),
      fetch,
    });
    // No fake timers — maxDelay=0 means no sleep is needed.
    const err = await c.countries.list().catch((e) => e);
    expect(err).toBeInstanceOf(RateLimitError);
    expect(c.lastResponse).not.toBeNull();
    expect(c.lastResponse!.status).toBe(429);
    expect(c.lastResponse!.headers.get("x-ratelimit-remaining")).toBe("0");
  });

  it("populated on 2xx", async () => {
    const { fetch } = mockFetch(() => jsonResponse(200, [], { "x-ratelimit-remaining": "100" }));
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    await c.countries.list();
    expect(c.lastResponse).not.toBeNull();
    expect(c.lastResponse!.headers.get("x-ratelimit-remaining")).toBe("100");
  });
});

