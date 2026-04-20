// Package legalize is the official Go SDK for the Legalize API
// (https://legalize.dev) — open legislation as structured data, every
// reform as a diff.
//
// # Quick start
//
// With LEGALIZE_API_KEY set in the environment:
//
//	import legalize "github.com/legalize-dev/legalize-sdks/go"
//
//	client, err := legalize.New()
//	if err != nil { log.Fatal(err) }
//	defer client.Close()
//
//	page, err := client.Laws().List(ctx, "es", nil)
//
// # Configuration
//
// All client state is supplied via functional options:
//
//	client, err := legalize.New(
//	    legalize.WithAPIKey("leg_..."),
//	    legalize.WithBaseURL("https://legalize.dev"),
//	    legalize.WithAPIVersion("v1"),
//	    legalize.WithTimeout(30 * time.Second),
//	    legalize.WithMaxRetries(3),
//	)
//
// The environment variables LEGALIZE_API_KEY, LEGALIZE_BASE_URL and
// LEGALIZE_API_VERSION are consulted when the corresponding option is
// not supplied. Empty strings are treated as unset. Explicit options
// always win over the environment.
//
// # Resources
//
// The API is organised in seven resource groups. Each returns a
// service attached to the client:
//
//   - client.Countries()       — list available countries
//   - client.Jurisdictions()   — list jurisdictions inside a country
//   - client.LawTypes()        — list law-type codes inside a country
//   - client.Laws()            — list, search, retrieve, meta, commits, at-commit
//   - client.Reforms()         — list reforms for a law
//   - client.Stats()           — aggregate statistics per country
//   - client.Webhooks()        — manage webhook endpoints + deliveries
//
// # Errors
//
// Every non-2xx response surfaces as a typed error. Callers can match
// on the concrete type with errors.As:
//
//	var rle *legalize.RateLimitError
//	if errors.As(err, &rle) {
//	    time.Sleep(rle.RetryAfter)
//	}
//
// All typed errors implement the unexported Error marker and
// expose APIError fields (status code, code, message, body,
// request id).
//
// # Webhooks
//
// Verify incoming webhook signatures with Verify:
//
//	event, err := legalize.Verify(
//	    body,
//	    r.Header.Get("X-Legalize-Signature"),
//	    r.Header.Get("X-Legalize-Timestamp"),
//	    os.Getenv("LEGALIZE_WHSEC"),
//	)
package legalize
