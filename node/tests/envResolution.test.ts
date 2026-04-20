/**
 * Cross-SDK environment-variable contract (see `sdk/ENVIRONMENT.md`).
 *
 * Verifies that the Node client honors:
 *   - LEGALIZE_API_KEY
 *   - LEGALIZE_BASE_URL
 *   - LEGALIZE_API_VERSION
 *
 * Precedence: explicit arg > env var > default. Empty env = unset.
 *
 * This suite is the direct port of `python/tests/unit/test_env_resolution.py`.
 * Test names mirror the Python suite so drift is easy to detect.
 */

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  AuthenticationError,
  DEFAULT_API_VERSION,
  DEFAULT_BASE_URL,
  Legalize,
  resolveApiVersion,
  resolveBaseUrl,
} from "../src/index.js";

const ENV_VARS = ["LEGALIZE_API_KEY", "LEGALIZE_BASE_URL", "LEGALIZE_API_VERSION"] as const;

let saved: Record<string, string | undefined>;

beforeEach(() => {
  saved = {};
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

// ---- LEGALIZE_API_KEY ---------------------------------------------------

describe("TestApiKey", () => {
  it("test_missing_raises", () => {
    try {
      new Legalize();
      throw new Error("did not throw");
    } catch (err) {
      expect(err).toBeInstanceOf(AuthenticationError);
      expect((err as AuthenticationError).code).toBe("missing_api_key");
    }
  });

  it("test_empty_string_treated_as_missing", () => {
    process.env.LEGALIZE_API_KEY = "";
    try {
      new Legalize();
      throw new Error("did not throw");
    } catch (err) {
      expect(err).toBeInstanceOf(AuthenticationError);
      expect((err as AuthenticationError).code).toBe("missing_api_key");
    }
  });

  it("test_env_provides_key", () => {
    process.env.LEGALIZE_API_KEY = "leg_env_abc";
    const c = new Legalize();
    expect(c._apiKey).toBe("leg_env_abc");
  });

  it("test_explicit_arg_wins", () => {
    process.env.LEGALIZE_API_KEY = "leg_env_abc";
    const c = new Legalize({ apiKey: "leg_arg_xyz" });
    expect(c._apiKey).toBe("leg_arg_xyz");
  });

  it("test_invalid_prefix_rejected_early", () => {
    process.env.LEGALIZE_API_KEY = "sk_wrong";
    try {
      new Legalize();
      throw new Error("did not throw");
    } catch (err) {
      expect(err).toBeInstanceOf(AuthenticationError);
      expect((err as AuthenticationError).code).toBe("invalid_api_key");
    }
  });
});

// ---- LEGALIZE_BASE_URL --------------------------------------------------

describe("TestBaseUrl", () => {
  it("test_resolver_default_when_nothing_set", () => {
    expect(resolveBaseUrl(undefined)).toBe(DEFAULT_BASE_URL);
  });

  it("test_resolver_uses_env", () => {
    process.env.LEGALIZE_BASE_URL = "https://staging.legalize.dev";
    expect(resolveBaseUrl(undefined)).toBe("https://staging.legalize.dev");
  });

  it("test_resolver_explicit_wins", () => {
    process.env.LEGALIZE_BASE_URL = "https://staging.legalize.dev";
    expect(resolveBaseUrl("https://other.example")).toBe("https://other.example");
  });

  it("test_resolver_empty_env_falls_through", () => {
    process.env.LEGALIZE_BASE_URL = "";
    expect(resolveBaseUrl(undefined)).toBe(DEFAULT_BASE_URL);
  });

  it("test_client_honors_env", () => {
    process.env.LEGALIZE_API_KEY = "leg_t";
    process.env.LEGALIZE_BASE_URL = "https://staging.legalize.dev";
    const c = new Legalize();
    expect(c._baseUrl).toBe("https://staging.legalize.dev");
  });

  it("test_client_strips_trailing_slash_from_env", () => {
    process.env.LEGALIZE_API_KEY = "leg_t";
    process.env.LEGALIZE_BASE_URL = "https://staging.legalize.dev/";
    const c = new Legalize();
    expect(c._baseUrl).toBe("https://staging.legalize.dev");
  });

  it("test_client_explicit_arg_wins_over_env", () => {
    process.env.LEGALIZE_API_KEY = "leg_t";
    process.env.LEGALIZE_BASE_URL = "https://staging.legalize.dev";
    const c = new Legalize({ baseUrl: "https://explicit.example" });
    expect(c._baseUrl).toBe("https://explicit.example");
  });
});

// ---- LEGALIZE_API_VERSION ----------------------------------------------

describe("TestApiVersion", () => {
  it("test_resolver_default_when_nothing_set", () => {
    expect(resolveApiVersion(undefined)).toBe(DEFAULT_API_VERSION);
  });

  it("test_resolver_uses_env", () => {
    process.env.LEGALIZE_API_VERSION = "v2";
    expect(resolveApiVersion(undefined)).toBe("v2");
  });

  it("test_resolver_explicit_wins", () => {
    process.env.LEGALIZE_API_VERSION = "v2";
    expect(resolveApiVersion("v99")).toBe("v99");
  });

  it("test_resolver_empty_env_falls_through", () => {
    process.env.LEGALIZE_API_VERSION = "";
    expect(resolveApiVersion(undefined)).toBe(DEFAULT_API_VERSION);
  });

  it("test_client_honors_env", () => {
    process.env.LEGALIZE_API_KEY = "leg_t";
    process.env.LEGALIZE_API_VERSION = "v42";
    const c = new Legalize();
    expect(c._apiVersion).toBe("v42");
    expect(c._headers["Legalize-API-Version"]).toBe("v42");
  });

  it("test_client_explicit_arg_wins_over_env", () => {
    process.env.LEGALIZE_API_KEY = "leg_t";
    process.env.LEGALIZE_API_VERSION = "v42";
    const c = new Legalize({ apiVersion: "v1" });
    expect(c._apiVersion).toBe("v1");
  });
});

// ---- Zero-config construction ------------------------------------------

describe("TestZeroConfig", () => {
  it("test_full_env_is_enough", () => {
    process.env.LEGALIZE_API_KEY = "leg_prod_xyz";
    process.env.LEGALIZE_BASE_URL = "https://api.internal.example";
    process.env.LEGALIZE_API_VERSION = "v1";
    const c = new Legalize();
    expect(c._apiKey).toBe("leg_prod_xyz");
    expect(c._baseUrl).toBe("https://api.internal.example");
    expect(c._apiVersion).toBe("v1");
    expect(c._headers.Authorization).toBe("Bearer leg_prod_xyz");
    expect(c._headers["Legalize-API-Version"]).toBe("v1");
  });

  it("test_only_api_key_is_enough", () => {
    process.env.LEGALIZE_API_KEY = "leg_prod_xyz";
    const c = new Legalize();
    expect(c._baseUrl).toBe(DEFAULT_BASE_URL);
    expect(c._apiVersion).toBe(DEFAULT_API_VERSION);
  });
});
