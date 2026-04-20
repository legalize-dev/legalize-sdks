/**
 * Public response and request types.
 *
 * The underlying schemas live in `generated.ts` (produced by
 * `openapi-typescript` from `../openapi-sdk.json`). This file re-exports
 * the curated subset the SDK user interacts with, plus a few hand-written
 * helper types where OpenAPI generation is awkward.
 *
 * We preserve the server's `snake_case` field names on response objects
 * to match the wire format byte-for-byte — same philosophy as the Python
 * SDK, which keeps Pydantic aliases and populates fields from the raw
 * JSON directly.
 */

import type { components } from "./generated.js";

// -------- Response types (curated re-exports) ---------------------------

export type CountryInfo = components["schemas"]["CountryInfo"];
export type JurisdictionInfo = components["schemas"]["JurisdictionInfo"];
export type Commit = components["schemas"]["Commit"];
export type CommitsResponse = components["schemas"]["CommitsResponse"];
export type LawAtCommitResponse = components["schemas"]["LawAtCommitResponse"];
export type LawDetail = components["schemas"]["LawDetail"];
export type LawMeta = components["schemas"]["LawMeta"];
export type LawSearchResult = components["schemas"]["LawSearchResult"];
export type PaginatedLaws = components["schemas"]["PaginatedLaws"];
export type Reform = components["schemas"]["Reform"];
export type ReformsResponse = components["schemas"]["ReformsResponse"];
export type StatsResponse = components["schemas"]["StatsResponse"];
export type ApiValidationError = components["schemas"]["ValidationError"];
export type HTTPValidationError = components["schemas"]["HTTPValidationError"];
export type WebhookEndpointCreate = components["schemas"]["WebhookEndpointCreate"];
export type WebhookEndpointUpdate = components["schemas"]["WebhookEndpointUpdate"];

// -------- Hand-written helper types --------------------------------------

/**
 * Law listing sort options.
 *
 * The OpenAPI schema types this as `string` but the server enforces a
 * specific allowed set. We keep it open (`string`) to tolerate server
 * additions without bumping the SDK, but document the current values.
 */
export type LawSort =
  | "publication_date"
  | "-publication_date"
  | "last_updated"
  | "-last_updated"
  | "title"
  | "-title"
  // Forward-compat:
  | (string & {});

/** Options shared by `laws.list` and `laws.iter` filter surfaces. */
export interface LawFilterOptions {
  lawType?: string | string[];
  year?: number;
  status?: string;
  jurisdiction?: string;
  fromDate?: string;
  toDate?: string;
  sort?: LawSort;
}

export interface LawListOptions extends LawFilterOptions {
  page?: number;
  perPage?: number;
}

export interface LawSearchOptions extends LawFilterOptions {
  page?: number;
  perPage?: number;
}

export interface LawIterOptions extends LawFilterOptions {
  perPage?: number;
  limit?: number;
}

export interface ReformListOptions {
  limit?: number;
  offset?: number;
}

export interface ReformIterOptions {
  batch?: number;
  limit?: number;
}

export interface StatsOptions {
  jurisdiction?: string;
}

/** Webhook endpoint CRUD types — server-side response. */
export interface WebhookEndpoint {
  id: number;
  url: string;
  event_types: string[];
  countries?: string[] | null;
  description?: string;
  enabled?: boolean;
  created_at?: string;
  /** Only populated on creation, never on list/retrieve. */
  secret?: string;
  [key: string]: unknown;
}

export interface WebhookDeliveriesPage {
  total: number;
  deliveries: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

export interface WebhookDelivery {
  id: number;
  status: string;
  [key: string]: unknown;
}

export type WebhookDeliveryStatus = "failed" | "success" | "pending";

export interface WebhookCreateOptions {
  url: string;
  eventTypes: string[];
  countries?: string[];
  description?: string;
}

export interface WebhookUpdateOptions {
  url?: string;
  eventTypes?: string[];
  countries?: string[];
  description?: string;
  enabled?: boolean;
}

export interface WebhookDeliveriesOptions {
  page?: number;
  status?: WebhookDeliveryStatus;
}
