package legalize

import (
	"context"
	"net/http"
)

// ReformsService exposes /api/v1/{country}/laws/{law_id}/reforms.
type ReformsService struct {
	client *Client
}

// ReformsListOptions controls pagination. Both fields are optional.
type ReformsListOptions struct {
	Limit  *int
	Offset *int
}

// List returns a single page of reforms for a law.
func (s *ReformsService) List(ctx context.Context, country, lawID string, opts *ReformsListOptions) (*ReformsResponse, error) {
	params := map[string]any{}
	if opts != nil {
		if opts.Limit != nil {
			params["limit"] = opts.Limit
		}
		if opts.Offset != nil {
			params["offset"] = opts.Offset
		}
	}
	var out ReformsResponse
	if err := s.client.requestJSON(ctx, http.MethodGet,
		API+"/"+country+"/laws/"+lawID+"/reforms",
		[]RequestOption{WithParams(params)}, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Iter returns an auto-paginator over every reform for a law.
// batch clamps to min 1; pass 0 for the SDK default (100).
func (s *ReformsService) Iter(ctx context.Context, country, lawID string, batch, limit int) *ReformsIter {
	fetch := func(ctx context.Context, b, offset int) ([]Reform, int, error) {
		bPtr, oPtr := b, offset
		resp, err := s.List(ctx, country, lawID, &ReformsListOptions{Limit: &bPtr, Offset: &oPtr})
		if err != nil {
			return nil, 0, err
		}
		return resp.Reforms, resp.Total, nil
	}
	return newReformsIter(fetch, batch, limit)
}
