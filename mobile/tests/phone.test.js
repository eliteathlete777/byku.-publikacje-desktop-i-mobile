import test from "node:test";
import assert from "node:assert/strict";
import { pickMedia, displayTitle, relativeTarget, unsyncedEvents } from "../src/domain.js";
import { pingDesktop, sendEvents } from "../src/sync.js";

const f = name => ({ name, sha256: "a".repeat(64) });
test("rolka wysyła do Instagrama dokładnie jeden film — wersję HD, jeśli jest", () => {
  assert.deepEqual(pickMedia([f("13.mp4"), f("13-hd.mp4"), f("miniaturka.png"), f("opis.txt")]).map(x => x.name), ["13-hd.mp4"]);
  assert.deepEqual(pickMedia([f("klip.mov"), f("miniaturka.png")]).map(x => x.name), ["klip.mov"]);
});
test("karuzela zachowuje wszystkie slajdy w kolejności numerów", () => {
  assert.deepEqual(pickMedia([f("slajd-10.jpg"), f("slajd-2.webp"), f("miniaturka.png"), f("slajd-1.jpg")]).map(x => x.name), ["slajd-1.jpg", "slajd-2.webp", "slajd-10.jpg"]);
});
test("tytuł karty: nagłówek z opisu, potem nazwa, potem id", () => {
  assert.equal(displayTitle({ headline: "Pompki na klatce?!", title: "13.mp4", post_id: "p" }), "Pompki na klatce?!");
  assert.equal(displayTitle({ title: "13.mp4", post_id: "p" }), "13.mp4");
  assert.equal(displayTitle({ post_id: "p" }), "p");
});
test("czas względny: po terminie, strefa 15 minut, wkrótce, później", () => {
  const now = Date.parse("2026-09-27T18:00:00");
  assert.deepEqual(relativeTarget(new Date("2026-09-27T15:00:00"), now), { rel: "3 h temu", tone: "late" });
  assert.deepEqual(relativeTarget(new Date("2026-09-27T18:10:00"), now), { rel: "za 10 min", tone: "hot" });
  assert.deepEqual(relativeTarget(new Date("2026-09-27T19:40:00"), now), { rel: "za 1 h 40 min", tone: "soon" });
  assert.deepEqual(relativeTarget(new Date("2026-09-29T18:00:00"), now), { rel: "za 2 d", tone: "" });
  assert.deepEqual(relativeTarget(null, now), { rel: "", tone: "none" });
});
test("do komputera idą tylko czynności jeszcze niepotwierdzone", () => {
  assert.deepEqual(unsyncedEvents([{ event_id: "a" }, { event_id: "b" }], ["a"]).map(e => e.event_id), ["b"]);
});
test("czynności lecą POST-em na adres względny do appki, błąd komputera jest czytelny", async () => {
  let seen;
  const ok = async (url, opt) => { seen = { url, opt }; return { ok: true, json: async () => ({ accepted: 1, skipped: 0 }) }; };
  assert.deepEqual(await sendEvents([{ event_id: "a" }], ok, "https://pc.tailnet.ts.net/"), { accepted: 1, skipped: 0 });
  assert.equal(seen.url, "https://pc.tailnet.ts.net/api/events");
  assert.equal(JSON.parse(seen.opt.body).events.length, 1);
  const bad = async () => ({ ok: false, status: 400, json: async () => ({ error: "zły JSON" }) });
  await assert.rejects(sendEvents([], bad, "https://pc/"), /zły JSON/);
  const ping = async url => ({ ok: true, json: async () => ({ ok: true, packages: 3, url }) });
  assert.equal((await pingDesktop(ping, "https://pc/")).url, "https://pc/api/ping");
});
