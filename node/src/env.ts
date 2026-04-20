/**
 * Environment-variable resolution helpers.
 *
 * Contract: see `sdk/ENVIRONMENT.md`. Summary:
 *   - `LEGALIZE_API_KEY` — required (unless `apiKey` passed explicitly).
 *   - `LEGALIZE_BASE_URL` — default "https://legalize.dev".
 *   - `LEGALIZE_API_VERSION` — default "v1".
 *
 * Precedence: explicit arg > env var > default. Empty string = unset.
 * Prefix `LEGALIZE_` is mandatory; no aliases.
 */

import { AuthenticationError } from "./errors.js";

export const DEFAULT_BASE_URL = "https://legalize.dev";
export const DEFAULT_API_VERSION = "v1";
export const DEFAULT_TIMEOUT = 30_000; // ms

export const KEY_PREFIX = "leg_";

/**
 * Resolve the API key from the explicit argument or the environment.
 *
 * Raises AuthenticationError synchronously if no key is available or the
 * key prefix is unrecognized. Catching obviously-bad inputs before the
 * first network call saves operators from debugging 401s later.
 */
export function resolveApiKey(apiKey: string | undefined): string {
  let key = apiKey;
  if (key === undefined) {
    const envKey = process.env.LEGALIZE_API_KEY;
    key = envKey || undefined;
  }
  if (!key) {
    throw new AuthenticationError({
      message: "Missing API key. Pass apiKey=... or set LEGALIZE_API_KEY.",
      statusCode: 401,
      code: "missing_api_key",
    });
  }
  if (!key.startsWith(KEY_PREFIX)) {
    throw new AuthenticationError({
      message: `API key format unrecognized. Keys start with "${KEY_PREFIX}".`,
      statusCode: 401,
      code: "invalid_api_key",
    });
  }
  return key;
}

/**
 * Resolve the base URL from the explicit argument, env, or default.
 * Empty strings are treated as unset.
 */
export function resolveBaseUrl(baseUrl: string | undefined): string {
  if (baseUrl !== undefined) {
    return baseUrl;
  }
  const envUrl = process.env.LEGALIZE_BASE_URL;
  if (envUrl && envUrl.length > 0) {
    return envUrl;
  }
  return DEFAULT_BASE_URL;
}

/**
 * Resolve the API version from the explicit argument, env, or default.
 * Empty strings are treated as unset.
 */
export function resolveApiVersion(apiVersion: string | undefined): string {
  if (apiVersion !== undefined) {
    return apiVersion;
  }
  const envVer = process.env.LEGALIZE_API_VERSION;
  if (envVer && envVer.length > 0) {
    return envVer;
  }
  return DEFAULT_API_VERSION;
}
