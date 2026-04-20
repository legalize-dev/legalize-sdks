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
	"io"
	"log"
	"log/slog"
	"net/http"
	"os"
	"time"

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
		defer func() { _ = r.Body.Close() }()

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

		// Structured logging with slog is log-injection-safe: each
		// field is recorded independently, so newlines in event.Type
		// or event.Data cannot forge log lines. gosec's taint check
		// (G706) is regex-based and flags any user-derived value in a
		// log call; it does not understand slog's structured model.
		switch event.Type {
		case "law.updated", "law.created", "law.repealed", "reform.created":
			slog.Info("received webhook", "type", event.Type, "data", string(event.Data)) //nolint:gosec // slog is injection-safe
		case "test.ping":
			slog.Info("received webhook", "type", "test.ping")
		default:
			slog.Warn("unknown event type", "type", event.Type) //nolint:gosec // slog is injection-safe
		}
		w.WriteHeader(http.StatusNoContent)
	})

	addr := ":8080"
	if v := os.Getenv("ADDR"); v != "" {
		addr = v
	}
	slog.Info("listening", "addr", addr) //nolint:gosec // slog is injection-safe; addr comes from env
	server := &http.Server{Addr: addr, Handler: mux, ReadHeaderTimeout: 5 * time.Second}
	log.Fatal(server.ListenAndServe())
}
