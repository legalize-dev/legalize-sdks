/**
 * Read-only integration tests against the live Legalize API.
 *
 * Skipped automatically when `LEGALIZE_API_KEY` is not in the
 * environment, so developers can run `npm test` locally without
 * hitting production.
 *
 * The assertions target CONTRACT shape (types, required fields, stable
 * invariants) rather than specific counts that drift over time.
 */

import { describe, expect, it } from "vitest";

import { Legalize, NotFoundError } from "../../src/index.js";

const key = process.env.LEGALIZE_API_KEY;
const describeIf = key ? describe : describe.skip;

describeIf("integration · live prod", () => {
  const client = new Legalize({
    apiKey: key,
    baseUrl: process.env.LEGALIZE_BASE_URL ?? "https://legalize.dev",
  });

  describe("countries", () => {
    it("returns non-empty list with es present", async () => {
      const countries = await client.countries.list();
      expect(countries.length).toBeGreaterThan(0);
      expect(countries.map((c) => c.country)).toContain("es");
    });
  });

  describe("jurisdictions", () => {
    it("returns regions for Spain", async () => {
      const regions = await client.jurisdictions.list("es");
      expect(regions.length).toBeGreaterThan(0);
    });

    it("throws NotFoundError for unknown country", async () => {
      await expect(client.jurisdictions.list("zz")).rejects.toBeInstanceOf(NotFoundError);
    });
  });

  describe("laws", () => {
    it("lists first page for Spain", async () => {
      const page = await client.laws.list("es", { page: 1, perPage: 5 });
      expect(page.country).toBe("es");
      expect(page.total).toBeGreaterThan(0);
      expect(page.results.length).toBeLessThanOrEqual(5);
    });

    it("search returns matches for a common term", async () => {
      const page = await client.laws.search("es", "protección de datos", { perPage: 3 });
      expect(page.total).toBeGreaterThan(0);
      expect(page.results.length).toBeGreaterThan(0);
    });

    it("404 on unknown law id", async () => {
      await expect(
        client.laws.retrieve("es", "does_not_exist_xxxxx"),
      ).rejects.toBeInstanceOf(NotFoundError);
    });
  });

  describe("stats", () => {
    it("returns structured stats for Spain", async () => {
      const stats = await client.stats.retrieve("es");
      expect(stats.country).toBe("es");
      expect(Array.isArray(stats.law_types)).toBe(true);
    });
  });
});
