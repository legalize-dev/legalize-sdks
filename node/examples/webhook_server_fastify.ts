/**
 * Minimal Fastify webhook server that verifies Legalize signatures.
 *
 * Install dependencies:
 *
 *   npm install fastify legalize
 *
 * Run:
 *
 *   LEGALIZE_WHSEC=whsec_... npx tsx examples/webhook_server_fastify.ts
 */

import Fastify from "fastify";

import { Webhook, WebhookVerificationError } from "legalize";

const SECRET = process.env.LEGALIZE_WHSEC!;
if (!SECRET) {
  throw new Error("LEGALIZE_WHSEC is required");
}

const app = Fastify({ logger: true });

// Register a raw-body parser for application/json so signature
// verification sees the exact bytes the server signed.
app.addContentTypeParser(
  "application/json",
  { parseAs: "buffer" },
  (_req, body, done) => {
    done(null, body);
  },
);

app.post("/webhooks/legalize", async (req, reply) => {
  try {
    const event = Webhook.verify({
      payload: req.body as Buffer,
      sigHeader: (req.headers["x-legalize-signature"] as string) ?? "",
      timestamp: (req.headers["x-legalize-timestamp"] as string) ?? "",
      secret: SECRET,
    });
    req.log.info({ type: event.type, id: event.id }, "legalize event");
    if (event.type === "law.updated") {
      // React to law updates — enqueue a worker, update your DB, etc.
    }
    await reply.code(204).send();
  } catch (err) {
    if (err instanceof WebhookVerificationError) {
      req.log.warn({ reason: err.reason }, "webhook rejected");
      await reply.code(400).send();
      return;
    }
    throw err;
  }
});

const port = Number(process.env.PORT ?? 3000);
app.listen({ port, host: "0.0.0.0" }).catch((err) => {
  app.log.error(err);
  process.exit(1);
});
