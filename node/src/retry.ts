/**
 * Retry policy for transient failures.
 *
 * Retries happen on:
 *   - Network errors (DNS, connect, read timeout, TLS)
 *   - HTTP 429 (rate limit)
 *   - HTTP 500, 502, 503, 504 (transient server issues)
 *
 * Retries do NOT happen on:
 *   - 4xx other than 429 (caller error, retrying won't help)
 *   - Non-idempotent methods by default (POST, PATCH): mutations are
 *     never auto-retried. Only GET/HEAD/OPTIONS/PUT/DELETE are retried.
 *     This prevents duplicate webhook creation and duplicate retry calls.
 *
 * The `Retry-After` header wins when present and non-negative. Otherwise
 * exponential backoff with full jitter, capped at `maxDelay`.
 */

export const DEFAULT_MAX_RETRIES = 3;
export const DEFAULT_INITIAL_DELAY = 0.5; // seconds
export const DEFAULT_MAX_DELAY = 30.0; // seconds — matches Python reference
export const DEFAULT_BACKOFF_FACTOR = 2.0;

export const RETRY_STATUSES: ReadonlySet<number> = new Set([429, 500, 502, 503, 504]);

/** HTTP methods considered safe to auto-retry (idempotent). */
export const IDEMPOTENT_METHODS: ReadonlySet<string> = new Set([
  "GET",
  "HEAD",
  "OPTIONS",
  "PUT",
  "DELETE",
]);

export interface RetryPolicyOptions {
  maxRetries?: number;
  initialDelay?: number;
  maxDelay?: number;
  backoffFactor?: number;
  /**
   * When true, retry POST/PATCH too. Default false — the SDK never
   * auto-retries mutations unless the caller opts in explicitly.
   */
  retryNonIdempotent?: boolean;
}

/**
 * Configuration for automatic retries.
 *
 * Immutable — construct a new instance to tweak. Matches the Python
 * `RetryPolicy` contract:
 *   - `maxRetries`: total attempts is at most `maxRetries + 1`. 0 disables retries.
 *   - `initialDelay`: seconds before the first retry (pre-jitter).
 *   - `maxDelay`: cap on any single sleep in seconds.
 *   - `backoffFactor`: multiplier applied to delay each attempt.
 */
export class RetryPolicy {
  readonly maxRetries: number;
  readonly initialDelay: number;
  readonly maxDelay: number;
  readonly backoffFactor: number;
  readonly retryNonIdempotent: boolean;

  constructor(options: RetryPolicyOptions = {}) {
    this.maxRetries = options.maxRetries ?? DEFAULT_MAX_RETRIES;
    this.initialDelay = options.initialDelay ?? DEFAULT_INITIAL_DELAY;
    this.maxDelay = options.maxDelay ?? DEFAULT_MAX_DELAY;
    this.backoffFactor = options.backoffFactor ?? DEFAULT_BACKOFF_FACTOR;
    this.retryNonIdempotent = options.retryNonIdempotent ?? false;
  }

  /**
   * Decide whether to retry given attempt index, HTTP status, and method.
   *
   * `status` is undefined when the failure was a transport error before
   * the server returned a status. Transport errors are retried for any
   * method (the request never hit the server, so the "don't duplicate
   * mutations" concern doesn't apply).
   */
  shouldRetry(attempt: number, options: { status?: number; method?: string }): boolean {
    if (attempt >= this.maxRetries) return false;
    const method = (options.method ?? "GET").toUpperCase();

    if (options.status === undefined) {
      // Transport error — safe to retry even for POST/PATCH, because the
      // request never reached the server.
      return true;
    }

    if (!RETRY_STATUSES.has(options.status)) return false;

    // Server returned a retryable status. Only retry idempotent methods
    // unless the caller opted in.
    if (this.retryNonIdempotent) return true;
    return IDEMPOTENT_METHODS.has(method);
  }

  /**
   * Seconds to wait before retry `attempt` (0-indexed).
   *
   * `Retry-After` wins unambiguously when present and non-negative: the
   * server is telling us exactly how long to wait. Otherwise we use
   * exponential backoff with full jitter:
   *
   *     delay = random.uniform(0, min(maxDelay, initial * factor^attempt))
   *
   * Full jitter beats "equal jitter" and "decorrelated jitter" for
   * preventing thundering-herd recovery spikes.
   */
  computeDelay(attempt: number, options: { retryAfter?: number }): number {
    if (options.retryAfter !== undefined && options.retryAfter >= 0) {
      return Math.min(options.retryAfter, this.maxDelay);
    }
    const base = this.initialDelay * Math.pow(this.backoffFactor, attempt);
    const capped = Math.min(base, this.maxDelay);
    return Math.random() * capped;
  }
}

/**
 * Parse the `Retry-After` header into seconds.
 *
 * RFC 9110 allows two forms:
 *   - A non-negative integer (delta-seconds): `Retry-After: 120`
 *   - An HTTP-date: `Retry-After: Wed, 21 Oct 2025 07:28:00 GMT`
 *
 * Unparseable input returns `undefined` so the caller can fall back to
 * its own backoff. HTTP-date values in the past clamp to `0`.
 */
export function parseRetryAfter(header: string | null | undefined): number | undefined {
  if (header === null || header === undefined) return undefined;
  const trimmed = header.trim();
  if (!trimmed) return undefined;

  // Delta-seconds form: pure integer (possibly negative).
  if (/^-?\d+$/.test(trimmed)) {
    const n = parseInt(trimmed, 10);
    return Math.max(0, n);
  }

  // HTTP-date form.
  const parsed = Date.parse(trimmed);
  if (Number.isNaN(parsed)) return undefined;
  const nowMs = Date.now();
  const delta = (parsed - nowMs) / 1000;
  return Math.max(0, delta);
}

/** Promise-based sleep — used by the client's retry loop. */
export function sleep(seconds: number): Promise<void> {
  if (seconds <= 0) return Promise.resolve();
  return new Promise((resolve) => setTimeout(resolve, seconds * 1000));
}
