package legalize_test

import (
	"context"
	"encoding/xml"
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
	defer func() { _ = client.Close() }()

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
	defer func() { _ = client.Close() }()

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

// ExampleClient_RequestRaw fetches a law as XML via content
// negotiation and unmarshals the body with encoding/xml. The typed
// resource services always return JSON; RequestRaw is the opt-in
// escape hatch for other wire formats (XML by default).
func ExampleClient_RequestRaw() {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/xml; charset=utf-8")
		_, _ = fmt.Fprint(w, `<law id="BOE-A-1978-31229"><title>Constitucion</title></law>`)
	}))
	defer srv.Close()

	client, _ := legalize.New(
		legalize.WithAPIKey("leg_demo"),
		legalize.WithBaseURL(srv.URL),
	)
	defer func() { _ = client.Close() }()

	res, err := client.RequestRaw(context.Background(), "GET", "/api/v1/es/laws/BOE-A-1978-31229")
	if err != nil {
		fmt.Println("error:", err)
		return
	}

	var law struct {
		ID    string `xml:"id,attr"`
		Title string `xml:"title"`
	}
	if err := xml.Unmarshal(res.Content, &law); err != nil {
		fmt.Println("error:", err)
		return
	}
	fmt.Println(law.ID, law.Title)
	// Output: BOE-A-1978-31229 Constitucion
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
	defer func() { _ = client.Close() }()

	_, err := client.Laws().Retrieve(context.Background(), "es", "MISSING")
	var nf *legalize.NotFoundError
	if errors.As(err, &nf) {
		fmt.Println("not found:", nf.Message)
	}
	// Output: not found: law not found
}
