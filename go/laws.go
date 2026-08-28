package legalize

import (
	"context"
	"errors"
	"net/http"
)

// LawsService exposes /api/v1/{country}/laws and sub-resources.
type LawsService struct {
	client *Client
}

// LawsListOptions controls the filters applied to laws.List and
// friends. All fields are optional; nil/zero means "don't filter by
// this dimension". Use legalize.String / Int helpers to set scalars
// inline.
type LawsListOptions struct {
	Page    *int
	PerPage *int
	LawType []string
	Year    *int
	Status  *string
	// Jurisdiction keeps only laws from one jurisdiction: a region code, or
	// JurisdictionNational for the norms of the state itself. Nil returns both
	// together, which is what this endpoint has always done.
	Jurisdiction *string
	FromDate     *string
	ToDate       *string
	Sort         *string
	// TextState keeps only laws whose body is in that state — one of
	// TextStatePointInTime, TextStateCurrent, TextStateAsEnacted. Nil returns
	// every state, which is what this endpoint has always done.
	TextState *string
}

func (o *LawsListOptions) params() map[string]any {
	if o == nil {
		return map[string]any{}
	}
	return map[string]any{
		"page":         o.Page,
		"per_page":     o.PerPage,
		"law_type":     o.LawType,
		"year":         o.Year,
		"status":       o.Status,
		"jurisdiction": o.Jurisdiction,
		"from_date":    o.FromDate,
		"to_date":      o.ToDate,
		"sort":         o.Sort,
		"text_state":   o.TextState,
	}
}

// List returns a single page of laws for a country.
func (s *LawsService) List(ctx context.Context, country string, opts *LawsListOptions) (*PaginatedLaws, error) {
	params := opts.params()
	var out PaginatedLaws
	if err := s.client.requestJSON(ctx, http.MethodGet, API+"/"+country+"/laws",
		[]RequestOption{WithParams(params)}, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Search issues a full-text search against a country's laws.
// q must be non-empty.
func (s *LawsService) Search(ctx context.Context, country, q string, opts *LawsListOptions) (*PaginatedLaws, error) {
	if q == "" {
		return nil, errors.New("legalize: q must be a non-empty search query")
	}
	params := opts.params()
	params["q"] = q
	var out PaginatedLaws
	if err := s.client.requestJSON(ctx, http.MethodGet, API+"/"+country+"/laws",
		[]RequestOption{WithParams(params)}, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Iter returns an auto-paginator over every matching law. The
// iterator fetches pages on demand — early exit is cost-free.
// perPage clamps to [1, 100]; pass 0 for the SDK default.
func (s *LawsService) Iter(ctx context.Context, country string, perPage, limit int, opts *LawsListOptions) *LawsIter {
	if perPage <= 0 {
		perPage = PageMax
	}
	fetch := func(ctx context.Context, page, per int) ([]LawSearchResult, int, error) {
		o := cloneLawsOpts(opts)
		p, pp := page, per
		o.Page = &p
		o.PerPage = &pp
		resp, err := s.List(ctx, country, o)
		if err != nil {
			return nil, 0, err
		}
		return resp.Results, resp.Total, nil
	}
	return newLawsIter(fetch, perPage, limit)
}

// SearchIter returns an auto-paginator over full-text search results.
func (s *LawsService) SearchIter(ctx context.Context, country, q string, perPage, limit int, opts *LawsListOptions) *LawsIter {
	if perPage <= 0 {
		perPage = PageMax
	}
	fetch := func(ctx context.Context, page, per int) ([]LawSearchResult, int, error) {
		o := cloneLawsOpts(opts)
		p, pp := page, per
		o.Page = &p
		o.PerPage = &pp
		resp, err := s.Search(ctx, country, q, o)
		if err != nil {
			return nil, 0, err
		}
		return resp.Results, resp.Total, nil
	}
	return newLawsIter(fetch, perPage, limit)
}

// Retrieve fetches a full law including its Markdown content.
func (s *LawsService) Retrieve(ctx context.Context, country, lawID string) (*LawDetail, error) {
	var out LawDetail
	if err := s.client.requestJSON(ctx, http.MethodGet, API+"/"+country+"/laws/"+lawID, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Meta fetches only the metadata for a law (fast — no GitHub hit).
func (s *LawsService) Meta(ctx context.Context, country, lawID string) (*LawMeta, error) {
	var out LawMeta
	if err := s.client.requestJSON(ctx, http.MethodGet, API+"/"+country+"/laws/"+lawID+"/meta", nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Commits returns the git commit history for a law.
func (s *LawsService) Commits(ctx context.Context, country, lawID string) (*CommitsResponse, error) {
	var out CommitsResponse
	if err := s.client.requestJSON(ctx, http.MethodGet, API+"/"+country+"/laws/"+lawID+"/commits", nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// AtCommit returns the law's full text at a specific historical
// version (time travel).
func (s *LawsService) AtCommit(ctx context.Context, country, lawID, sha string) (*LawAtCommitResponse, error) {
	var out LawAtCommitResponse
	if err := s.client.requestJSON(ctx, http.MethodGet, API+"/"+country+"/laws/"+lawID+"/at/"+sha, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// AtDate returns the law's full text as published on or before date
// (YYYY-MM-DD). The server resolves the date to a version, so callers need not
// walk Commits looking for a SHA; the resolved SHA and VersionDate come back
// with the text so the answer stays verifiable.
//
// The rule is "published on or before" date, not "in force on" it: the dates
// are official publication dates, so a reform still inside its vacatio legis
// resolves as already applying. Cite accordingly.
func (s *LawsService) AtDate(ctx context.Context, country, lawID, date string) (*LawAtDateResponse, error) {
	var out LawAtDateResponse
	if err := s.client.requestJSON(ctx, http.MethodGet, API+"/"+country+"/laws/"+lawID+"/at",
		[]RequestOption{WithParams(map[string]any{"date": date})}, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func cloneLawsOpts(opts *LawsListOptions) *LawsListOptions {
	if opts == nil {
		return &LawsListOptions{}
	}
	clone := *opts
	return &clone
}
