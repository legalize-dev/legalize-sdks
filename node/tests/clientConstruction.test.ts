/** Client construction: defaults, overrides, headers. */

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  DEFAULT_BASE_URL,
  Legalize,
  RetryPolicy,
  SDK_VERSION,
  defaultUserAgent,
} from "../src/index.js";

const saved: Record<string, string | undefined> = {};
const ENV_VARS = ["LEGALIZE_API_KEY", "LEGALIZE_BASE_URL", "LEGALIZE_API_VERSION"] as const;

beforeEach(() => {
  for (const name of ENV_VARS) {
    saved[name] = process.env[name];
    delete process.env[name];
  }
});
afterEach(() => {
  for (const name of ENV_VARS) {
    const v = saved[name];
    if (v === undefined) delete process.env[name];
    else process.env[name] = v;
  }
});

describe("construction", () => {
  it("builds with explicit apiKey", () => {
    const c = new Legalize({ apiKey: "leg_test" });
    expect(c._apiKey).toBe("leg_test");
    expect(c._baseUrl).toBe(DEFAULT_BASE_URL);
  });

  it("accepts a RetryPolicy", () => {
    const policy = new RetryPolicy({ maxRetries: 7 });
    const c = new Legalize({ apiKey: "leg_t", retry: policy });
    expect(c).toBeDefined();
  });

  it("maxRetries maps to a policy", () => {
    const c = new Legalize({ apiKey: "leg_t", maxRetries: 2 });
    expect(c).toBeDefined();
  });

  it("merges defaultHeaders", () => {
    const c = new Legalize({
      apiKey: "leg_t",
      defaultHeaders: { "X-Correlation-Id": "abc" },
    });
    expect(c._headers["X-Correlation-Id"]).toBe("abc");
  });

  it("has bound resources", () => {
    const c = new Legalize({ apiKey: "leg_t" });
    expect(c.countries).toBeDefined();
    expect(c.jurisdictions).toBeDefined();
    expect(c.lawTypes).toBeDefined();
    expect(c.laws).toBeDefined();
    expect(c.reforms).toBeDefined();
    expect(c.stats).toBeDefined();
    expect(c.webhooks).toBeDefined();
  });

  it("close() is idempotent", async () => {
    const c = new Legalize({ apiKey: "leg_t" });
    await c.close();
    await c.close();
  });

  it("supports async disposal", async () => {
    const c = new Legalize({ apiKey: "leg_t" });
    await c[Symbol.asyncDispose]();
  });

  it("SDK_VERSION matches package.json", async () => {
    const { readFileSync } = await import("node:fs");
    const { fileURLToPath } = await import("node:url");
    const { dirname, resolve } = await import("node:path");
    const here = dirname(fileURLToPath(import.meta.url));
    const pkgRaw = readFileSync(resolve(here, "..", "package.json"), "utf8");
    const pkg = JSON.parse(pkgRaw) as { version: string };
    expect(pkg.version).toBe(SDK_VERSION);
  });

  it("defaultUserAgent has the expected shape", () => {
    const ua = defaultUserAgent();
    expect(ua.startsWith(`legalize-node/${SDK_VERSION} `)).toBe(true);
    expect(ua.includes(" node/")).toBe(true);
  });

  it("lastResponse starts null", () => {
    const c = new Legalize({ apiKey: "leg_t" });
    expect(c.lastResponse).toBeNull();
  });
});
