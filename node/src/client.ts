/**
 * HTTP client core — the `Legalize` class.
 *
 * Wraps the built-in `fetch` with:
 *   - auth + identifying headers on every request
 *   - query-param cleanup matching the Python reference
 *   - retry policy with exponential backoff (see `retry.ts`)
 *   - error hierarchy mapping (see `errors.ts`)
 *   - per-request AbortSignal support
 *   - `lastResponse` populated on success AND error, for inspecting
 *     rate-limit headers and X-Request-Id after failures
 *
 * Design notes:
 *   - No runtime deps. Node 20+ ships `fetch`, `AbortController`, and
 *     `crypto.webcrypto` — we use only those.
 *   - `follow_redirects` is effectively false: the server doesn't
 *     redirect, and silently following one would hide misconfigurations.
 *     `fetch` supports "manual" redirect mode so we use it.
 */

import * as os from "node:os";

import {
  APIConnectionError,
  APIError,
  APITimeoutError,
} from "./errors.js";
import {
  DEFAULT_API_VERSION,
  DEFAULT_BASE_URL,
  DEFAULT_TIMEOUT,
  resolveApiKey,
  resolveApiVersion,
  resolveBaseUrl,
} from "./env.js";
import { RetryPolicy, parseRetryAfter, sleep } from "./retry.js";
import { Countries } from "./resources/countries.js";
import { Jurisdictions } from "./resources/jurisdictions.js";
import { Laws } from "./resources/laws.js";
import { LawTypes } from "./resources/lawTypes.js";
import { Reforms } from "./resources/reforms.js";
import { Stats } from "./resources/stats.js";
import { Webhooks } from "./resources/webhooks.js";
import { SDK_VERSION } from "./version.js";

export { DEFAULT_API_VERSION, DEFAULT_BASE_URL, DEFAULT_TIMEOUT };

/** Compose the User-Agent the SDK sends with every request. */
export function defaultUserAgent(): string {
  // Example: "legalize-node/0.1.0 node/v20.10.0 darwin"
  return `legalize-node/${SDK_VERSION} node/${process.version} ${os.platform()}`;
}

// O(n) non-regex trimmer — avoids polynomial backtracking on a
// pathological base URL, even though the input is trusted.
function stripTrailingSlashes(s: string): string {
  let end = s.length;
  while (end > 0 && s.charCodeAt(end - 1) === 47 /* "/" */) end--;
  return s.slice(0, end);
}

/** The fetch implementation the client uses. Global by default; overridable. */
export type FetchImpl = typeof fetch;

export interface LegalizeOptions {
  apiKey?: string;
  baseUrl?: string;
  apiVersion?: string;
  /** Timeout in milliseconds. Default 30000. */
  timeout?: number;
  maxRetries?: number;
  retry?: RetryPolicy;
  defaultHeaders?: Record<string, string>;
  /** Override fetch — primarily for tests. */
  fetch?: FetchImpl;
}

export interface RequestOptions {
  params?: Record<string, unknown>;
  json?: unknown;
  extraHeaders?: Record<string, string>;
  signal?: AbortSignal;
  /**
   * Override the retry policy's idempotency check for this call.
   * POST/PATCH are NOT retried by default.
   */
  idempotencyKey?: string;
}

export interface RequestRawOptions extends Omit<RequestOptions, "json"> {
  /**
   * The wire format to negotiate via the `Accept` header. `"xml"` (the
   * default) requests `application/xml`, `"json"` requests
   * `application/json`, and any other value is sent verbatim as the
   * media type (so `format: "text/xml"` works too). Empty falls back to
   * XML.
   */
  format?: string;
}

/**
 * A raw, non-JSON-decoded API response.
 *
 * Returned by {@link Legalize.requestRaw} for content negotiation — when
 * you want the body in a specific wire format (e.g. XML) instead of the
 * typed JSON model the resource methods return. The SDK has zero runtime
 * dependencies and ships no XML parser: parse `.text` (or `.content`)
 * with your own library (e.g. `fast-xml-parser`, `@xmldom/xmldom`).
 */
export interface RawResponse {
  /** HTTP status of the response. */
  statusCode: number;
  /** Raw response body as bytes. */
  content: Uint8Array;
  /** The body decoded to a string (server charset, default UTF-8). */
  text: string;
  /** The `Content-Type` header value (e.g. `application/xml; charset=utf-8`). */
  contentType: string;
  /** The response headers as a plain, lower-cased mapping. */
  headers: Record<string, string>;
  /** Parse the body as JSON (handy when `format: "json"`). */
  json(): unknown;
}

const FORMAT_ALIASES: Record<string, string> = {
  xml: "application/xml",
  json: "application/json",
};

/**
 * Map a `format` shorthand to an Accept media type.
 *
 * `"xml"` → `application/xml`, `"json"` → `application/json`. Any other
 * value is treated as an explicit media type and sent as-is (so
 * `format: "text/xml"` works too). Empty falls back to XML.
 */
export function formatToAccept(format: string | undefined): string {
  const key = (format ?? "").trim().toLowerCase();
  if (!key) return "application/xml";
  return FORMAT_ALIASES[key] ?? format!;
}

function headersToRecord(headers: Headers): Record<string, string> {
  const out: Record<string, string> = {};
  headers.forEach((value, key) => {
    out[key] = value;
  });
  return out;
}

/**
 * Synchronous-API, promise-based client for the Legalize API.
 *
 * Example:
 *
 *   import { Legalize } from "@legalize-dev/sdk";
 *
 *   const client = new Legalize({ apiKey: "leg_..." });
 *   const countries = await client.countries.list();
 *
 * Use `await using` (TS 5.2+) for deterministic cleanup:
 *
 *   await using client = new Legalize({ apiKey: "leg_..." });
 */
export class Legalize {
  readonly countries: Countries;
  readonly jurisdictions: Jurisdictions;
  readonly lawTypes: LawTypes;
  readonly laws: Laws;
  readonly reforms: Reforms;
  readonly stats: Stats;
  readonly webhooks: Webhooks;

  /** Exposed for tests; treat as private otherwise. */
  readonly _apiKey: string;
  readonly _baseUrl: string;
  readonly _apiVersion: string;
  readonly _headers: Record<string, string>;

  private readonly _timeout: number;
  private readonly _retry: RetryPolicy;
  private readonly _fetch: FetchImpl;
  private _lastResponse: Response | null = null;

  constructor(options: LegalizeOptions = {}) {
    this._apiKey = resolveApiKey(options.apiKey);
    this._baseUrl = stripTrailingSlashes(resolveBaseUrl(options.baseUrl));
    this._apiVersion = resolveApiVersion(options.apiVersion);
    this._timeout = options.timeout ?? DEFAULT_TIMEOUT;
    this._retry = resolveRetryPolicy(options.retry, options.maxRetries);
    this._fetch = options.fetch ?? globalThis.fetch;

    this._headers = buildHeaders(this._apiKey, this._apiVersion, options.defaultHeaders);

    this.countries = new Countries(this);
    this.jurisdictions = new Jurisdictions(this);
    this.lawTypes = new LawTypes(this);
    this.laws = new Laws(this);
    this.reforms = new Reforms(this);
    this.stats = new Stats(this);
    this.webhooks = new Webhooks(this);
  }

  /** The raw HTTP response from the most recent request, or null. */
  get lastResponse(): Response | null {
    return this._lastResponse;
  }

  /**
   * Execute a request and return the parsed JSON body (or null for 204).
   *
   * Throws an APIError subclass on non-2xx responses (after retries),
   * APITimeoutError on timeout, or APIConnectionError on transport
   * failure.
   */
  async request<T = unknown>(
    method: string,
    path: string,
    options: RequestOptions = {},
  ): Promise<T> {
    const upperMethod = method.toUpperCase();
    const headers = { ...this._headers };
    if (options.extraHeaders) Object.assign(headers, options.extraHeaders);
    if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;

    const hasJson = options.json !== undefined;
    if (hasJson) headers["Content-Type"] = "application/json";

    const response = await this.sendWithRetry(upperMethod, path, headers, options, hasJson);
    this._lastResponse = response;
    if (response.status === 204) return null as T;
    const text = await response.text();
    if (!text) return null as T;
    try {
      return JSON.parse(text) as T;
    } catch (err) {
      throw new APIError({
        message: "Server returned non-JSON body",
        statusCode: response.status,
        body: text,
        response,
        cause: err,
      });
    }
  }

  /**
   * Execute a request and return the raw, non-JSON-decoded body.
   *
   * The escape hatch for content negotiation: the typed resource methods
   * always return JSON models, but `requestRaw` lets you fetch any
   * endpoint in another wire format. `format` controls the `Accept`
   * header — `"xml"` (the default) requests `application/xml`, `"json"`
   * requests `application/json`, and any other value is sent verbatim as
   * the media type.
   *
   * The SDK has zero runtime deps and ships no XML parser — parse the
   * returned `.text` (or `.content`) with your own library.
   *
   * Example:
   *
   *   const res = await client.requestRaw("GET", "/api/v1/es/laws/BOE-A-1978-31229");
   *   res.contentType; // "application/xml; charset=utf-8"
   *   const xmlText = res.text; // already application/xml
   *
   * Throws the same APIError subclasses as {@link request} on a non-2xx
   * response; the error body is in whatever format you negotiated.
   */
  async requestRaw(
    method: string,
    path: string,
    options: RequestRawOptions = {},
  ): Promise<RawResponse> {
    const upperMethod = method.toUpperCase();
    const headers: Record<string, string> = { ...this._headers };
    // Override the default `Accept: application/json` with the negotiated format.
    headers["Accept"] = formatToAccept(options.format);
    if (options.extraHeaders) Object.assign(headers, options.extraHeaders);
    if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;

    const response = await this.sendWithRetry(upperMethod, path, headers, options, false);
    this._lastResponse = response;
    return rawFromResponse(response);
  }

  /** Release any resources held by the client. Kept for API symmetry. */
  async close(): Promise<void> {
    // Native fetch doesn't expose a connection pool to close; this is
    // a no-op. Declared async so callers can `await close()` without
    // rewriting if we later wire in a custom pool.
  }

  /** TS 5.2+ `using` / `await using` support. */
  async [Symbol.asyncDispose](): Promise<void> {
    await this.close();
  }

  // ---- internals --------------------------------------------------------

  private buildUrl(path: string, params?: Record<string, unknown>): string {
    let base: string;
    if (path.startsWith("http://") || path.startsWith("https://")) {
      base = path;
    } else {
      const p = path.startsWith("/") ? path : `/${path}`;
      base = this._baseUrl + p;
    }
    if (!params) return base;
    const query = buildQueryString(params);
    if (!query) return base;
    return base.includes("?") ? `${base}&${query}` : `${base}?${query}`;
  }

  /**
   * Run the retry loop and return the raw 2xx `Response`.
   *
   * Shared by {@link request} (which then JSON-parses) and
   * {@link requestRaw} (which builds a `RawResponse`). Applies the retry
   * policy on transport errors and retryable statuses, populates
   * `lastResponse` on the failing response before raising, and throws the
   * typed `APIError` hierarchy on a final non-2xx. The returned response
   * body is left unread for the caller to consume.
   */
  private async sendWithRetry(
    method: string,
    path: string,
    headers: Record<string, string>,
    options: RequestOptions,
    hasJson: boolean,
  ): Promise<Response> {
    const url = this.buildUrl(path, options.params);
    let attempt = 0;
    while (true) {
      let response: Response;
      try {
        response = await this.sendOnce(url, method, headers, options, hasJson);
      } catch (err) {
        const shouldRetry = this._retry.shouldRetry(attempt, { method });
        if (!shouldRetry) {
          throw wrapTransportError(err);
        }
        const delay = this._retry.computeDelay(attempt, {});
        await sleep(delay);
        attempt += 1;
        continue;
      }

      if (response.status >= 200 && response.status < 300) {
        return response;
      }

      // Non-2xx: decide whether to retry.
      const shouldRetry = this._retry.shouldRetry(attempt, {
        status: response.status,
        method,
      });
      if (!shouldRetry) {
        this._lastResponse = response;
        throw await errorFromResponse(response);
      }

      const retryAfter = parseRetryAfter(response.headers.get("retry-after"));
      const delay = this._retry.computeDelay(attempt, { retryAfter });
      // Drain the response body so the socket can be reused.
      try {
        await response.text();
      } catch {
        /* no-op — best-effort drain */
      }
      await sleep(delay);
      attempt += 1;
    }
  }

  private async sendOnce(
    url: string,
    method: string,
    headers: Record<string, string>,
    options: RequestOptions,
    hasJson: boolean,
  ): Promise<Response> {
    const controller = new AbortController();
    const timeoutMs = this._timeout;
    const timeoutHandle = setTimeout(() => controller.abort(new TimeoutSignal()), timeoutMs);
    let externalListener: (() => void) | undefined;
    if (options.signal) {
      if (options.signal.aborted) controller.abort(options.signal.reason);
      externalListener = () => controller.abort(options.signal!.reason);
      options.signal.addEventListener("abort", externalListener, { once: true });
    }
    try {
      const init: RequestInit = {
        method,
        headers,
        signal: controller.signal,
        redirect: "manual",
      };
      if (hasJson) init.body = JSON.stringify(options.json);
      return await this._fetch(url, init);
    } finally {
      clearTimeout(timeoutHandle);
      if (options.signal && externalListener) {
        options.signal.removeEventListener("abort", externalListener);
      }
    }
  }
}

class TimeoutSignal extends Error {
  override readonly name = "TimeoutSignal";
  constructor() {
    super("request timed out");
  }
}

function resolveRetryPolicy(
  policy: RetryPolicy | undefined,
  maxRetries: number | undefined,
): RetryPolicy {
  if (policy !== undefined) return policy;
  if (maxRetries === undefined) return new RetryPolicy();
  return new RetryPolicy({ maxRetries });
}

function buildHeaders(
  apiKey: string,
  apiVersion: string,
  extra: Record<string, string> | undefined,
): Record<string, string> {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${apiKey}`,
    "User-Agent": defaultUserAgent(),
    "Legalize-API-Version": apiVersion,
    Accept: "application/json",
  };
  if (extra) Object.assign(headers, extra);
  return headers;
}

/**
 * Serialize query params matching the Python reference:
 *   - undefined/null → dropped.
 *   - booleans → "true" / "false".
 *   - arrays → comma-joined; empty arrays dropped.
 *   - everything else → String(value).
 */
export function buildQueryString(params: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    let serialized: string;
    if (typeof value === "boolean") {
      serialized = value ? "true" : "false";
    } else if (Array.isArray(value)) {
      if (value.length === 0) continue;
      serialized = value.map((v) => String(v)).join(",");
    } else {
      serialized = String(value);
    }
    parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(serialized)}`);
  }
  return parts.join("&");
}

async function errorFromResponse(response: Response): Promise<APIError> {
  const text = await response.text();
  let data: unknown = undefined;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = undefined;
    }
  }
  return APIError.fromResponse(response, text, data);
}

/** Read a 2xx response body once and build a {@link RawResponse}. */
async function rawFromResponse(response: Response): Promise<RawResponse> {
  const buffer = await response.arrayBuffer();
  const content = new Uint8Array(buffer);
  const text = new TextDecoder().decode(content);
  return {
    statusCode: response.status,
    content,
    text,
    contentType: response.headers.get("content-type") ?? "",
    headers: headersToRecord(response.headers),
    json(): unknown {
      return JSON.parse(text);
    },
  };
}

function wrapTransportError(err: unknown): Error {
  if (err instanceof Error) {
    const isAbort =
      err.name === "AbortError" || (err as { code?: string }).code === "ABORT_ERR";
    const causeName = (err as { cause?: { name?: string } }).cause?.name;
    const isTimeout =
      isAbort &&
      (err.message.includes("timed out") ||
        err.message.toLowerCase().includes("timeout") ||
        causeName === "TimeoutSignal");
    if (isTimeout) {
      return new APITimeoutError("request timed out", { cause: err });
    }
    if (isAbort) {
      return new APIConnectionError("request aborted", { cause: err });
    }
    return new APIConnectionError(err.message || "transport error", { cause: err });
  }
  return new APIConnectionError("transport error");
}
