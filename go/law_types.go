package legalize

import (
	"context"
	"net/http"
)

// LawTypesService exposes /api/v1/{country}/law-types.
type LawTypesService struct {
	client *Client
}

// List returns the law-type codes defined for a country (e.g. "ley",
// "real_decreto", "constitucion").
func (s *LawTypesService) List(ctx context.Context, country string) ([]string, error) {
	var out []string
	if err := s.client.requestJSON(ctx, http.MethodGet, API+"/"+country+"/law-types", nil, &out); err != nil {
		return nil, err
	}
	return out, nil
}
