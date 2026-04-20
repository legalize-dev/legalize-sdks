/** Error hierarchy: class dispatch, parsing, extras. */

import { describe, expect, it } from "vitest";

import {
  APIConnectionError,
  APIError,
  APITimeoutError,
  AuthenticationError,
  ForbiddenError,
  InvalidRequestError,
  LegalizeError,
  NotFoundError,
  RateLimitError,
  ServerError,
  ServiceUnavailableError,
  ValidationError,
  WebhookVerificationError,
} from "../src/index.js";

function makeResponse(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}

describe("class hierarchy", () => {
  it("all errors inherit LegalizeError", () => {
    const opts = { message: "x", statusCode: 400 };
    expect(new APIError(opts)).toBeInstanceOf(LegalizeError);
    expect(new AuthenticationError(opts)).toBeInstanceOf(APIError);
    expect(new NotFoundError(opts)).toBeInstanceOf(APIError);
    expect(new ForbiddenError(opts)).toBeInstanceOf(APIError);
    expect(new InvalidRequestError(opts)).toBeInstanceOf(APIError);
    expect(new ValidationError(opts)).toBeInstanceOf(APIError);
    expect(new RateLimitError(opts)).toBeInstanceOf(APIError);
    expect(new ServerError(opts)).toBeInstanceOf(APIError);
    expect(new ServiceUnavailableError(opts)).toBeInstanceOf(ServerError);
    expect(new APIConnectionError("t")).toBeInstanceOf(LegalizeError);
    expect(new APITimeoutError("t")).toBeInstanceOf(APIConnectionError);
    expect(new WebhookVerificationError("bad_signature")).toBeInstanceOf(LegalizeError);
  });
});

describe("APIError.fromResponse dispatch", () => {
  const cases: Array<[number, typeof APIError]> = [
    [400, InvalidRequestError],
    [401, AuthenticationError],
    [403, ForbiddenError],
    [404, NotFoundError],
    [422, ValidationError],
    [429, RateLimitError],
    [500, ServerError],
    [502, ServerError],
    [503, ServiceUnavailableError],
    [504, ServerError],
    [418, APIError],
  ];
  for (const [status, cls] of cases) {
    it(`${status} → ${cls.name}`, () => {
      const res = makeResponse(status, { detail: "boom" });
      const err = APIError.fromResponse(res, '{"detail":"boom"}', { detail: "boom" });
      expect(err).toBeInstanceOf(cls);
      expect(err.statusCode).toBe(status);
      expect(err.message).toBe("boom");
    });
  }
});

describe("error body parsing", () => {
  it("structured detail dict populates code + extras", () => {
    const body = {
      detail: {
        error: "quota_exceeded",
        message: "Monthly quota exceeded",
        retry_after: 3600,
        limit: 10000,
        upgrade_url: "https://legalize.dev/pricing",
      },
    };
    const res = makeResponse(429, body);
    const err = APIError.fromResponse(res, JSON.stringify(body), body);
    expect(err).toBeInstanceOf(RateLimitError);
    expect(err.code).toBe("quota_exceeded");
    expect(err.message).toBe("Monthly quota exceeded");
    expect((err as unknown as Record<string, unknown>).retryAfter).toBe(3600);
    expect((err as unknown as Record<string, unknown>).limit).toBe(10000);
  });

  it("FastAPI validation list populates .errors", () => {
    const body = {
      detail: [
        { loc: ["query", "page"], msg: "input should be >= 1", type: "value_error" },
      ],
    };
    const res = makeResponse(422, body);
    const err = APIError.fromResponse(res, JSON.stringify(body), body) as ValidationError;
    expect(err).toBeInstanceOf(ValidationError);
    expect((err as unknown as Record<string, unknown>).errors).toEqual(body.detail);
    expect(err.message).toBe("input should be >= 1");
  });

  it("plain string detail shows the message", () => {
    const body = { detail: "Law not found" };
    const res = makeResponse(404, body);
    const err = APIError.fromResponse(res, JSON.stringify(body), body);
    expect(err.message).toBe("Law not found");
  });

  it("reads X-Request-Id header", () => {
    const res = makeResponse(500, { detail: "oops" }, { "x-request-id": "req_abc" });
    const err = APIError.fromResponse(res, '{"detail":"oops"}', { detail: "oops" });
    expect(err.requestId).toBe("req_abc");
  });

  it("pulls retry_after from header when body omits it", () => {
    const res = makeResponse(429, { detail: "slow" }, { "retry-after": "15" });
    const err = APIError.fromResponse(res, '{"detail":"slow"}', { detail: "slow" });
    expect((err as unknown as Record<string, unknown>).retryAfter).toBe(15);
  });

  it("falls back to HTTP status when message missing", () => {
    const res = makeResponse(500, {});
    const err = APIError.fromResponse(res, "{}", {});
    expect(err.message).toBe("HTTP 500");
  });

  it("toString includes parts", () => {
    const err = new APIError({
      message: "boom",
      statusCode: 500,
      code: "srv",
      requestId: "req_42",
    });
    expect(err.toString()).toContain("HTTP 500");
    expect(err.toString()).toContain("srv");
    expect(err.toString()).toContain("boom");
    expect(err.toString()).toContain("req_42");
  });
});
