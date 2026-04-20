/** `/api/v1/countries` — list every country the API serves. */

import type { Legalize } from "../client.js";
import type { CountryInfo } from "../types.js";

const API = "/api/v1";

export class Countries {
  private readonly client: Legalize;
  constructor(client: Legalize) {
    this.client = client;
  }

  /** Return every country the API serves, with law counts. */
  async list(options: { signal?: AbortSignal } = {}): Promise<CountryInfo[]> {
    return this.client.request<CountryInfo[]>("GET", `${API}/countries`, {
      ...(options.signal ? { signal: options.signal } : {}),
    });
  }
}
