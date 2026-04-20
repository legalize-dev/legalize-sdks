/** `/api/v1/{country}/laws/{law_id}/reforms` — reform history. */

import type { Legalize } from "../client.js";
import { OffsetIterator } from "../pagination.js";
import type { Reform, ReformIterOptions, ReformListOptions, ReformsResponse } from "../types.js";

const API = "/api/v1";

export class Reforms {
  private readonly client: Legalize;
  constructor(client: Legalize) {
    this.client = client;
  }

  /** Return a single page of reforms for a law. */
  async list(
    country: string,
    lawId: string,
    options: ReformListOptions & { signal?: AbortSignal } = {},
  ): Promise<ReformsResponse> {
    const params: Record<string, unknown> = {
      limit: options.limit ?? 100,
      offset: options.offset ?? 0,
    };
    return this.client.request<ReformsResponse>(
      "GET",
      `${API}/${country}/laws/${lawId}/reforms`,
      { params, ...(options.signal ? { signal: options.signal } : {}) },
    );
  }

  /** Auto-paginate across every reform for a law. */
  iter(
    country: string,
    lawId: string,
    options: ReformIterOptions & { signal?: AbortSignal } = {},
  ): AsyncIterableIterator<Reform> {
    const batch = options.batch ?? 100;
    const limit = options.limit;
    const fetchPage = async (limitArg: number, offset: number): Promise<[Reform[], number]> => {
      const listOpts: ReformListOptions & { signal?: AbortSignal } = {
        limit: limitArg,
        offset,
      };
      if (options.signal) listOpts.signal = options.signal;
      const resp = await this.list(country, lawId, listOpts);
      return [resp.reforms, resp.total];
    };
    return new OffsetIterator(fetchPage, { batch, ...(limit !== undefined ? { limit } : {}) });
  }
}
