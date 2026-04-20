/**
 * Full-text search for laws.
 *
 * Usage:
 *
 *   LEGALIZE_API_KEY=leg_... npx tsx examples/search.ts es "protección de datos"
 */

import { Legalize } from "@legalize-dev/sdk";

async function main(): Promise<number> {
  const country = process.argv[2] ?? "es";
  const q = process.argv[3] ?? "protección de datos";

  const client = new Legalize();
  try {
    const page = await client.laws.search(country, q, { perPage: 10 });
    console.log(`total=${page.total}  page=${page.page}  per_page=${page.per_page}`);
    for (const law of page.results) {
      console.log(`  ${law.id}  ${law.title}`);
    }
  } finally {
    await client.close();
  }
  return 0;
}

main().then((code) => process.exit(code));
