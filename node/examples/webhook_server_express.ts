/**
 * Minimal Express webhook server that verifies Legalize signatures.
 *
 * Install dependencies:
 *
 *   npm install express express-rate-limit legalize
 *   npm install --save-dev @types/express
 *
 * Run:
 *
 *   LEGALIZE_WHSEC=whsec_... npx tsx examples/webhook_server_express.ts
 *
 * Then register the endpoint URL in the Legalize dashboard and hit
 * "Send test event" — your server should print the event.
 */

import express from "express";
import rateLimit from "express-rate-limit";

import { Webhook, WebhookVerificationError } from "@legalize-dev/sdk";

const app = express();
const SECRET = process.env.LEGALIZE_WHSEC!;
if (!SECRET) {
  throw new Error("LEGALIZE_WHSEC is required");
}

// Rate-limit the webhook endpoint. Legalize sends each event at most a
// handful of times per minute, so this cap is generous; tune it for
// the scale you expect. The limiter runs before signature verification
// so it also protects against unauthenticated flooders.
const limiter = rateLimit({
  windowMs: 60_000,
  limit: 120,
  standardHeaders: true,
  legacyHeaders: false,
});

// CRITICAL: use express.raw so we get the exact bytes the server signed.
// If you use `express.json()` the body is re-serialized and the signature
// no longer matches.
app.post(
  "/webhooks/legalize",
  limiter,
  express.raw({ type: "application/json" }),
  (req, res) => {
    try {
      const event = Webhook.verify({
        payload: req.body as Buffer,
        sigHeader: req.header("X-Legalize-Signature") ?? "",
        timestamp: req.header("X-Legalize-Timestamp") ?? "",
        secret: SECRET,
      });
      // Structured logging via JSON is injection-safe — newlines in
      // user-controlled fields become \n inside a single record rather
      // than forging additional log lines.
      console.log(JSON.stringify({ type: event.type, id: event.id, data: event.data }));
      if (event.type === "law.updated") {
        // React to law updates — enqueue a worker, update your DB, etc.
      }
      res.status(204).send();
    } catch (err) {
      if (err instanceof WebhookVerificationError) {
        console.error("webhook rejected:", err.reason);
        res.status(400).send();
        return;
      }
      throw err;
    }
  },
);

const port = Number(process.env.PORT ?? 3000);
app.listen(port, () => {
  console.log(`Legalize webhook receiver listening on http://0.0.0.0:${port}/webhooks/legalize`);
});
