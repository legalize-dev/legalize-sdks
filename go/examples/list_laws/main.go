// List the first page of Spanish laws.
//
// Run with:
//
//	LEGALIZE_API_KEY=leg_... go run .
package main

import (
	"context"
	"fmt"
	"log"

	legalize "github.com/legalize-dev/legalize-sdks/go"
)

func main() {
	client, err := legalize.New()
	if err != nil {
		log.Fatal(err)
	}
	defer func() { _ = client.Close() }()

	page, err := client.Laws().List(context.Background(), "es", &legalize.LawsListOptions{
		PerPage: legalize.Int(10),
	})
	if err != nil {
		log.Fatal(err)
	}

	fmt.Printf("country=%s total=%d showing=%d\n", page.Country, page.Total, len(page.Results))
	for _, law := range page.Results {
		fmt.Printf("- [%s] %s\n", law.ID, law.Title)
	}
}
