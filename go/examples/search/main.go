// Stream every Spanish law matching a full-text query.
//
// Run with:
//
//	LEGALIZE_API_KEY=leg_... go run . elections
package main

import (
	"context"
	"fmt"
	"log"
	"os"

	legalize "github.com/legalize-dev/legalize-sdks/go"
)

func main() {
	query := "elections"
	if len(os.Args) > 1 {
		query = os.Args[1]
	}

	client, err := legalize.New()
	if err != nil {
		log.Fatal(err)
	}
	defer client.Close()

	ctx := context.Background()

	// Cap the stream at 100 results to avoid runaway output.
	it := client.Laws().SearchIter(ctx, "es", query, 100, 100, nil)
	var shown int
	for {
		law, ok, err := it.Next(ctx)
		if err != nil {
			log.Fatal(err)
		}
		if !ok {
			break
		}
		shown++
		fmt.Printf("%3d. [%s] %s\n", shown, law.ID, law.Title)
	}
	fmt.Printf("%d results for %q\n", shown, query)
}
