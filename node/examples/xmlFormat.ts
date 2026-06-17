/**
 * Content negotiation: fetch a law as XML instead of JSON.
 *
 * The typed resource methods always return JSON-parsed models. When your
 * app speaks XML, `requestRaw` fetches any endpoint in another wire
 * format and hands you the body untouched — the SDK ships no XML parser,
 * so parse `.text` with your own library.
 *
 * Usage:
 *
 *   LEGALIZE_API_KEY=leg_... npx tsx examples/xmlFormat.ts es BOE-A-1978-31229
 */

import { Legalize } from "@legalize-dev/sdk";

async function main(): Promise<number> {
  const country = process.argv[2] ?? "es";
  const lawId = process.argv[3] ?? "BOE-A-1978-31229";

  const client = new Legalize();
  try {
    // format defaults to "xml" → Accept: application/xml
    const res = await client.requestRaw("GET", `/api/v1/${country}/laws/${lawId}`);
    console.log(`status      ${res.statusCode}`);
    console.log(`contentType ${res.contentType}`);
    console.log("---");
    console.log(res.text.slice(0, 500)); // raw XML; parse with your own library

    // The same call with format: "json" gives you the JSON body to parse.
    const countries = await client.requestRaw("GET", "/api/v1/countries", { format: "json" });
    console.log("---");
    console.log(`countries payload is ${countries.contentType}`);
    console.log(countries.json());
  } finally {
    await client.close();
  }
  return 0;
}

main().then((code) => process.exit(code));
