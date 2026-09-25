import test from "node:test";
import assert from "node:assert/strict";
import { mergeIndex, verifiedBlob, sha256Hex, IntegrityError, appendUnique, markOpened } from "../src/domain.js";
import { reel } from "./helpers.js";

const rev = c => c.repeat(64);

test("nowa paczka z serwera ma stan: dostępna nowsza wersja", () => {
  const r = mergeIndex([], [reel()]);
  assert.equal(r.packages.length, 1);
  assert.equal(r.summary, "newer");
});

test("ponowne odświeżenie nie tworzy duplikatów", () => {
  const first = mergeIndex([], [reel()]);
  const second = mergeIndex(first.packages, [reel()]);
  const third = mergeIndex(second.packages, [reel(), reel()]);
  assert.equal(third.packages.length, 1);
  assert.equal(third.results.length, 1);
});

test("starsza wersja nie zastępuje nowszej", () => {
  const local = { ...reel(), content_revision: rev("c"), exported_at: "2026-09-26T10:00:00Z" };
  const older = { ...reel(), content_revision: rev("d"), exported_at: "2026-09-20T10:00:00Z" };
  const r = mergeIndex([local], [older]);
  assert.equal(r.packages[0].content_revision, rev("c"));
  assert.equal(r.summary, "current");
});

test("nowsza wersja zastępuje starszą", () => {
  const local = { ...reel(), content_revision: rev("c"), exported_at: "2026-09-20T10:00:00Z" };
  const newer = { ...reel(), content_revision: rev("d"), exported_at: "2026-09-26T10:00:00Z" };
  const r = mergeIndex([local], [newer]);
  assert.equal(r.packages[0].content_revision, rev("d"));
  assert.equal(r.summary, "newer");
  assert.equal(markOpened(r.packages, r.packages[0].package_id)[0]._state, "current");
});

test("paczka niekompletna nie zastępuje poprawnej i jest zgłoszona", () => {
  const local = reel();
  const broken = { ...reel(), content_revision: rev("e"), exported_at: "2026-09-30T10:00:00Z", files: reel().files.slice(1) };
  const r = mergeIndex([local], [broken]);
  assert.equal(r.packages[0].content_revision, local.content_revision);
  assert.equal(r.summary, "incomplete");
});

test("paczka w innej wersji schematu jest niezgodna", () => {
  const r = mergeIndex([], [{ ...reel(), schema_version: 3 }]);
  assert.equal(r.summary, "incompatible");
  assert.equal(r.packages.length, 0);
});

test("błędna suma SHA-256 blokuje użycie pliku", async () => {
  const blob = new Blob(["prawdziwy film"]);
  const good = { name: "film.mp4", sha256: await sha256Hex(blob) };
  assert.equal(await verifiedBlob(blob, good), blob);
  await assert.rejects(verifiedBlob(new Blob(["podmieniony"]), good), IntegrityError);
});

test("zdarzenia są idempotentne po event_id", () => {
  const e = { event_id: "abc-12345678" };
  assert.equal(appendUnique(appendUnique([], e), e).length, 1);
});
