/** `/api/v1/{country}/law-types` — law types per country. */

import type { Legalize } from "../client.js";

const API = "/api/v1";

export class LawTypes {
  private readonly client: Legalize;
  constructor(client: Legalize) {
    this.client = client;
  }

  /** List law type identifiers (e.g. `["constitucion", "ley", "real_decreto"]`). */
  async list(country: string, options: { signal?: AbortSignal } = {}): Promise<string[]> {
    return this.client.request<string[]>("GET", `${API}/${country}/law-types`, {
      ...(options.signal ? { signal: options.signal } : {}),
    });
  }
}
