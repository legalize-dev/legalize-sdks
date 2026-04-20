/**
 * List all laws for a country, auto-paginated.
 *
 * Usage:
 *
 *   LEGALIZE_API_KEY=leg_... npx tsx examples/list_laws.ts es ley_organica
 */

import { Legalize } from "@legalize-dev/sdk";

async function main(): Promise<number> {
  const country = process.argv[2] ?? "es";
  const lawType = process.argv[3];

  const client = new Legalize();
  let i = 1;
  try {
    for await (const law of client.laws.iter(country, lawType ? { lawType } : {})) {
      console.log(`${String(i).padStart(5)}  ${law.id}  ${(law.title ?? "").slice(0, 80)}`);
      i += 1;
    }
  } finally {
    await client.close();
  }
  return 0;
}

main().then((code) => process.exit(code));
