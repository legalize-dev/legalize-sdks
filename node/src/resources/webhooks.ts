/**
 * `/api/v1/webhooks` — endpoint management + delivery history + test ping.
 *
 * The management endpoints (this file) require Pro+ tier. The webhook
 * signature verification utility lives in `webhooks.ts` at the package
 * root — it runs on the recipient's server and doesn't touch this API.
 */

import type { Legalize } from "../client.js";
import type {
  WebhookCreateOptions,
  WebhookDeliveriesOptions,
  WebhookDeliveriesPage,
  WebhookDelivery,
  WebhookEndpoint,
  WebhookUpdateOptions,
} from "../types.js";

const API = "/api/v1";

const VALID_STATUSES = new Set(["failed", "success", "pending"]);

export class Webhooks {
  private readonly client: Legalize;
  constructor(client: Legalize) {
    this.client = client;
  }

  /** Create a webhook endpoint. Returns the signing secret ONCE. */
  async create(
    options: WebhookCreateOptions & { signal?: AbortSignal },
  ): Promise<WebhookEndpoint> {
    const body: Record<string, unknown> = {
      url: options.url,
      event_types: options.eventTypes,
      countries: options.countries ?? null,
      description: options.description ?? "",
    };
    return this.client.request<WebhookEndpoint>("POST", `${API}/webhooks`, {
      json: body,
      ...(options.signal ? { signal: options.signal } : {}),
    });
  }

  /** List all webhook endpoints for the authenticated org. */
  async list(options: { signal?: AbortSignal } = {}): Promise<WebhookEndpoint[]> {
    return this.client.request<WebhookEndpoint[]>("GET", `${API}/webhooks`, {
      ...(options.signal ? { signal: options.signal } : {}),
    });
  }

  /** Fetch a single endpoint by id. */
  async retrieve(
    endpointId: number,
    options: { signal?: AbortSignal } = {},
  ): Promise<WebhookEndpoint> {
    return this.client.request<WebhookEndpoint>("GET", `${API}/webhooks/${endpointId}`, {
      ...(options.signal ? { signal: options.signal } : {}),
    });
  }

  /** Patch mutable fields on a webhook endpoint. */
  async update(
    endpointId: number,
    options: WebhookUpdateOptions & { signal?: AbortSignal },
  ): Promise<WebhookEndpoint> {
    const body: Record<string, unknown> = {};
    if (options.url !== undefined) body.url = options.url;
    if (options.eventTypes !== undefined) body.event_types = options.eventTypes;
    if (options.countries !== undefined) body.countries = options.countries;
    if (options.description !== undefined) body.description = options.description;
    if (options.enabled !== undefined) body.enabled = options.enabled;
    return this.client.request<WebhookEndpoint>("PATCH", `${API}/webhooks/${endpointId}`, {
      json: body,
      ...(options.signal ? { signal: options.signal } : {}),
    });
  }

  /** Delete a webhook endpoint. */
  async delete(
    endpointId: number,
    options: { signal?: AbortSignal } = {},
  ): Promise<Record<string, unknown>> {
    return this.client.request<Record<string, unknown>>(
      "DELETE",
      `${API}/webhooks/${endpointId}`,
      { ...(options.signal ? { signal: options.signal } : {}) },
    );
  }

  /** List delivery attempts for an endpoint, optionally filtered by status. */
  async deliveries(
    endpointId: number,
    options: WebhookDeliveriesOptions & { signal?: AbortSignal } = {},
  ): Promise<WebhookDeliveriesPage> {
    if (options.status !== undefined && !VALID_STATUSES.has(options.status)) {
      throw new TypeError(
        "status must be 'failed', 'success', 'pending', or omitted",
      );
    }
    const params: Record<string, unknown> = {
      page: options.page ?? 1,
      status: options.status,
    };
    return this.client.request<WebhookDeliveriesPage>(
      "GET",
      `${API}/webhooks/${endpointId}/deliveries`,
      { params, ...(options.signal ? { signal: options.signal } : {}) },
    );
  }

  /** Retry a failed delivery. */
  async retry(
    endpointId: number,
    deliveryId: number,
    options: { signal?: AbortSignal } = {},
  ): Promise<WebhookDelivery> {
    return this.client.request<WebhookDelivery>(
      "POST",
      `${API}/webhooks/${endpointId}/deliveries/${deliveryId}/retry`,
      { ...(options.signal ? { signal: options.signal } : {}) },
    );
  }

  /** Send a `test.ping` event to verify the endpoint is reachable. */
  async test(
    endpointId: number,
    options: { signal?: AbortSignal } = {},
  ): Promise<WebhookDelivery> {
    return this.client.request<WebhookDelivery>(
      "POST",
      `${API}/webhooks/${endpointId}/test`,
      { ...(options.signal ? { signal: options.signal } : {}) },
    );
  }
}
