/**
 * Legalize — official Node client for the Legalize API.
 *
 * Typical usage:
 *
 *   import { Legalize } from "legalize";
 *
 *   const client = new Legalize({ apiKey: "leg_..." });
 *   for await (const law of client.laws.iter("es", { lawType: "ley_organica" })) {
 *     console.log(law.id, law.title);
 *   }
 *
 * See https://legalize.dev/api/docs for the API reference.
 */

export { Legalize, defaultUserAgent, buildQueryString } from "./client.js";
export type { FetchImpl, LegalizeOptions, RequestOptions } from "./client.js";

export {
  DEFAULT_API_VERSION,
  DEFAULT_BASE_URL,
  DEFAULT_TIMEOUT,
  KEY_PREFIX,
  resolveApiKey,
  resolveApiVersion,
  resolveBaseUrl,
} from "./env.js";

export {
  APIError,
  APIConnectionError,
  APITimeoutError,
  AuthenticationError,
  ForbiddenError,
  InvalidRequestError,
  LegalizeError,
  NotFoundError,
  RateLimitError,
  ServerError,
  ServiceUnavailableError,
  ValidationError,
  WebhookVerificationError,
} from "./errors.js";
export type { APIErrorOptions, WebhookVerificationReason } from "./errors.js";

export {
  DEFAULT_BACKOFF_FACTOR,
  DEFAULT_INITIAL_DELAY,
  DEFAULT_MAX_DELAY,
  DEFAULT_MAX_RETRIES,
  IDEMPOTENT_METHODS,
  RETRY_STATUSES,
  RetryPolicy,
  parseRetryAfter,
  sleep,
} from "./retry.js";
export type { RetryPolicyOptions } from "./retry.js";

export { OffsetIterator, PAGE_MAX, PageIterator } from "./pagination.js";

export { Webhook, DEFAULT_TOLERANCE_SECONDS } from "./webhooks.js";
export type { WebhookEvent, WebhookVerifyOptions } from "./webhooks.js";

export { Countries } from "./resources/countries.js";
export { Jurisdictions } from "./resources/jurisdictions.js";
export { Laws } from "./resources/laws.js";
export { LawTypes } from "./resources/lawTypes.js";
export { Reforms } from "./resources/reforms.js";
export { Stats } from "./resources/stats.js";
export { Webhooks } from "./resources/webhooks.js";

export type {
  ApiValidationError,
  Commit,
  CommitsResponse,
  CountryInfo,
  HTTPValidationError,
  JurisdictionInfo,
  LawAtCommitResponse,
  LawDetail,
  LawFilterOptions,
  LawIterOptions,
  LawListOptions,
  LawMeta,
  LawSearchOptions,
  LawSearchResult,
  LawSort,
  PaginatedLaws,
  Reform,
  ReformIterOptions,
  ReformListOptions,
  ReformsResponse,
  StatsOptions,
  StatsResponse,
  WebhookCreateOptions,
  WebhookDeliveriesOptions,
  WebhookDeliveriesPage,
  WebhookDelivery,
  WebhookDeliveryStatus,
  WebhookEndpoint,
  WebhookEndpointCreate,
  WebhookEndpointUpdate,
  WebhookUpdateOptions,
} from "./types.js";

export { SDK_VERSION } from "./version.js";
