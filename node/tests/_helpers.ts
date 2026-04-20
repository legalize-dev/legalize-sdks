/**
 * Test helpers — a minimal mock-fetch harness.
 *
 * The SDK accepts a `fetch` override on construction, so we intercept
 * HTTP calls without touching any global state or pulling in MSW.
 */

import { vi } from "vitest";

export interface CapturedRequest {
  url: URL;
  method: string;
  headers: Record<string, string>;
  body: string | null;
}

export type Handler = (req: CapturedRequest) => Response | Promise<Response>;

export interface MockFetchHarness {
  fetch: typeof fetch;
  calls: CapturedRequest[];
}

/** Build a mock fetch that applies `handler` to every request. */
export function mockFetch(handler: Handler): MockFetchHarness {
  const calls: CapturedRequest[] = [];
  const fn = vi.fn(
    async (
      input: string | URL | Request,
      init?: RequestInit,
    ): Promise<Response> => {
      const urlStr =
        typeof input === "string" || input instanceof URL ? String(input) : input.url;
      const url = new URL(urlStr);
      const method = (init?.method ?? "GET").toUpperCase();
      const headers: Record<string, string> = {};
      const raw = init?.headers;
      if (raw) {
        if (raw instanceof Headers) {
          raw.forEach((v, k) => {
            headers[k.toLowerCase()] = v;
          });
        } else if (Array.isArray(raw)) {
          for (const entry of raw) {
            const k = entry[0];
            const v = entry[1];
            if (typeof k === "string" && typeof v === "string") {
              headers[k.toLowerCase()] = v;
            }
          }
        } else {
          for (const [k, v] of Object.entries(raw)) headers[k.toLowerCase()] = String(v);
        }
      }
      let body: string | null = null;
      if (init?.body !== undefined && init.body !== null) {
        if (typeof init.body === "string") body = init.body;
        else body = String(init.body);
      }
      const captured: CapturedRequest = { url, method, headers, body };
      calls.push(captured);

      const signal = init?.signal;
      if (signal?.aborted) {
        const err = Object.assign(new Error("aborted"), { name: "AbortError" });
        (err as { cause?: unknown }).cause = signal.reason;
        throw err;
      }
      if (signal) {
        // Race the handler against the signal.
        return await new Promise<Response>((resolve, reject) => {
          const onAbort = (): void => {
            const err = Object.assign(new Error("aborted"), { name: "AbortError" });
            (err as { cause?: unknown }).cause = signal.reason;
            reject(err);
          };
          signal.addEventListener("abort", onAbort, { once: true });
          Promise.resolve(handler(captured)).then(
            (res) => {
              signal.removeEventListener("abort", onAbort);
              resolve(res);
            },
            (err) => {
              signal.removeEventListener("abort", onAbort);
              reject(err);
            },
          );
        });
      }
      return await handler(captured);
    },
  );
  return { fetch: fn as unknown as typeof fetch, calls };
}

/** Shortcut: JSON response. */
export function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}
