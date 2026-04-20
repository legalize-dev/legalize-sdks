package legalize_test

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"

	legalize "github.com/legalize-dev/legalize-sdks/go"
)

// Example shows the zero-config construction path that most users
// follow — it pulls the API key and base URL from the environment.
func Example() {
	_ = os.Setenv("LEGALIZE_API_KEY", "leg_demo") // normally set outside the process.

	client, err := legalize.New()
	if err != nil {
		fmt.Println("error:", err)
		return
	}
	defer client.Close()

	_ = client.BaseURL() // https://legalize.dev
	fmt.Println(client.APIVersion())

	// Output: v1
}

// ExampleClient_Laws_List lists the first page of Spanish laws.
// pkg.go.dev renders this example alongside the method's godoc.
func ExampleClient_laws() {
	// Spin up a test server so the example is runnable without
	// hitting the real API.
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = fmt.Fprint(w, `{"country":"es","total":1,"page":1,"per_page":1,
			"results":[{"id":"BOE-A-2025-0001","title":"Ley de ejemplo","country":"es","law_type":"ley"}]}`)
	}))
	defer srv.Close()

	client, err := legalize.New(
		legalize.WithAPIKey("leg_demo"),
		legalize.WithBaseURL(srv.URL),
	)
	if err != nil {
		fmt.Println("error:", err)
		return
	}
	defer client.Close()

	page, err := client.Laws().List(context.Background(), "es", &legalize.LawsListOptions{
		PerPage: legalize.Int(1),
	})
	if err != nil {
		fmt.Println("error:", err)
		return
	}
	fmt.Println(page.Results[0].ID)
	// Output: BOE-A-2025-0001
}

// ExampleClient_errorHandling shows how to branch on typed errors.
func ExampleClient_errorHandling() {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(404)
		_, _ = fmt.Fprint(w, `{"detail":"law not found"}`)
	}))
	defer srv.Close()

	client, _ := legalize.New(
		legalize.WithAPIKey("leg_demo"),
		legalize.WithBaseURL(srv.URL),
		legalize.WithMaxRetries(0),
	)
	defer client.Close()

	_, err := client.Laws().Retrieve(context.Background(), "es", "MISSING")
	var nf *legalize.NotFoundError
	if errors.As(err, &nf) {
		fmt.Println("not found:", nf.Message)
	}
	// Output: not found: law not found
}
