import test from "node:test";
import assert from "node:assert/strict";
import { validateManifest } from "../src/contract.js";
import { cases } from "./helpers.js";

for (const c of cases) {
  test(`kontrakt v2: ${c.name}`, () => {
    const codes = new Set(validateManifest(c.manifest).map(e => e.code));
    if (c.valid) assert.deepEqual([...codes], []);
    else assert.ok(codes.has(c.error), `oczekiwano ${c.error}, jest ${[...codes]}`);
  });
}
