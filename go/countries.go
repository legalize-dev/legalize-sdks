package legalize

import (
	"context"
	"net/http"
)

// CountriesService exposes /api/v1/countries.
type CountriesService struct {
	client *Client
}

// List returns every country the API serves, with law counts.
func (s *CountriesService) List(ctx context.Context) ([]CountryInfo, error) {
	var out []CountryInfo
	if err := s.client.requestJSON(ctx, http.MethodGet, API+"/countries", nil, &out); err != nil {
		return nil, err
	}
	return out, nil
}
