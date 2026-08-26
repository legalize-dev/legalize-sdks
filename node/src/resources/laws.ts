/**
 * `/api/v1/{country}/laws` and sub-resources.
 *
 * Covers:
 *   - `list` / `search` — listing vs. full-text search
 *   - `iter` / `searchIter` — auto-paginated async iterators
 *   - `retrieve` — full law with Markdown content
 *   - `meta` — metadata only (fast, no GitHub fetch)
 *   - `commits` — git commit history
 *   - `atCommit` — time-travel to a specific SHA
 *   - `atDate` — time-travel to a date, SHA resolved server-side
 */

import type { Legalize } from "../client.js";
import { PageIterator } from "../pagination.js";
import type {
  CommitsResponse,
  LawAtCommitResponse,
  LawAtDateResponse,
  LawDetail,
  LawIterOptions,
  LawListOptions,
  LawMeta,
  LawSearchOptions,
  LawSearchResult,
  PaginatedLaws,
} from "../types.js";

const API = "/api/v1";

function buildFilterParams(
  opts: LawIterOptions | LawListOptions | LawSearchOptions,
  extras: Record<string, unknown>,
): Record<string, unknown> {
  return {
    law_type: opts.lawType,
    year: opts.year,
    status: opts.status,
    jurisdiction: opts.jurisdiction,
    from_date: opts.fromDate,
    to_date: opts.toDate,
    sort: opts.sort,
    text_state: opts.textState,
    ...extras,
  };
}

export class Laws {
  private readonly client: Legalize;
  constructor(client: Legalize) {
    this.client = client;
  }

  /** Return a single page of laws for a country. */
  async list(
    country: string,
    options: LawListOptions & { signal?: AbortSignal } = {},
  ): Promise<PaginatedLaws> {
    const params = buildFilterParams(options, {
      page: options.page ?? 1,
      per_page: options.perPage ?? 50,
    });
    return this.client.request<PaginatedLaws>("GET", `${API}/${country}/laws`, {
      params,
      ...(options.signal ? { signal: options.signal } : {}),
    });
  }

  /** Full-text search for laws. `q` is required. */
  async search(
    country: string,
    q: string,
    options: LawSearchOptions & { signal?: AbortSignal } = {},
  ): Promise<PaginatedLaws> {
    if (!q || !q.trim()) {
      throw new TypeError("q must be a non-empty search query");
    }
    const params = buildFilterParams(options, {
      page: options.page ?? 1,
      per_page: options.perPage ?? 50,
      q,
    });
    return this.client.request<PaginatedLaws>("GET", `${API}/${country}/laws`, {
      params,
      ...(options.signal ? { signal: options.signal } : {}),
    });
  }

  /** Auto-paginate across every matching law. */
  iter(
    country: string,
    options: LawIterOptions & { signal?: AbortSignal } = {},
  ): AsyncIterableIterator<LawSearchResult> {
    const { perPage: _perPage, limit, ...filters } = options;
    const perPage = options.perPage ?? 100;
    const fetchPage = async (page: number, per: number): Promise<[LawSearchResult[], number]> => {
      // Forward the filters, never re-list them. Rebuilding this object field
      // by field is how `textState` came to be dropped here while `list` and
      // `search` honored it: every field is optional, so the compiler saw a
      // valid LawListOptions and said nothing, and the mocked unit tests only
      // covered the two methods that were right.
      const listOpts: LawListOptions & { signal?: AbortSignal } = {
        ...filters,
        page,
        perPage: per,
      };
      const resp = await this.list(country, listOpts);
      return [resp.results, resp.total];
    };
    return new PageIterator(fetchPage, { perPage, ...(limit !== undefined ? { limit } : {}) });
  }

  /** Auto-paginate across every match of a full-text search. */
  searchIter(
    country: string,
    q: string,
    options: LawIterOptions & { signal?: AbortSignal } = {},
  ): AsyncIterableIterator<LawSearchResult> {
    if (!q || !q.trim()) {
      throw new TypeError("q must be a non-empty search query");
    }
    const { perPage: _perPage, limit, ...filters } = options;
    const perPage = options.perPage ?? 100;
    const fetchPage = async (page: number, per: number): Promise<[LawSearchResult[], number]> => {
      // Same forwarding rule as iter — see the comment there.
      const searchOpts: LawSearchOptions & { signal?: AbortSignal } = {
        ...filters,
        page,
        perPage: per,
      };
      const resp = await this.search(country, q, searchOpts);
      return [resp.results, resp.total];
    };
    return new PageIterator(fetchPage, { perPage, ...(limit !== undefined ? { limit } : {}) });
  }

  /** Fetch the full law including Markdown content. */
  async retrieve(
    country: string,
    lawId: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<LawDetail> {
    return this.client.request<LawDetail>("GET", `${API}/${country}/laws/${lawId}`, {
      ...(options.signal ? { signal: options.signal } : {}),
    });
  }

  /** Fetch only the law metadata (no content). */
  async meta(
    country: string,
    lawId: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<LawMeta> {
    return this.client.request<LawMeta>("GET", `${API}/${country}/laws/${lawId}/meta`, {
      ...(options.signal ? { signal: options.signal } : {}),
    });
  }

  /** Git commit history for the law. */
  async commits(
    country: string,
    lawId: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<CommitsResponse> {
    return this.client.request<CommitsResponse>(
      "GET",
      `${API}/${country}/laws/${lawId}/commits`,
      { ...(options.signal ? { signal: options.signal } : {}) },
    );
  }

  /** Return the law's full text at a specific historical version. */
  async atCommit(
    country: string,
    lawId: string,
    sha: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<LawAtCommitResponse> {
    return this.client.request<LawAtCommitResponse>(
      "GET",
      `${API}/${country}/laws/${lawId}/at/${sha}`,
      { ...(options.signal ? { signal: options.signal } : {}) },
    );
  }

  /**
   * Return the law's full text as published on or before `date`.
   *
   * The server resolves the date to a version, so callers need not walk
   * {@link commits} looking for a SHA. The response carries the resolved
   * `sha` and `versionDate` so the answer stays verifiable.
   *
   * The rule is *published on or before* `date`, not *in force on* it: the
   * dates are official publication dates, so a reform still inside its
   * vacatio legis resolves as already applying. Cite accordingly.
   *
   * @param date - Point in time as `YYYY-MM-DD`.
   */
  async atDate(
    country: string,
    lawId: string,
    date: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<LawAtDateResponse> {
    return this.client.request<LawAtDateResponse>(
      "GET",
      `${API}/${country}/laws/${lawId}/at`,
      {
        params: { date },
        ...(options.signal ? { signal: options.signal } : {}),
      },
    );
  }
}
