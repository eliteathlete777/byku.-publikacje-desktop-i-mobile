import test from "node:test";
import assert from "node:assert/strict";
import { appendUniqueEvent, comparePackage, mergeManifests, validateManifest } from "../src/domain.js";

const hash = "a".repeat(64);
const manifest = (overrides={}) => ({ schema_version:1, post_id:"post-1", brand:"atlet", content_revision:"rev-1", exported_at:"2026-09-24T10:00:00Z", channel:"instagram", source_state:{tiktok:"scheduled",instagram:"unknown"}, files:[{name:"film.mp4",sha256:hash},{name:"opis-do-skopiowania.txt",sha256:hash},{name:"hashtagi.txt",sha256:hash}], ...overrides });

test("akceptuje paczkę odbiorową TikTok gotowy, Instagram czeka", () => assert.equal(validateManifest(manifest(), "atlet").ok, true));
test("wykrywa brak pliku źródłowego", () => assert.equal(validateManifest(manifest({files:[{name:"opis-do-skopiowania.txt",sha256:hash},{name:"hashtagi.txt",sha256:hash}]}), "atlet").ok, false));
test("wykrywa niezgodną markę i schemat", () => assert.equal(comparePackage(null, manifest({brand:"rigger",schema_version:2}), "atlet").state, "incompatible"));
test("nowsza rewizja zastępuje starszą", () => { const newer=manifest({content_revision:"rev-2",exported_at:"2026-09-25T10:00:00Z"}); const result=mergeManifests([manifest()],[newer],"atlet"); assert.equal(result.manifests[0].content_revision,"rev-2"); assert.equal(result.results[0].state,"newer"); });
test("starsza rewizja nie nadpisuje nowszej", () => { const older=manifest({content_revision:"old",exported_at:"2026-09-20T10:00:00Z"}); const result=mergeManifests([manifest()],[older],"atlet"); assert.equal(result.manifests[0].content_revision,"rev-1"); assert.equal(result.results[0].state,"current"); });
test("ponowne odświeżenie nie tworzy duplikatu", () => { const result=mergeManifests([manifest()],[manifest()],"atlet"); assert.equal(result.manifests.length,1); assert.equal(result.results[0].state,"current"); });
test("zdarzenia są idempotentne po event_id", () => { const event={event_id:"same"}; assert.equal(appendUniqueEvent(appendUniqueEvent([],event),event).length,1); });
