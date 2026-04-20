package legalize

import (
	"context"
	"net/http"
)

// JurisdictionsService exposes /api/v1/{country}/jurisdictions.
type JurisdictionsService struct {
	client *Client
}

// List returns the jurisdictions registered for a country.
func (s *JurisdictionsService) List(ctx context.Context, country string) ([]JurisdictionInfo, error) {
	var out []JurisdictionInfo
	if err := s.client.requestJSON(ctx, http.MethodGet, API+"/"+country+"/jurisdictions", nil, &out); err != nil {
		return nil, err
	}
	return out, nil
}
