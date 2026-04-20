/**
 * Time-travel: fetch a law at a past revision.
 *
 * Usage:
 *
 *   LEGALIZE_API_KEY=leg_... npx tsx examples/time_travel.ts es ley_organica_3_2018
 */

import { Legalize } from "legalize";

async function main(): Promise<number> {
  const country = process.argv[2] ?? "es";
  const lawId = process.argv[3] ?? "ley_organica_3_2018";

  const client = new Legalize();
  try {
    const commits = await client.laws.commits(country, lawId);
    console.log(`Found ${commits.commits.length} commits for ${lawId}.`);
    if (commits.commits.length === 0) return 0;
    const firstSha = commits.commits[commits.commits.length - 1]!.sha;
    console.log(`Retrieving law at first commit ${firstSha}...`);
    const past = await client.laws.atCommit(country, lawId, firstSha);
    console.log("---");
    console.log(past.content_md.slice(0, 500));
  } finally {
    await client.close();
  }
  return 0;
}

main().then((code) => process.exit(code));
