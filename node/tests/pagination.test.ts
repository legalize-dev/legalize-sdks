/** Pagination iterators — async iteration, limits, total=0, lazy fetch. */

import { describe, expect, it } from "vitest";

import { OffsetIterator, PAGE_MAX, PageIterator } from "../src/index.js";

async function collect<T>(it: AsyncIterable<T>): Promise<T[]> {
  const out: T[] = [];
  for await (const v of it) out.push(v);
  return out;
}

describe("PageIterator", () => {
  it("yields nothing when total=0 and does not spin", async () => {
    let calls = 0;
    const it = new PageIterator<string>(async () => {
      calls++;
      return [[], 0];
    }, { perPage: 50 });
    const out = await collect(it);
    expect(out).toEqual([]);
    expect(calls).toBeLessThanOrEqual(1);
  });

  it("yields all items across pages", async () => {
    const pages: Array<[string[], number]> = [
      [["a", "b"], 4],
      [["c", "d"], 4],
    ];
    let i = 0;
    const it = new PageIterator<string>(async () => pages[i++]!, { perPage: 2 });
    const out = await collect(it);
    expect(out).toEqual(["a", "b", "c", "d"]);
  });

  it("stops when short page arrives", async () => {
    const pages: Array<[string[], number]> = [
      [["a", "b"], 10],
      [["c"], 10],
    ];
    let i = 0;
    const it = new PageIterator<string>(async () => pages[i++]!, { perPage: 2 });
    const out = await collect(it);
    expect(out).toEqual(["a", "b", "c"]);
  });

  it("respects `limit` cap", async () => {
    let call = 0;
    const it = new PageIterator<string>(
      async () => {
        call++;
        return [["a", "b", "c"], 100];
      },
      { perPage: 3, limit: 2 },
    );
    const out = await collect(it);
    expect(out).toEqual(["a", "b"]);
    expect(call).toBe(1);
  });

  it("lazy: doesn't fetch page 2 until page 1 drained", async () => {
    let fetched = 0;
    const pages: Array<[string[], number]> = [
      [["a", "b"], 4],
      [["c", "d"], 4],
    ];
    const it = new PageIterator<string>(
      async () => {
        fetched++;
        return pages[fetched - 1]!;
      },
      { perPage: 2 },
    );
    const iter = it[Symbol.asyncIterator]();
    await iter.next();
    expect(fetched).toBe(1);
    await iter.next();
    expect(fetched).toBe(1);
    await iter.next(); // triggers page 2
    expect(fetched).toBe(2);
  });

  it("rejects invalid perPage", () => {
    expect(() => new PageIterator<string>(async () => [[], 0], { perPage: 0 })).toThrow();
    expect(() => new PageIterator<string>(async () => [[], 0], { perPage: PAGE_MAX + 1 })).toThrow();
  });

  it("rejects negative limit", () => {
    expect(() => new PageIterator<string>(async () => [[], 0], { limit: -1 })).toThrow();
  });

  it("yields exactly `total` across page boundaries", async () => {
    const pages: Array<[string[], number]> = [
      [["a", "b", "c"], 5],
      [["d", "e"], 5],
    ];
    let i = 0;
    const it = new PageIterator<string>(async () => pages[i++]!, { perPage: 3 });
    const out = await collect(it);
    expect(out.length).toBe(5);
  });
});

describe("OffsetIterator", () => {
  it("yields all items across batches", async () => {
    const pages: Array<[string[], number]> = [
      [["a", "b"], 3],
      [["c"], 3],
    ];
    let i = 0;
    const it = new OffsetIterator<string>(async () => pages[i++]!, { batch: 2 });
    const out = await collect(it);
    expect(out).toEqual(["a", "b", "c"]);
  });

  it("respects `limit`", async () => {
    const it = new OffsetIterator<string>(async () => [["a", "b", "c"], 10], {
      batch: 3,
      limit: 2,
    });
    const out = await collect(it);
    expect(out).toEqual(["a", "b"]);
  });

  it("stops when short batch arrives", async () => {
    const pages: Array<[string[], number]> = [
      [["a", "b"], 10],
      [["c"], 10],
    ];
    let i = 0;
    const it = new OffsetIterator<string>(async () => pages[i++]!, { batch: 2 });
    const out = await collect(it);
    expect(out).toEqual(["a", "b", "c"]);
  });

  it("yields nothing when first batch empty", async () => {
    const it = new OffsetIterator<string>(async () => [[], 0], { batch: 10 });
    const out = await collect(it);
    expect(out).toEqual([]);
  });

  it("rejects invalid batch", () => {
    expect(() => new OffsetIterator<string>(async () => [[], 0], { batch: 0 })).toThrow();
  });

  it("rejects negative limit", () => {
    expect(() => new OffsetIterator<string>(async () => [[], 0], { limit: -1 })).toThrow();
  });
});
