import test from "node:test";
import assert from "node:assert/strict";
import { composeCaption, packageProgress, sortPackages, instagramUrl, createEvent } from "../src/domain.js";

const m = { post_id: "p", brand: "atlet", content_revision: "r2" };
test("podpis łączy opis i hashtagi pustą linią", () => {
  assert.equal(composeCaption(" Nikt cię nie uratuje. \n", "#byku\n"), "Nikt cię nie uratuje.\n\n#byku");
  assert.equal(composeCaption("", "#byku"), "#byku");
});
test("postęp liczy tylko zdarzenia tej paczki i tej rewizji", () => {
  const ev = [createEvent("description_copied", m, {}, "1"), createEvent("sent", { ...m, content_revision: "r1" }, {}, "2"), createEvent("manual_hook", { ...m, post_id: "inna" }, {}, "3")];
  assert.deepEqual(packageProgress(ev, m), { caption: true, media: false, published: false });
});
test("najbliższy termin na górze, bez terminu na końcu", () => {
  const xs = sortPackages([{ post_id: "c" }, { post_id: "b", target_at: "2026-09-28 19:00" }, { post_id: "a", target_at: "2026-09-27 19:07" }]);
  assert.deepEqual(xs.map(x => x.post_id), ["a", "b", "c"]);
});
test("Android otwiera aplikację Instagram, reszta stronę", () => {
  assert.match(instagramUrl("Mozilla/5.0 (Linux; Android 14; Pixel 8)"), /^intent:.*package=com\.instagram\.android/);
  assert.equal(instagramUrl("iPhone"), "https://www.instagram.com/");
});
