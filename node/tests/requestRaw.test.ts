/**
 * `requestRaw` — the low-level content-negotiation escape hatch.
 *
 * Mirrors the Python `request_raw` contract: the `format` shorthand maps
 * to an `Accept` header (`xml` → `application/xml`, default), the body is
 * returned untouched as a `RawResponse`, and non-2xx responses raise the
 * same typed errors as `request`.
 */

import { describe, expect, it } from "vitest";

import { Legalize, NotFoundError, RateLimitError, RetryPolicy } from "../src/index.js";
import { mockFetch } from "./_helpers.js";

const SAMPLE_XML = '<?xml version="1.0"?><law id="BOE-A-1978-31229"><title>Constitución</title></law>';

/** Shortcut: a raw (non-JSON) response with an explicit content type. */
function rawResponse(
  status: number,
  body: string,
  contentType: string,
  headers: Record<string, string> = {},
): Response {
  return new Response(body, {
    status,
    headers: { "content-type": contentType, ...headers },
  });
}

describe("requestRaw", () => {
  it("defaults to Accept: application/xml", async () => {
    const { fetch, calls } = mockFetch(() =>
      rawResponse(200, SAMPLE_XML, "application/xml; charset=utf-8"),
    );
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    await c.requestRaw("GET", "/api/v1/es/laws/BOE-A-1978-31229");
    expect(calls[0]!.headers.accept).toBe("application/xml");
  });

  it("format:'json' sends Accept: application/json", async () => {
    const { fetch, calls } = mockFetch(() => rawResponse(200, "{}", "application/json"));
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    await c.requestRaw("GET", "/api/v1/countries", { format: "json" });
    expect(calls[0]!.headers.accept).toBe("application/json");
  });

  it("explicit media type passes through verbatim", async () => {
    const { fetch, calls } = mockFetch(() => rawResponse(200, SAMPLE_XML, "text/xml"));
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    await c.requestRaw("GET", "/api/v1/x", { format: "text/xml" });
    expect(calls[0]!.headers.accept).toBe("text/xml");
  });

  it("empty format falls back to xml", async () => {
    const { fetch, calls } = mockFetch(() =>
      rawResponse(200, SAMPLE_XML, "application/xml"),
    );
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    await c.requestRaw("GET", "/api/v1/x", { format: "" });
    expect(calls[0]!.headers.accept).toBe("application/xml");
  });

  it("forwards params and extraHeaders, keeps default Authorization", async () => {
    const { fetch, calls } = mockFetch(() =>
      rawResponse(200, SAMPLE_XML, "application/xml"),
    );
    const c = new Legalize({ apiKey: "leg_secret", baseUrl: "http://t", fetch, maxRetries: 0 });
    await c.requestRaw("GET", "/api/v1/es/laws", {
      params: { q: "foo bar", page: 2 },
      extraHeaders: { "X-Request-Tag": "raw-1" },
    });
    const call = calls[0]!;
    expect(call.url.searchParams.get("q")).toBe("foo bar");
    expect(call.url.searchParams.get("page")).toBe("2");
    expect(call.headers["x-request-tag"]).toBe("raw-1");
    // The negotiated Accept does not strip the auth / version headers.
    expect(call.headers.authorization).toBe("Bearer leg_secret");
    expect(call.headers["legalize-api-version"]).toBeDefined();
  });

  it("extraHeaders cannot clobber the negotiated Accept unless explicit", async () => {
    const { fetch, calls } = mockFetch(() =>
      rawResponse(200, SAMPLE_XML, "application/xml"),
    );
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    // An explicit Accept in extraHeaders wins (Object.assign order).
    await c.requestRaw("GET", "/api/v1/x", { extraHeaders: { Accept: "application/json" } });
    expect(calls[0]!.headers.accept).toBe("application/json");
  });

  it("exposes .text, .content, .contentType and .json()", async () => {
    const { fetch } = mockFetch(() =>
      rawResponse(200, SAMPLE_XML, "application/xml; charset=utf-8"),
    );
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    const res = await c.requestRaw("GET", "/api/v1/es/laws/BOE-A-1978-31229");
    expect(res.statusCode).toBe(200);
    expect(res.text).toBe(SAMPLE_XML);
    expect(res.contentType).toBe("application/xml; charset=utf-8");
    // Raw bytes round-trip back to the same string.
    expect(res.content).toBeInstanceOf(Uint8Array);
    expect(new TextDecoder().decode(res.content)).toBe(SAMPLE_XML);
    expect(res.headers["content-type"]).toBe("application/xml; charset=utf-8");
  });

  it(".json() parses a JSON-negotiated body", async () => {
    const { fetch } = mockFetch(() =>
      rawResponse(200, '{"code":"es","name":"Spain"}', "application/json"),
    );
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    const res = await c.requestRaw("GET", "/api/v1/countries", { format: "json" });
    expect(res.json()).toEqual({ code: "es", name: "Spain" });
  });

  it("does not JSON-parse the body (XML stays raw)", async () => {
    const { fetch } = mockFetch(() =>
      rawResponse(200, SAMPLE_XML, "application/xml"),
    );
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    // XML body must not raise the "non-JSON body" APIError that `request` would.
    const res = await c.requestRaw("GET", "/api/v1/x");
    expect(res.text.startsWith("<?xml")).toBe(true);
  });

  it("throws the typed error on non-2xx and sets lastResponse", async () => {
    const { fetch } = mockFetch(() =>
      rawResponse(
        404,
        "<error>not found</error>",
        "application/xml",
        { "x-request-id": "req_raw" },
      ),
    );
    const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
    await expect(c.requestRaw("GET", "/api/v1/es/laws/missing")).rejects.toBeInstanceOf(
      NotFoundError,
    );
    expect(c.lastResponse).not.toBeNull();
    expect(c.lastResponse!.status).toBe(404);
    expect(c.lastResponse!.headers.get("x-request-id")).toBe("req_raw");
  });

  it("runs the same retry policy as request", async () => {
    const responses = [
      rawResponse(503, "<error/>", "application/xml"),
      rawResponse(200, SAMPLE_XML, "application/xml"),
    ];
    let i = 0;
    const { fetch, calls } = mockFetch(() => responses[i++]!);
    const c = new Legalize({
      apiKey: "leg_t",
      baseUrl: "http://t",
      retry: new RetryPolicy({ maxRetries: 3, initialDelay: 0, maxDelay: 0 }),
      fetch,
    });
    const res = await c.requestRaw("GET", "/api/v1/x");
    expect(calls.length).toBe(2);
    expect(res.statusCode).toBe(200);
  });

  it("exhausts retries and raises the typed error (RateLimitError)", async () => {
    const { fetch } = mockFetch(() =>
      rawResponse(429, "<error/>", "application/xml", { "retry-after": "0" }),
    );
    const c = new Legalize({
      apiKey: "leg_t",
      baseUrl: "http://t",
      retry: new RetryPolicy({ maxRetries: 1, initialDelay: 0, maxDelay: 0 }),
      fetch,
    });
    await expect(c.requestRaw("GET", "/api/v1/x")).rejects.toBeInstanceOf(RateLimitError);
    expect(c.lastResponse!.status).toBe(429);
  });
});
