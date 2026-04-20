/** Webhook signature verification. */

import { createHmac } from "node:crypto";

import { describe, expect, it } from "vitest";

import { Webhook, WebhookVerificationError } from "../src/index.js";

function sign(secret: string, payload: string, ts: string): string {
  const hmac = createHmac("sha256", secret);
  hmac.update(`${ts}.${payload}`);
  return hmac.digest("hex");
}

function nowSecs(): string {
  return String(Math.floor(Date.now() / 1000));
}

describe("Webhook.computeSignature", () => {
  it("matches a known vector", () => {
    const secret = "whsec_test";
    const payload = '{"id":"evt_1","type":"law.updated"}';
    const ts = "1700000000";
    const expected = sign(secret, payload, ts);
    expect(Webhook.computeSignature(secret, payload, ts)).toBe(`v1=${expected}`);
  });

  it("accepts Buffer payloads", () => {
    const secret = "whsec_test";
    const payload = Buffer.from('{"id":"evt_1"}');
    const ts = "1700000000";
    const sig = Webhook.computeSignature(secret, payload, ts);
    expect(sig).toMatch(/^v1=[a-f0-9]+$/);
  });

  it("accepts Uint8Array payloads", () => {
    const secret = "whsec_test";
    const payload = new TextEncoder().encode('{"id":"evt_1"}');
    const ts = "1700000000";
    const sig = Webhook.computeSignature(secret, payload, ts);
    expect(sig).toMatch(/^v1=[a-f0-9]+$/);
  });
});

describe("Webhook.verify", () => {
  const secret = "whsec_test";
  const payload = '{"id":"evt_1","event_type":"law.updated","created_at":"2026-01-01T00:00:00Z","data":{"law_id":"ley_x"}}';

  it("accepts a valid signature", () => {
    const ts = nowSecs();
    const sig = sign(secret, payload, ts);
    const event = Webhook.verify({
      payload,
      sigHeader: `v1=${sig}`,
      timestamp: ts,
      secret,
    });
    expect(event.id).toBe("evt_1");
    expect(event.type).toBe("law.updated");
    expect(event.data.law_id).toBe("ley_x");
    expect(event.raw.event_type).toBe("law.updated");
    expect(event.createdAt).toBe("2026-01-01T00:00:00Z");
  });

  it("rejects tampered body", () => {
    const ts = nowSecs();
    const sig = sign(secret, payload, ts);
    const tampered = payload.replace("ley_x", "ley_y");
    try {
      Webhook.verify({
        payload: tampered,
        sigHeader: `v1=${sig}`,
        timestamp: ts,
        secret,
      });
      throw new Error("did not throw");
    } catch (err) {
      expect(err).toBeInstanceOf(WebhookVerificationError);
      expect((err as WebhookVerificationError).reason).toBe("bad_signature");
    }
  });

  it("rejects stale timestamp", () => {
    const stale = String(Math.floor(Date.now() / 1000) - 10_000);
    const sig = sign(secret, payload, stale);
    try {
      Webhook.verify({
        payload,
        sigHeader: `v1=${sig}`,
        timestamp: stale,
        secret,
      });
      throw new Error("did not throw");
    } catch (err) {
      expect(err).toBeInstanceOf(WebhookVerificationError);
      expect((err as WebhookVerificationError).reason).toBe("timestamp_outside_tolerance");
    }
  });

  it("accepts timestamp within custom tolerance", () => {
    const ts = String(Math.floor(Date.now() / 1000) - 1000);
    const sig = sign(secret, payload, ts);
    const event = Webhook.verify({
      payload,
      sigHeader: `v1=${sig}`,
      timestamp: ts,
      secret,
      tolerance: 2000,
    });
    expect(event.id).toBe("evt_1");
  });

  it("accepts multi-signature header (first valid wins)", () => {
    const ts = nowSecs();
    const sig = sign(secret, payload, ts);
    const other = "0".repeat(64);
    const event = Webhook.verify({
      payload,
      sigHeader: `v1=${other},v1=${sig}`,
      timestamp: ts,
      secret,
    });
    expect(event.id).toBe("evt_1");
  });

  it("rejects missing sig header", () => {
    try {
      Webhook.verify({ payload, sigHeader: "", timestamp: "1", secret });
      throw new Error("did not throw");
    } catch (err) {
      expect(err).toBeInstanceOf(WebhookVerificationError);
      expect((err as WebhookVerificationError).reason).toBe("missing_header");
    }
  });

  it("rejects missing timestamp", () => {
    try {
      Webhook.verify({ payload, sigHeader: "v1=abc", timestamp: "", secret });
      throw new Error("did not throw");
    } catch (err) {
      expect((err as WebhookVerificationError).reason).toBe("missing_header");
    }
  });

  it("rejects missing secret", () => {
    try {
      Webhook.verify({ payload, sigHeader: "v1=abc", timestamp: "1", secret: "" });
      throw new Error("did not throw");
    } catch (err) {
      expect((err as WebhookVerificationError).reason).toBe("missing_header");
    }
  });

  it("rejects bad timestamp format", () => {
    try {
      Webhook.verify({
        payload,
        sigHeader: "v1=abc",
        timestamp: "not-a-number",
        secret,
      });
      throw new Error("did not throw");
    } catch (err) {
      expect((err as WebhookVerificationError).reason).toBe("bad_timestamp");
    }
  });

  it("rejects when no v1 scheme present", () => {
    const ts = nowSecs();
    try {
      Webhook.verify({
        payload,
        sigHeader: "v2=ffff",
        timestamp: ts,
        secret,
      });
      throw new Error("did not throw");
    } catch (err) {
      expect((err as WebhookVerificationError).reason).toBe("no_valid_signature");
    }
  });

  it("rejects header with only non-hex content", () => {
    const ts = nowSecs();
    try {
      Webhook.verify({
        payload,
        sigHeader: "v1=hello",
        timestamp: ts,
        secret,
      });
      throw new Error("did not throw");
    } catch (err) {
      expect((err as WebhookVerificationError).reason).toBe("no_valid_signature");
    }
  });

  it("rejects wrong-length hex", () => {
    const ts = nowSecs();
    try {
      Webhook.verify({
        payload,
        sigHeader: "v1=abc",
        timestamp: ts,
        secret,
      });
      throw new Error("did not throw");
    } catch (err) {
      expect((err as WebhookVerificationError).reason).toBe("bad_signature");
    }
  });

  it("rejects non-JSON payload", () => {
    const ts = nowSecs();
    const badPayload = "not json";
    const sig = sign(secret, badPayload, ts);
    try {
      Webhook.verify({
        payload: badPayload,
        sigHeader: `v1=${sig}`,
        timestamp: ts,
        secret,
      });
      throw new Error("did not throw");
    } catch (err) {
      expect(err).toBeInstanceOf(WebhookVerificationError);
    }
  });

  it("rejects JSON array payload", () => {
    const ts = nowSecs();
    const arrPayload = "[]";
    const sig = sign(secret, arrPayload, ts);
    try {
      Webhook.verify({
        payload: arrPayload,
        sigHeader: `v1=${sig}`,
        timestamp: ts,
        secret,
      });
      throw new Error("did not throw");
    } catch (err) {
      expect(err).toBeInstanceOf(WebhookVerificationError);
    }
  });

  it("honors `now` override", () => {
    const ts = "1700000000";
    const sig = sign(secret, payload, ts);
    const event = Webhook.verify({
      payload,
      sigHeader: `v1=${sig}`,
      timestamp: ts,
      secret,
      now: 1700000050,
    });
    expect(event.id).toBe("evt_1");
  });

  it("handles Buffer payload", () => {
    const ts = nowSecs();
    const sig = sign(secret, payload, ts);
    const event = Webhook.verify({
      payload: Buffer.from(payload, "utf8"),
      sigHeader: `v1=${sig}`,
      timestamp: ts,
      secret,
    });
    expect(event.id).toBe("evt_1");
  });

  it("constant-time compare actually runs on equal-length buffers", () => {
    // White-box: if the implementation used `===` we'd still pass valid
    // inputs, but a mismatched signature of the same length should be
    // reported as bad_signature (not as a thrown exception from
    // timingSafeEqual).
    const ts = nowSecs();
    const badSig = "f".repeat(64);
    try {
      Webhook.verify({
        payload,
        sigHeader: `v1=${badSig}`,
        timestamp: ts,
        secret,
      });
      throw new Error("did not throw");
    } catch (err) {
      expect(err).toBeInstanceOf(WebhookVerificationError);
      expect((err as WebhookVerificationError).reason).toBe("bad_signature");
    }
  });
});
