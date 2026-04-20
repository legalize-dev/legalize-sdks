package legalize

// This file holds the Go structs corresponding to the Legalize API
// schemas defined in sdk/openapi-sdk.json. A future pass may generate
// it with oapi-codegen; until then it is hand-maintained to keep the
// runtime dependency surface at zero.

// Commit is a single git commit in a law's history.
type Commit struct {
	SHA     string `json:"sha"`
	Date    string `json:"date"`
	Message string `json:"message"`
}

// CommitsResponse is the return payload of laws.commits.
type CommitsResponse struct {
	LawID   string   `json:"law_id"`
	Commits []Commit `json:"commits"`
}

// CountryInfo is a single row in the countries.list response.
type CountryInfo struct {
	Country string `json:"country"`
	Count   int    `json:"count"`
}

// JurisdictionInfo is a single row in the jurisdictions.list response.
// Jurisdiction is a pointer so callers can distinguish "national" (nil)
// from an empty string.
type JurisdictionInfo struct {
	Jurisdiction *string `json:"jurisdiction"`
	Count        int     `json:"count"`
}

// LawAtCommitResponse is the return payload of laws.at_commit.
type LawAtCommitResponse struct {
	LawID     string `json:"law_id"`
	SHA       string `json:"sha"`
	ContentMD string `json:"content_md"`
}

// LawDetail is a full law with Markdown content.
type LawDetail struct {
	ID              string         `json:"id"`
	Title           string         `json:"title"`
	Country         string         `json:"country"`
	LawType         string         `json:"law_type"`
	ShortTitle      *string        `json:"short_title,omitempty"`
	Status          *string        `json:"status,omitempty"`
	PublicationDate *string        `json:"publication_date,omitempty"`
	Jurisdiction    *string        `json:"jurisdiction,omitempty"`
	ArticleCount    *int           `json:"article_count,omitempty"`
	ContentMD       *string        `json:"content_md,omitempty"`
	Department      *string        `json:"department,omitempty"`
	Source          *string        `json:"source,omitempty"`
	LastUpdated     *string        `json:"last_updated,omitempty"`
	Extra           map[string]any `json:"extra,omitempty"`
	Frontmatter     map[string]any `json:"frontmatter,omitempty"`
}

// LawMeta is law metadata without content — fast, no GitHub fetch.
type LawMeta struct {
	ID              string         `json:"id"`
	Title           string         `json:"title"`
	Country         string         `json:"country"`
	LawType         string         `json:"law_type"`
	ShortTitle      *string        `json:"short_title,omitempty"`
	Status          *string        `json:"status,omitempty"`
	PublicationDate *string        `json:"publication_date,omitempty"`
	Jurisdiction    *string        `json:"jurisdiction,omitempty"`
	ArticleCount    *int           `json:"article_count,omitempty"`
	Department      *string        `json:"department,omitempty"`
	Source          *string        `json:"source,omitempty"`
	LastUpdated     *string        `json:"last_updated,omitempty"`
	Extra           map[string]any `json:"extra,omitempty"`
}

// LawSearchResult is the per-item shape of a paginated law listing.
type LawSearchResult struct {
	ID              string  `json:"id"`
	Title           string  `json:"title"`
	Country         string  `json:"country"`
	LawType         string  `json:"law_type"`
	ShortTitle      *string `json:"short_title,omitempty"`
	Status          *string `json:"status,omitempty"`
	PublicationDate *string `json:"publication_date,omitempty"`
	Jurisdiction    *string `json:"jurisdiction,omitempty"`
	ArticleCount    *int    `json:"article_count,omitempty"`
	TitleSnippet    *string `json:"title_snippet,omitempty"`
}

// PaginatedLaws is the unified response for both law listing and
// full-text search.
type PaginatedLaws struct {
	Country      string            `json:"country"`
	Total        int               `json:"total"`
	Page         int               `json:"page"`
	PerPage      int               `json:"per_page"`
	Results      []LawSearchResult `json:"results"`
	Count        *int              `json:"count,omitempty"`
	Query        *string           `json:"query,omitempty"`
	Sort         *string           `json:"sort,omitempty"`
	Jurisdiction *string           `json:"jurisdiction,omitempty"`
	FromDate     *string           `json:"from_date,omitempty"`
	ToDate       *string           `json:"to_date,omitempty"`
}

// Reform is a single legislative amendment.
type Reform struct {
	Date             string  `json:"date"`
	SourceID         *string `json:"source_id,omitempty"`
	ArticlesAffected *string `json:"articles_affected,omitempty"`
}

// ReformsResponse is the return payload of reforms.list.
type ReformsResponse struct {
	LawID   string   `json:"law_id"`
	Total   int      `json:"total"`
	Offset  int      `json:"offset"`
	Limit   int      `json:"limit"`
	Reforms []Reform `json:"reforms"`
}

// StatsResponse is the return payload of stats.retrieve.
type StatsResponse struct {
	Country              string           `json:"country"`
	Jurisdiction         *string          `json:"jurisdiction,omitempty"`
	LawTypes             []string         `json:"law_types"`
	MostReformedLaws     []map[string]any `json:"most_reformed_laws"`
	ReformActivityByYear []map[string]any `json:"reform_activity_by_year"`
}

// WebhookEndpointCreate is the create-endpoint request body.
type WebhookEndpointCreate struct {
	URL         string   `json:"url"`
	EventTypes  []string `json:"event_types"`
	Countries   []string `json:"countries,omitempty"`
	Description string   `json:"description,omitempty"`
}

// WebhookEndpointUpdate is the patch-endpoint request body.
type WebhookEndpointUpdate struct {
	URL         *string  `json:"url,omitempty"`
	EventTypes  []string `json:"event_types,omitempty"`
	Countries   []string `json:"countries,omitempty"`
	Description *string  `json:"description,omitempty"`
	Enabled     *bool    `json:"enabled,omitempty"`
}

// WebhookEndpoint is the canonical response shape for endpoint reads.
// Fields not present in the OpenAPI spec's 200 response are typed
// loosely to match server additions without breaking clients.
type WebhookEndpoint = map[string]any

// WebhookDelivery is a single delivery attempt record.
type WebhookDelivery = map[string]any

// WebhookDeliveriesResponse is returned by webhooks.deliveries.
type WebhookDeliveriesResponse = map[string]any
