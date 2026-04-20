import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    // Offline tests only. Integration tests live under tests/integration/
    // and run via the `npm run test:integration` script (CI: node-integration.yml).
    include: ["tests/**/*.test.ts"],
    exclude: ["node_modules", "dist", "tests/integration/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "lcov"],
      include: ["src/**/*.ts"],
      exclude: ["src/generated.ts", "src/index.ts", "src/types.ts"],
      thresholds: {
        lines: 95,
        functions: 95,
        branches: 85,
        statements: 95,
      },
    },
  },
});
