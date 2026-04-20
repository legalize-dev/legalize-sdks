/**
 * Error hierarchy for the Legalize SDK.
 *
 * The server returns three response shapes:
 *
 * 1. Structured dict from the API layer:
 *    { "detail": { "error": "quota_exceeded", "message": "...", "retry_after": 3600, ... } }
 *
 * 2. FastAPI validation errors (422):
 *    { "detail": [{ "loc": [...], "msg": "...", "type": "..." }, ...] }
 *
 * 3. Plain string detail for simple 404/400:
 *    { "detail": "Law not found: xyz" }
 *
 * `APIError.fromResponse` normalizes all three into an instance of the
 * most specific subclass, keeping the raw body on `.body` and the parsed
 * payload on `.data`.
 */

import { parseRetryAfter } from "./retry.js";

/** Base error for everything the SDK raises. */
export class LegalizeError extends Error {
  override readonly name: string = "LegalizeError";

  constructor(message: string, options?: { cause?: unknown }) {
    super(message);
    if (options?.cause !== undefined) {
      (this as { cause?: unknown }).cause = options.cause;
    }
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export interface APIErrorOptions {
  message: string;
  statusCode?: number;
  code?: string | undefined;
  body?: unknown;
  data?: unknown;
  requestId?: string | undefined;
  response?: Response | undefined;
  cause?: unknown;
}

/** Any non-2xx HTTP response. */
export class APIError extends LegalizeError {
  override readonly name: string = "APIError";
  readonly statusCode: number | undefined;
  readonly code: string | undefined;
  readonly body: unknown;
  readonly data: unknown;
  readonly requestId: string | undefined;
  readonly response: Response | undefined;

  constructor(options: APIErrorOptions) {
    super(options.message, options.cause !== undefined ? { cause: options.cause } : undefined);
    this.statusCode = options.statusCode;
    this.code = options.code;
    this.body = options.body;
    this.data = options.data;
    this.requestId = options.requestId;
    this.response = options.response;
  }

  override toString(): string {
    const parts: string[] = [];
    if (this.statusCode !== undefined) parts.push(`HTTP ${this.statusCode}`);
    if (this.code) parts.push(this.code);
    parts.push(this.message);
    if (this.requestId) parts.push(`(request_id=${this.requestId})`);
    return parts.join(" ");
  }

  /**
   * Build the most specific APIError subclass for a response.
   *
   * `body` is the raw bytes of the response body (or the parsed JSON
   * object if already consumed). `data` is the parsed JSON, which
   * drives error-code dispatch. Reads `X-Request-Id` for support.
   */
  static fromResponse(response: Response, body: unknown, data?: unknown): APIError {
    const status = response.status;
    const parsedData = data !== undefined ? data : body;
    const { code, message, extras } = parseErrorBody(parsedData, response);
    const requestId =
      response.headers.get("x-request-id") ?? response.headers.get("X-Request-Id") ?? undefined;

    const ErrorClass = pickErrorClass(status);
    const err = new ErrorClass({
      message,
      statusCode: status,
      code,
      body,
      data: parsedData,
      requestId,
      response,
    });
    // Copy extras (retry_after, limit, errors, etc.) onto the error.
    for (const [k, v] of Object.entries(extras)) {
      (err as unknown as Record<string, unknown>)[k] = v;
    }
    return err;
  }
}

export class AuthenticationError extends APIError {
  override readonly name = "AuthenticationError";
}
export class ForbiddenError extends APIError {
  override readonly name = "ForbiddenError";
}
export class NotFoundError extends APIError {
  override readonly name = "NotFoundError";
}
export class InvalidRequestError extends APIError {
  override readonly name = "InvalidRequestError";
}
export class ValidationError extends APIError {
  override readonly name = "ValidationError";
  readonly errors: Array<Record<string, unknown>> = [];
}
export class RateLimitError extends APIError {
  override readonly name = "RateLimitError";
  readonly retryAfter: number | undefined;
  readonly limit: number | undefined;
}
export class ServerError extends APIError {
  override readonly name: string = "ServerError";
}
export class ServiceUnavailableError extends ServerError {
  override readonly name: string = "ServiceUnavailableError";
}

/** Transport failure, no response. */
export class APIConnectionError extends LegalizeError {
  override readonly name: string = "APIConnectionError";
}

/** Request exceeded timeout. */
export class APITimeoutError extends APIConnectionError {
  override readonly name: string = "APITimeoutError";
}

export type WebhookVerificationReason =
  | "missing_header"
  | "bad_timestamp"
  | "timestamp_outside_tolerance"
  | "no_valid_signature"
  | "bad_signature";

/**
 * Raised by Webhook.verify on any signature or timestamp failure.
 *
 * The message is intentionally generic so that an attacker probing the
 * endpoint can't distinguish "bad signature" from "stale timestamp". The
 * specific reason is available on `.reason` for server-side logging.
 */
export class WebhookVerificationError extends LegalizeError {
  override readonly name: string = "WebhookVerificationError";
  readonly reason: WebhookVerificationReason;

  constructor(reason: WebhookVerificationReason) {
    super("Webhook signature verification failed");
    this.reason = reason;
  }
}

// --- internal parsing ----------------------------------------------------

interface ParsedErrorBody {
  code: string | undefined;
  message: string;
  extras: Record<string, unknown>;
}

function parseErrorBody(data: unknown, response: Response): ParsedErrorBody {
  const extras: Record<string, unknown> = {};
  let code: string | undefined;
  let message = "";

  if (data && typeof data === "object" && !Array.isArray(data)) {
    const dataObj = data as Record<string, unknown>;
    const detailRaw = "detail" in dataObj ? dataObj.detail : dataObj;

    if (detailRaw && typeof detailRaw === "object" && !Array.isArray(detailRaw)) {
      const detail = detailRaw as Record<string, unknown>;
      code = (detail.error as string | undefined) ?? (detail.code as string | undefined);
      message =
        (detail.message as string | undefined) ??
        (detail.detail as string | undefined) ??
        "";
      for (const key of ["retry_after", "limit", "upgrade_url"]) {
        if (key in detail) {
          // translate snake_case → camelCase for the Node idiom, but
          // preserve the raw key too to match server responses literally.
          if (key === "retry_after") {
            extras.retryAfter = detail[key];
          } else {
            extras[key] = detail[key];
          }
        }
      }
    } else if (Array.isArray(detailRaw)) {
      extras.errors = detailRaw;
      if (detailRaw.length > 0) {
        const first = detailRaw[0] as Record<string, unknown>;
        message = (first.msg as string | undefined) ?? "validation error";
      } else {
        message = "validation error";
      }
    } else if (typeof detailRaw === "string") {
      message = detailRaw;
    }
  }

  // If server didn't put retry_after in the body, pull it from the
  // Retry-After header. Supports both delta-seconds and HTTP-date.
  if (extras.retryAfter === undefined) {
    const parsed = parseRetryAfter(response.headers.get("retry-after"));
    if (parsed !== undefined) {
      extras.retryAfter = parsed;
    }
  }

  if (!message) {
    message = `HTTP ${response.status}`;
  }

  return { code, message, extras };
}

function pickErrorClass(status: number): new (opts: APIErrorOptions) => APIError {
  if (status === 400) return InvalidRequestError;
  if (status === 401) return AuthenticationError;
  if (status === 403) return ForbiddenError;
  if (status === 404) return NotFoundError;
  if (status === 422) return ValidationError;
  if (status === 429) return RateLimitError;
  if (status === 503) return ServiceUnavailableError;
  if (status >= 500 && status < 600) return ServerError;
  return APIError;
}
