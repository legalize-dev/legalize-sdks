/**
 * Resource endpoints — verifies the request shape (method, URL, params,
 * body) for every SDK method.
 */

import { describe, expect, it } from "vitest";

import { Legalize } from "../src/index.js";
import { jsonResponse, mockFetch, type CapturedRequest } from "./_helpers.js";

function buildClient<T>(responseBody: T, status = 200) {
  const { fetch, calls } = mockFetch(() => jsonResponse(status, responseBody));
  const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
  return { client: c, calls };
}

function buildClientSeq(responses: Array<[number, unknown]>) {
  let i = 0;
  const { fetch, calls } = mockFetch(() => {
    const [status, body] = responses[i++]!;
    return jsonResponse(status, body);
  });
  const c = new Legalize({ apiKey: "leg_t", baseUrl: "http://t", fetch, maxRetries: 0 });
  return { client: c, calls };
}

function qParams(req: CapturedRequest): Record<string, string> {
  const out: Record<string, string> = {};
  req.url.searchParams.forEach((v, k) => {
    out[k] = v;
  });
  return out;
}

// ---- countries ---------------------------------------------------------

describe("countries.list", () => {
  it("hits /api/v1/countries", async () => {
    const { client, calls } = buildClient([{ country: "es", count: 100 }]);
    const out = await client.countries.list();
    expect(calls[0]!.url.pathname).toBe("/api/v1/countries");
    expect(calls[0]!.method).toBe("GET");
    expect(out[0]!.country).toBe("es");
  });
});

// ---- jurisdictions -----------------------------------------------------

describe("jurisdictions.list", () => {
  it("hits /api/v1/{country}/jurisdictions", async () => {
    const { client, calls } = buildClient([{ jurisdiction: "catalonia", count: 50 }]);
    await client.jurisdictions.list("es");
    expect(calls[0]!.url.pathname).toBe("/api/v1/es/jurisdictions");
  });
});

// ---- lawTypes ---------------------------------------------------------

describe("lawTypes.list", () => {
  it("hits /api/v1/{country}/law-types", async () => {
    const { client, calls } = buildClient(["constitucion", "ley"]);
    const out = await client.lawTypes.list("es");
    expect(calls[0]!.url.pathname).toBe("/api/v1/es/law-types");
    expect(out).toEqual(["constitucion", "ley"]);
  });
});

// ---- laws -------------------------------------------------------------

const LAW_META = {
  id: "ley_organica_3_2018",
  country: "es",
  law_type: "ley_organica",
  title: "Ley Orgánica 3/2018",
};

describe("laws.list", () => {
  it("serializes filters as expected", async () => {
    const { client, calls } = buildClient({
      country: "es",
      total: 2,
      page: 1,
      per_page: 50,
      results: [LAW_META, { ...LAW_META, id: "y" }],
    });
    await client.laws.list("es", {
      page: 1,
      perPage: 50,
      lawType: ["ley_organica", "ley"],
      year: 2018,
      status: "vigente",
    });
    const q = qParams(calls[0]!);
    expect(q.law_type).toBe("ley_organica,ley");
    expect(q.year).toBe("2018");
    expect(q.status).toBe("vigente");
    expect(q.page).toBe("1");
    expect(q.per_page).toBe("50");
  });
});

describe("laws.search", () => {
  it("requires a non-empty query", async () => {
    const c = new Legalize({ apiKey: "leg_t", fetch: async () => jsonResponse(200, {}) });
    await expect(c.laws.search("es", "")).rejects.toThrow(/q must be/);
    await expect(c.laws.search("es", "   ")).rejects.toThrow(/q must be/);
  });

  it("sets q in query string", async () => {
    const { client, calls } = buildClient({
      country: "es",
      total: 1,
      page: 1,
      per_page: 50,
      query: "privacidad",
      results: [LAW_META],
    });
    const out = await client.laws.search("es", "privacidad");
    expect(qParams(calls[0]!).q).toBe("privacidad");
    expect(out.total).toBe(1);
  });
});

describe("laws.iter", () => {
  it("paginates across total", async () => {
    const { client } = buildClientSeq([
      [
        200,
        {
          country: "es",
          total: 4,
          page: 1,
          per_page: 2,
          results: [
            { ...LAW_META, id: "a" },
            { ...LAW_META, id: "b" },
          ],
        },
      ],
      [
        200,
        {
          country: "es",
          total: 4,
          page: 2,
          per_page: 2,
          results: [
            { ...LAW_META, id: "c" },
            { ...LAW_META, id: "d" },
          ],
        },
      ],
    ]);
    const ids: string[] = [];
    for await (const law of client.laws.iter("es", { perPage: 2 })) {
      ids.push(law.id);
    }
    expect(ids).toEqual(["a", "b", "c", "d"]);
  });
});

describe("laws.searchIter", () => {
  it("requires a non-empty query", () => {
    // Note: searchIter is NOT async — it constructs an iterator
    // synchronously, so the input validation runs synchronously too.
    const c = new Legalize({ apiKey: "leg_t", fetch: async () => jsonResponse(200, {}) });
    expect(() => c.laws.searchIter("es", "")).toThrow(/q must be/);
  });

  it("auto-paginates search", async () => {
    const { client } = buildClientSeq([
      [
        200,
        {
          country: "es",
          total: 2,
          page: 1,
          per_page: 1,
          query: "x",
          results: [{ ...LAW_META, id: "a" }],
        },
      ],
      [
        200,
        {
          country: "es",
          total: 2,
          page: 2,
          per_page: 1,
          query: "x",
          results: [{ ...LAW_META, id: "b" }],
        },
      ],
    ]);
    const ids: string[] = [];
    for await (const l of client.laws.searchIter("es", "x", { perPage: 1 })) {
      ids.push(l.id);
    }
    expect(ids).toEqual(["a", "b"]);
  });
});

describe("laws.retrieve / meta / commits / atCommit", () => {
  it("retrieve", async () => {
    const { client, calls } = buildClient({ ...LAW_META, content_md: "# body" });
    const out = await client.laws.retrieve("es", "ley_organica_3_2018");
    expect(calls[0]!.url.pathname).toBe("/api/v1/es/laws/ley_organica_3_2018");
    expect(out.content_md).toBe("# body");
  });
  it("meta", async () => {
    const { client, calls } = buildClient({ ...LAW_META });
    await client.laws.meta("es", "ley_x");
    expect(calls[0]!.url.pathname.endsWith("/meta")).toBe(true);
  });
  it("commits", async () => {
    const { client, calls } = buildClient({
      law_id: "x",
      commits: [{ sha: "abc1234", date: "2024-01-01", message: "Initial" }],
    });
    const out = await client.laws.commits("es", "x");
    expect(calls[0]!.url.pathname.endsWith("/commits")).toBe(true);
    expect(out.commits[0]!.sha).toBe("abc1234");
  });
  it("atCommit", async () => {
    const { client, calls } = buildClient({
      law_id: "x",
      sha: "abc1234",
      content_md: "# historical",
    });
    await client.laws.atCommit("es", "x", "abc1234");
    expect(calls[0]!.url.pathname).toBe("/api/v1/es/laws/x/at/abc1234");
  });
});

// ---- reforms ----------------------------------------------------------

describe("reforms", () => {
  it("list serializes limit+offset", async () => {
    const { client, calls } = buildClient({
      law_id: "x",
      total: 1,
      offset: 0,
      limit: 100,
      reforms: [{ date: "2024-01-01", source_id: "s1" }],
    });
    await client.reforms.list("es", "x");
    const q = qParams(calls[0]!);
    expect(q.limit).toBe("100");
    expect(q.offset).toBe("0");
  });

  it("iter paginates", async () => {
    const { client } = buildClientSeq([
      [
        200,
        {
          law_id: "x",
          total: 3,
          offset: 0,
          limit: 2,
          reforms: [
            { date: "2024-01-01", source_id: "a" },
            { date: "2024-01-02", source_id: "b" },
          ],
        },
      ],
      [
        200,
        {
          law_id: "x",
          total: 3,
          offset: 2,
          limit: 2,
          reforms: [{ date: "2024-01-03", source_id: "c" }],
        },
      ],
    ]);
    const ids: string[] = [];
    for await (const r of client.reforms.iter("es", "x", { batch: 2 })) {
      ids.push(r.source_id!);
    }
    expect(ids).toEqual(["a", "b", "c"]);
  });
});

// ---- stats ------------------------------------------------------------

describe("stats", () => {
  it("retrieve base", async () => {
    const { client, calls } = buildClient({
      country: "es",
      jurisdiction: null,
      reform_activity_by_year: [{ year: 2024, count: 100 }],
      most_reformed_laws: [{ id: "x", title: "T", count: 50 }],
      law_types: ["ley"],
    });
    await client.stats.retrieve("es");
    expect(calls[0]!.url.pathname).toBe("/api/v1/es/stats");
  });

  it("retrieve with jurisdiction filter", async () => {
    const { client, calls } = buildClient({
      country: "es",
      jurisdiction: "catalonia",
      reform_activity_by_year: [],
      most_reformed_laws: [],
      law_types: [],
    });
    await client.stats.retrieve("es", { jurisdiction: "catalonia" });
    expect(qParams(calls[0]!).jurisdiction).toBe("catalonia");
  });
});

// ---- webhooks ---------------------------------------------------------

describe("webhooks", () => {
  it("create posts body", async () => {
    const { client, calls } = buildClient({
      id: 1,
      url: "https://example.test/hook",
      secret: "whsec_abc",
      event_types: ["law.updated"],
      countries: ["es"],
      description: "",
      enabled: true,
      created_at: "2026-04-01T00:00:00Z",
    });
    const out = await client.webhooks.create({
      url: "https://example.test/hook",
      eventTypes: ["law.updated"],
      countries: ["es"],
    });
    expect(calls[0]!.method).toBe("POST");
    expect(calls[0]!.url.pathname).toBe("/api/v1/webhooks");
    const body = JSON.parse(calls[0]!.body!);
    expect(body.url).toBe("https://example.test/hook");
    expect(body.event_types).toEqual(["law.updated"]);
    expect(out.secret).toBe("whsec_abc");
  });

  it("list", async () => {
    const { client } = buildClient([{ id: 1, url: "u", enabled: true }]);
    const out = await client.webhooks.list();
    expect(out).toEqual([{ id: 1, url: "u", enabled: true }]);
  });

  it("retrieve", async () => {
    const { client, calls } = buildClient({ id: 7, url: "u" });
    await client.webhooks.retrieve(7);
    expect(calls[0]!.url.pathname).toBe("/api/v1/webhooks/7");
  });

  it("update patches a subset", async () => {
    const { client, calls } = buildClient({ id: 7, enabled: false });
    await client.webhooks.update(7, { enabled: false, description: "paused" });
    expect(calls[0]!.method).toBe("PATCH");
    const body = JSON.parse(calls[0]!.body!);
    expect(body).toEqual({ description: "paused", enabled: false });
  });

  it("delete", async () => {
    const { client, calls } = buildClient({ status: "deleted" });
    const out = await client.webhooks.delete(7);
    expect(calls[0]!.method).toBe("DELETE");
    expect(out).toEqual({ status: "deleted" });
  });

  it("deliveries params", async () => {
    const { client, calls } = buildClient({ total: 0, deliveries: [] });
    await client.webhooks.deliveries(7, { page: 2, status: "failed" });
    const q = qParams(calls[0]!);
    expect(q.page).toBe("2");
    expect(q.status).toBe("failed");
  });

  it("deliveries rejects bad status", async () => {
    const c = new Legalize({ apiKey: "leg_t", fetch: async () => jsonResponse(200, {}) });
    await expect(
      c.webhooks.deliveries(7, { status: "weird" as unknown as "failed" }),
    ).rejects.toThrow(/status/);
  });

  it("retry", async () => {
    const { client, calls } = buildClient({ id: 42, status: "success" });
    await client.webhooks.retry(7, 42);
    expect(calls[0]!.url.pathname).toBe("/api/v1/webhooks/7/deliveries/42/retry");
  });

  it("test ping", async () => {
    const { client, calls } = buildClient({ id: 1, status: "success" });
    await client.webhooks.test(7);
    expect(calls[0]!.url.pathname).toBe("/api/v1/webhooks/7/test");
  });

  it("update with all fields", async () => {
    const { client, calls } = buildClient({ id: 1 });
    await client.webhooks.update(1, {
      url: "https://x",
      eventTypes: ["law.updated"],
      countries: ["es", "fr"],
      description: "d",
      enabled: true,
    });
    const body = JSON.parse(calls[0]!.body!);
    expect(body).toEqual({
      url: "https://x",
      event_types: ["law.updated"],
      countries: ["es", "fr"],
      description: "d",
      enabled: true,
    });
  });
});

// ---- query-param cleaning -------------------------------------------------

describe("query param serialization", () => {
  it("drops null/undefined values", async () => {
    const { client, calls } = buildClient([]);
    await client.request("GET", "/api/v1/countries", {
      params: { a: 1, b: null, c: undefined, d: "x" },
    });
    const q = qParams(calls[0]!);
    expect(q.a).toBe("1");
    expect(q.d).toBe("x");
    expect("b" in q).toBe(false);
    expect("c" in q).toBe(false);
  });

  it("coerces booleans to string", async () => {
    const { client, calls } = buildClient([]);
    await client.request("GET", "/api/v1/countries", { params: { t: true, f: false } });
    const q = qParams(calls[0]!);
    expect(q.t).toBe("true");
    expect(q.f).toBe("false");
  });

  it("joins arrays with comma", async () => {
    const { client, calls } = buildClient([]);
    await client.request("GET", "/api/v1/countries", {
      params: { kinds: ["a", "b", "c"] },
    });
    expect(qParams(calls[0]!).kinds).toBe("a,b,c");
  });

  it("drops empty arrays", async () => {
    const { client, calls } = buildClient([]);
    await client.request("GET", "/api/v1/countries", { params: { kinds: [] } });
    expect("kinds" in qParams(calls[0]!)).toBe(false);
  });
});
