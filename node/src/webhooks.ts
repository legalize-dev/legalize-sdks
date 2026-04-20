/**
 * Webhook signature verification.
 *
 * Mirrors the server-side signer in the Legalize web backend. The scheme
 * is Stripe-shaped:
 *
 *   - Signed content: `${timestamp}.${rawJsonBody}` — RAW bytes, never
 *     a re-serialized JSON string. Reserialization will break the signature.
 *   - Algorithm: HMAC-SHA256, hex-encoded.
 *   - Header format: `v1=<hex>`. A future v2 scheme can coexist:
 *     `X-Legalize-Signature: v1=<sig1>,v2=<sig2>`.
 *   - Replay protection: reject if the header timestamp is more than
 *     `tolerance` seconds away from `now`. Default 300 seconds.
 *
 * Usage (Express):
 *
 *   import express from "express";
 *   import { Webhook, WebhookVerificationError } from "@legalize-dev/sdk";
 *
 *   app.post("/webhooks/legalize",
 *     express.raw({ type: "application/json" }),
 *     (req, res) => {
 *       try {
 *         const event = Webhook.verify({
 *           payload: req.body,  // Buffer
 *           sigHeader: req.header("X-Legalize-Signature") ?? "",
 *           timestamp: req.header("X-Legalize-Timestamp") ?? "",
 *           secret: process.env.LEGALIZE_WHSEC!,
 *         });
 *         if (event.type === "law.updated") { ... }
 *         res.status(204).send();
 *       } catch (err) {
 *         res.status(400).send();
 *       }
 *     });
 */

import { createHmac, timingSafeEqual } from "node:crypto";

import { WebhookVerificationError } from "./errors.js";

export const DEFAULT_TOLERANCE_SECONDS = 300; // 5 minutes — matches server
const SUPPORTED_SCHEMES = ["v1"];

export interface WebhookEvent {
  /** Server-assigned event id (e.g. `evt_...`). */
  readonly id: string;
  /** Event type (`law.created`, `law.updated`, `law.repealed`, ...). */
  readonly type: string;
  /** Server-side timestamp (ISO-8601 string). */
  readonly createdAt: string;
  /** Event-specific payload body. */
  readonly data: Record<string, unknown>;
  /** The full decoded JSON body — useful for fields the SDK doesn't type. */
  readonly raw: Record<string, unknown>;
}

export interface WebhookVerifyOptions {
  /** The raw request body bytes. Do NOT pass a re-serialized JSON string. */
  payload: Buffer | Uint8Array | string;
  /** The `X-Legalize-Signature` header value. May contain several `vN=<hex>` pairs. */
  sigHeader: string;
  /** The `X-Legalize-Timestamp` header value (Unix seconds, decimal string). */
  timestamp: string;
  /** The endpoint's signing secret. */
  secret: string;
  /** Seconds of clock skew accepted. Default 300. */
  tolerance?: number;
  /** Unit-test hook: override the reference wall clock (Unix seconds). */
  now?: number;
}

export class Webhook {
  /** Default anti-replay tolerance. */
  static readonly TOLERANCE = DEFAULT_TOLERANCE_SECONDS;

  /** Compute the canonical `v1=<hex>` signature for (payload, timestamp). */
  static computeSignature(secret: string, payload: Buffer | Uint8Array | string, timestamp: string): string {
    const payloadBuf = normalizePayload(payload);
    const signed = Buffer.concat([
      Buffer.from(timestamp, "utf8"),
      Buffer.from(".", "utf8"),
      payloadBuf,
    ]);
    const sig = createHmac("sha256", secret).update(signed).digest("hex");
    return `v1=${sig}`;
  }

  /**
   * Verify a webhook delivery and return the parsed event.
   *
   * Signature verification happens BEFORE JSON parsing, to protect the
   * process from resource-exhaustion on unauthenticated bodies.
   *
   * Throws WebhookVerificationError on any failure. The `.reason`
   * field identifies which check tripped for server-side logging,
   * while the user-facing message stays generic.
   */
  static verify(options: WebhookVerifyOptions): WebhookEvent {
    if (!options.sigHeader || !options.timestamp || !options.secret) {
      throw new WebhookVerificationError("missing_header");
    }

    const payloadBuf = normalizePayload(options.payload);

    // ---- timestamp (anti-replay) --------------------------------------
    if (!/^-?\d+$/.test(options.timestamp.trim())) {
      throw new WebhookVerificationError("bad_timestamp");
    }
    const ts = parseInt(options.timestamp.trim(), 10);
    if (Number.isNaN(ts)) {
      throw new WebhookVerificationError("bad_timestamp");
    }
    const tol = options.tolerance ?? Webhook.TOLERANCE;
    const reference = options.now ?? Date.now() / 1000;
    if (Math.abs(reference - ts) > tol) {
      throw new WebhookVerificationError("timestamp_outside_tolerance");
    }

    // ---- signature ----------------------------------------------------
    const expected = Webhook.computeSignature(options.secret, payloadBuf, options.timestamp);
    const expectedHex = expected.slice(expected.indexOf("=") + 1);
    const candidates = extractSchemeHexes(options.sigHeader);
    if (candidates.length === 0) {
      throw new WebhookVerificationError("no_valid_signature");
    }
    let match = false;
    const expectedBuf = Buffer.from(expectedHex, "hex");
    for (const candidate of candidates) {
      let candBuf: Buffer;
      try {
        candBuf = Buffer.from(candidate, "hex");
      } catch {
        continue;
      }
      if (candBuf.length !== expectedBuf.length) continue;
      if (timingSafeEqual(expectedBuf, candBuf)) {
        match = true;
        break;
      }
    }
    if (!match) {
      throw new WebhookVerificationError("bad_signature");
    }

    // ---- parse --------------------------------------------------------
    let parsed: unknown;
    try {
      parsed = JSON.parse(payloadBuf.toString("utf8"));
    } catch {
      throw new WebhookVerificationError("bad_signature");
    }
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new WebhookVerificationError("bad_signature");
    }
    return webhookEventFromPayload(parsed as Record<string, unknown>);
  }
}

function normalizePayload(payload: Buffer | Uint8Array | string): Buffer {
  if (Buffer.isBuffer(payload)) return payload;
  if (typeof payload === "string") return Buffer.from(payload, "utf8");
  return Buffer.from(payload);
}

function extractSchemeHexes(header: string): string[] {
  const out: string[] = [];
  for (const rawPart of header.split(",")) {
    const part = rawPart.trim();
    const eq = part.indexOf("=");
    if (eq < 0) continue;
    const scheme = part.slice(0, eq);
    const value = part.slice(eq + 1).trim();
    if (!value) continue;
    if (!SUPPORTED_SCHEMES.includes(scheme)) continue;
    // Hex validity is checked later via Buffer.from + length match.
    if (!/^[0-9a-fA-F]+$/.test(value)) continue;
    out.push(value);
  }
  return out;
}

function webhookEventFromPayload(payload: Record<string, unknown>): WebhookEvent {
  const eventType =
    (payload.event_type as string | undefined) ??
    (payload.type as string | undefined) ??
    "";
  return {
    id: String(payload.id ?? ""),
    type: String(eventType),
    createdAt: String(payload.created_at ?? ""),
    data:
      payload.data && typeof payload.data === "object" && !Array.isArray(payload.data)
        ? { ...(payload.data as Record<string, unknown>) }
        : {},
    raw: { ...payload },
  };
}
