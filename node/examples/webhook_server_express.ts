/**
 * Minimal Express webhook server that verifies Legalize signatures.
 *
 * Install dependencies:
 *
 *   npm install express legalize
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

import { Webhook, WebhookVerificationError } from "legalize";

const app = express();
const SECRET = process.env.LEGALIZE_WHSEC!;
if (!SECRET) {
  throw new Error("LEGALIZE_WHSEC is required");
}

// CRITICAL: use express.raw so we get the exact bytes the server signed.
// If you use `express.json()` the body is re-serialized and the signature
// no longer matches.
app.post(
  "/webhooks/legalize",
  express.raw({ type: "application/json" }),
  (req, res) => {
    try {
      const event = Webhook.verify({
        payload: req.body as Buffer,
        sigHeader: req.header("X-Legalize-Signature") ?? "",
        timestamp: req.header("X-Legalize-Timestamp") ?? "",
        secret: SECRET,
      });
      console.log(`[${event.type}] ${event.id}`, event.data);
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
