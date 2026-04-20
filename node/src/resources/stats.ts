/** `/api/v1/{country}/stats` — aggregate statistics for a country. */

import type { Legalize } from "../client.js";
import type { StatsOptions, StatsResponse } from "../types.js";

const API = "/api/v1";

export class Stats {
  private readonly client: Legalize;
  constructor(client: Legalize) {
    this.client = client;
  }

  /** Return aggregate stats for a country (and optionally a jurisdiction). */
  async retrieve(
    country: string,
    options: StatsOptions & { signal?: AbortSignal } = {},
  ): Promise<StatsResponse> {
    const params: Record<string, unknown> = { jurisdiction: options.jurisdiction };
    return this.client.request<StatsResponse>("GET", `${API}/${country}/stats`, {
      params,
      ...(options.signal ? { signal: options.signal } : {}),
    });
  }
}
