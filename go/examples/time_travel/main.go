// Time-travel demo: fetch the current law, walk its commit history,
// and print its text at the oldest available version.
//
// Run with:
//
//	LEGALIZE_API_KEY=leg_... go run . BOE-A-1978-31229
package main

import (
	"context"
	"fmt"
	"log"
	"os"

	legalize "github.com/legalize-dev/legalize-sdks/go"
)

func main() {
	lawID := "BOE-A-1978-31229" // Spanish constitution
	if len(os.Args) > 1 {
		lawID = os.Args[1]
	}

	client, err := legalize.New()
	if err != nil {
		log.Fatal(err)
	}
	defer client.Close()

	ctx := context.Background()

	commits, err := client.Laws().Commits(ctx, "es", lawID)
	if err != nil {
		log.Fatal(err)
	}
	if len(commits.Commits) == 0 {
		log.Fatal("law has no commit history")
	}

	fmt.Printf("%s — %d commits on record\n", lawID, len(commits.Commits))
	for _, c := range commits.Commits {
		fmt.Printf("  %s  %s  %s\n", c.SHA[:7], c.Date, c.Message)
	}

	oldest := commits.Commits[len(commits.Commits)-1]
	fmt.Printf("\n--- Version at %s ---\n", oldest.SHA[:7])

	snap, err := client.Laws().AtCommit(ctx, "es", lawID, oldest.SHA)
	if err != nil {
		log.Fatal(err)
	}
	// Print the first 500 chars only, for demo purposes.
	content := snap.ContentMD
	if len(content) > 500 {
		content = content[:500] + "..."
	}
	fmt.Println(content)
}
