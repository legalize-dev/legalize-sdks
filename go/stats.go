package legalize

import (
	"context"
	"net/http"
)

// StatsService exposes /api/v1/{country}/stats.
type StatsService struct {
	client *Client
}

// StatsOptions holds optional filters for stats.Retrieve.
type StatsOptions struct {
	// Jurisdiction scopes the statistics to one jurisdiction: a region code, or
	// JurisdictionNational for the norms of the state itself.
	Jurisdiction *string
}

// Retrieve returns aggregate statistics for a country.
func (s *StatsService) Retrieve(ctx context.Context, country string, opts *StatsOptions) (*StatsResponse, error) {
	params := map[string]any{}
	if opts != nil && opts.Jurisdiction != nil {
		params["jurisdiction"] = opts.Jurisdiction
	}
	var out StatsResponse
	if err := s.client.requestJSON(ctx, http.MethodGet, API+"/"+country+"/stats",
		[]RequestOption{WithParams(params)}, &out); err != nil {
		return nil, err
	}
	return &out, nil
}
