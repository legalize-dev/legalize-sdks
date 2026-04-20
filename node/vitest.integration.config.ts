import { defineConfig } from "vitest/config";

// Separate config for the live-API integration suite. CI runs this via
// `npm run test:integration` under node-integration.yml with
// LEGALIZE_API_KEY set. Locally, set the env vars and run the same
// command; otherwise the default `npm test` already excludes this path.
export default defineConfig({
  test: {
    environment: "node",
    include: ["tests/integration/**/*.test.ts"],
    // Network requests to the real API can be slow — give each test room.
    testTimeout: 30_000,
  },
});
