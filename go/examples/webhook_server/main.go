// Minimal net/http server that verifies incoming Legalize webhook
// signatures and dispatches by event type.
//
// Run with:
//
//	LEGALIZE_WHSEC=whsec_... go run .
//
// The secret is the per-endpoint value shown exactly once when you
// call client.Webhooks().Create(...); store it somewhere safe.
package main

import (
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"

	legalize "github.com/legalize-dev/legalize-sdks/go"
)

func main() {
	secret := os.Getenv("LEGALIZE_WHSEC")
	if secret == "" {
		log.Fatal("LEGALIZE_WHSEC must be set")
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/webhooks/legalize", func(w http.ResponseWriter, r *http.Request) {
		// Always read the raw body — re-serialising JSON breaks the signature.
		body, err := io.ReadAll(r.Body)
		if err != nil {
			http.Error(w, "read", http.StatusBadRequest)
			return
		}
		defer r.Body.Close()

		event, err := legalize.Verify(
			body,
			r.Header.Get("X-Legalize-Signature"),
			r.Header.Get("X-Legalize-Timestamp"),
			secret,
		)
		if err != nil {
			var vErr *legalize.WebhookVerificationError
			if errors.As(err, &vErr) {
				log.Printf("webhook rejected: %s", vErr.Reason)
			}
			http.Error(w, "forbidden", http.StatusForbidden)
			return
		}

		switch event.Type {
		case "law.updated":
			fmt.Printf("received law.updated: %s\n", string(event.Data))
		case "law.created":
			fmt.Printf("received law.created: %s\n", string(event.Data))
		case "law.repealed":
			fmt.Printf("received law.repealed: %s\n", string(event.Data))
		case "reform.created":
			fmt.Printf("received reform.created: %s\n", string(event.Data))
		case "test.ping":
			fmt.Println("received test.ping")
		default:
			fmt.Printf("unknown event type: %s\n", event.Type)
		}
		w.WriteHeader(http.StatusNoContent)
	})

	addr := ":8080"
	if v := os.Getenv("ADDR"); v != "" {
		addr = v
	}
	log.Printf("listening on %s", addr)
	log.Fatal(http.ListenAndServe(addr, mux))
}
