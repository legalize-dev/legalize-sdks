/**
 * SDK version — MUST be kept in sync with the "version" field in package.json.
 *
 * The Node runtime doesn't resolve JSON imports cleanly across ESM/CJS dual
 * output without extra wiring, so we duplicate the literal here. The test
 * suite asserts they match so drift is caught immediately.
 */
export const SDK_VERSION = "0.1.0";
