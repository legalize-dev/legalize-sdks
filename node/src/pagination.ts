/**
 * Pagination helpers — async iterators over page- and offset-based endpoints.
 *
 * The Legalize API uses two pagination styles:
 *
 *   - page + perPage  — laws list, webhook deliveries
 *   - limit + offset  — reforms
 *
 * Each paginated response carries `total` (true match count). That lets
 * iterators terminate without inferring end-of-stream.
 *
 * The iterators here are transport-agnostic: they delegate fetching to
 * a caller-supplied async callback.
 */

export const PAGE_MAX = 100;

/** Async iterator over a page-based endpoint (page + perPage). */
export class PageIterator<T> implements AsyncIterableIterator<T> {
  private readonly fetchPage: (page: number, perPage: number) => Promise<[T[], number]>;
  private readonly perPage: number;
  private readonly limit: number | undefined;
  private page: number;
  private yielded: number;
  private buffer: T[];
  private bufferIdx: number;
  private total: number;
  private shortPage: boolean;

  constructor(
    fetchPage: (page: number, perPage: number) => Promise<[T[], number]>,
    options: { perPage?: number; limit?: number; startPage?: number } = {},
  ) {
    const perPage = options.perPage ?? PAGE_MAX;
    if (perPage < 1 || perPage > PAGE_MAX) {
      throw new RangeError(`perPage must be between 1 and ${PAGE_MAX}`);
    }
    if (options.limit !== undefined && options.limit < 0) {
      throw new RangeError("limit must be >= 0");
    }
    this.fetchPage = fetchPage;
    this.perPage = perPage;
    this.limit = options.limit;
    this.page = options.startPage ?? 1;
    this.yielded = 0;
    this.buffer = [];
    this.bufferIdx = 0;
    this.total = 0;
    this.shortPage = false;
  }

  [Symbol.asyncIterator](): AsyncIterableIterator<T> {
    return this;
  }

  async next(): Promise<IteratorResult<T>> {
    // Serve from the in-memory buffer first.
    while (true) {
      if (this.limit !== undefined && this.yielded >= this.limit) {
        return { value: undefined, done: true };
      }

      if (this.bufferIdx < this.buffer.length) {
        const item = this.buffer[this.bufferIdx]!;
        this.bufferIdx += 1;
        this.yielded += 1;
        return { value: item, done: false };
      }

      // Buffer exhausted. Decide whether to fetch the next page.
      if (this.yielded > 0 && this.yielded >= this.total) {
        return { value: undefined, done: true };
      }
      if (this.shortPage) {
        return { value: undefined, done: true };
      }

      const [items, total] = await this.fetchPage(this.page, this.perPage);
      if (items.length === 0) {
        return { value: undefined, done: true };
      }
      this.buffer = items;
      this.bufferIdx = 0;
      this.total = total;
      this.shortPage = items.length < this.perPage;
      this.page += 1;
    }
  }
}

/** Async iterator over a limit/offset-based endpoint (reforms). */
export class OffsetIterator<T> implements AsyncIterableIterator<T> {
  private readonly fetchPage: (limit: number, offset: number) => Promise<[T[], number]>;
  private readonly batch: number;
  private readonly limit: number | undefined;
  private offset: number;
  private yielded: number;
  private buffer: T[];
  private bufferIdx: number;
  private done: boolean;

  constructor(
    fetchPage: (limit: number, offset: number) => Promise<[T[], number]>,
    options: { batch?: number; limit?: number; startOffset?: number } = {},
  ) {
    const batch = options.batch ?? 100;
    if (batch < 1) {
      throw new RangeError("batch must be >= 1");
    }
    if (options.limit !== undefined && options.limit < 0) {
      throw new RangeError("limit must be >= 0");
    }
    this.fetchPage = fetchPage;
    this.batch = batch;
    this.limit = options.limit;
    this.offset = options.startOffset ?? 0;
    this.yielded = 0;
    this.buffer = [];
    this.bufferIdx = 0;
    this.done = false;
  }

  [Symbol.asyncIterator](): AsyncIterableIterator<T> {
    return this;
  }

  async next(): Promise<IteratorResult<T>> {
    while (true) {
      if (this.limit !== undefined && this.yielded >= this.limit) {
        return { value: undefined, done: true };
      }

      // Serve from the current batch buffer first.
      if (this.bufferIdx < this.buffer.length) {
        const item = this.buffer[this.bufferIdx]!;
        this.bufferIdx += 1;
        this.yielded += 1;
        return { value: item, done: false };
      }

      // Buffer drained. If a prior batch told us we were done, stop.
      if (this.done) return { value: undefined, done: true };

      const [items, total] = await this.fetchPage(this.batch, this.offset);
      if (items.length === 0) {
        this.done = true;
        return { value: undefined, done: true };
      }
      this.buffer = items;
      this.bufferIdx = 0;
      this.offset += items.length;
      // Flag termination for the next round-trip; still serve this batch.
      if (this.offset >= total) this.done = true;
      else if (items.length < this.batch) this.done = true;
    }
  }
}
