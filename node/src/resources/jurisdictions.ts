/** `/api/v1/{country}/jurisdictions` — regions/states within a country. */

import type { Legalize } from "../client.js";
import type { JurisdictionInfo } from "../types.js";

const API = "/api/v1";

export class Jurisdictions {
  private readonly client: Legalize;
  constructor(client: Legalize) {
    this.client = client;
  }

  /** List jurisdictions for a country (e.g. Spain's comunidades). */
  async list(
    country: string,
    options: { signal?: AbortSignal } = {},
  ): Promise<JurisdictionInfo[]> {
    return this.client.request<JurisdictionInfo[]>("GET", `${API}/${country}/jurisdictions`, {
      ...(options.signal ? { signal: options.signal } : {}),
    });
  }
}
