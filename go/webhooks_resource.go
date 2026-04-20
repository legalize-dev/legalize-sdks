package legalize

import (
	"context"
	"errors"
	"net/http"
	"strconv"
)

// WebhooksService exposes /api/v1/webhooks CRUD plus deliveries and
// test-ping helpers. For verifying incoming payloads on the recipient
// side, use the Verify function in this package.
type WebhooksService struct {
	client *Client
}

// WebhookCreateOptions is the body of webhooks.Create.
type WebhookCreateOptions struct {
	URL         string
	EventTypes  []string
	Countries   []string
	Description string
}

// Create registers a new webhook endpoint. Returns the endpoint
// payload including the one-time signing secret.
func (s *WebhooksService) Create(ctx context.Context, opts WebhookCreateOptions) (WebhookEndpoint, error) {
	body := WebhookEndpointCreate{
		URL:         opts.URL,
		EventTypes:  opts.EventTypes,
		Countries:   opts.Countries,
		Description: opts.Description,
	}
	var out WebhookEndpoint
	if err := s.client.requestJSON(ctx, http.MethodPost, API+"/webhooks",
		[]RequestOption{WithJSONBody(body)}, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// List returns every webhook endpoint owned by the authenticated org.
func (s *WebhooksService) List(ctx context.Context) ([]WebhookEndpoint, error) {
	var out []WebhookEndpoint
	if err := s.client.requestJSON(ctx, http.MethodGet, API+"/webhooks", nil, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// Retrieve fetches a single endpoint by id.
func (s *WebhooksService) Retrieve(ctx context.Context, endpointID int) (WebhookEndpoint, error) {
	var out WebhookEndpoint
	if err := s.client.requestJSON(ctx, http.MethodGet,
		API+"/webhooks/"+strconv.Itoa(endpointID), nil, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// WebhookUpdateOptions is the patch body for webhooks.Update.
type WebhookUpdateOptions struct {
	URL         *string
	EventTypes  []string
	Countries   []string
	Description *string
	Enabled     *bool
}

// Update patches an existing endpoint. Only non-nil fields on opts
// are sent, matching the server's partial-update semantics.
func (s *WebhooksService) Update(ctx context.Context, endpointID int, opts WebhookUpdateOptions) (WebhookEndpoint, error) {
	body := WebhookEndpointUpdate{
		URL:         opts.URL,
		EventTypes:  opts.EventTypes,
		Countries:   opts.Countries,
		Description: opts.Description,
		Enabled:     opts.Enabled,
	}
	var out WebhookEndpoint
	if err := s.client.requestJSON(ctx, http.MethodPatch,
		API+"/webhooks/"+strconv.Itoa(endpointID),
		[]RequestOption{WithJSONBody(body)}, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// Delete removes an endpoint.
func (s *WebhooksService) Delete(ctx context.Context, endpointID int) error {
	return s.client.requestJSON(ctx, http.MethodDelete,
		API+"/webhooks/"+strconv.Itoa(endpointID), nil, nil)
}

// WebhookDeliveriesOptions tunes webhooks.Deliveries.
type WebhookDeliveriesOptions struct {
	Page   *int
	Status *string
}

// Deliveries lists delivery attempts for an endpoint, optionally
// filtered by status (failed, success, pending).
func (s *WebhooksService) Deliveries(ctx context.Context, endpointID int, opts *WebhookDeliveriesOptions) (WebhookDeliveriesResponse, error) {
	if opts != nil && opts.Status != nil {
		switch *opts.Status {
		case "failed", "success", "pending":
		default:
			return nil, errors.New("legalize: status must be 'failed', 'success', 'pending', or nil")
		}
	}
	params := map[string]any{}
	if opts != nil {
		if opts.Page != nil {
			params["page"] = opts.Page
		}
		if opts.Status != nil {
			params["status"] = opts.Status
		}
	}
	var out WebhookDeliveriesResponse
	if err := s.client.requestJSON(ctx, http.MethodGet,
		API+"/webhooks/"+strconv.Itoa(endpointID)+"/deliveries",
		[]RequestOption{WithParams(params)}, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// Retry re-queues a failed delivery.
func (s *WebhooksService) Retry(ctx context.Context, endpointID, deliveryID int) (WebhookDelivery, error) {
	var out WebhookDelivery
	path := API + "/webhooks/" + strconv.Itoa(endpointID) + "/deliveries/" + strconv.Itoa(deliveryID) + "/retry"
	if err := s.client.requestJSON(ctx, http.MethodPost, path, nil, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// Test sends a test.ping event to verify the endpoint is reachable.
func (s *WebhooksService) Test(ctx context.Context, endpointID int) (WebhookDelivery, error) {
	var out WebhookDelivery
	if err := s.client.requestJSON(ctx, http.MethodPost,
		API+"/webhooks/"+strconv.Itoa(endpointID)+"/test", nil, &out); err != nil {
		return nil, err
	}
	return out, nil
}
