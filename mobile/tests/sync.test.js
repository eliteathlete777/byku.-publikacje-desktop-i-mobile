import test from "node:test";
import assert from "node:assert/strict";
import { refreshPackages } from "../src/sync.js";

const h="b".repeat(64); const packageManifest={schema_version:1,post_id:"p",brand:"atlet",content_revision:"r",exported_at:"2026-09-25T10:00:00Z",channel:"instagram",files:[{name:"x.mp4",sha256:h},{name:"opis-do-skopiowania.txt",sha256:h},{name:"hashtagi.txt",sha256:h}]};
test("offline zgłasza błąd i nie mutuje ostatniego poprawnego odczytu", async()=>{ const existing=[packageManifest]; await assert.rejects(refreshPackages({indexUrl:"https://drive.test/index.json",brand:"atlet",existing,fetcher:async()=>{throw Error("offline")}}),/offline/); assert.equal(existing.length,1); assert.equal(existing[0].content_revision,"r"); });
test("pobiera indeks i manifest względny", async()=>{ const fetcher=async url=>({ok:true,json:async()=>String(url).endsWith("index.json")?{packages:[{brand:"atlet",manifest_url:"p/manifest.json"}]}:packageManifest}); const result=await refreshPackages({indexUrl:"https://drive.test/index.json",brand:"atlet",existing:[],fetcher}); assert.equal(result.manifests.length,1); });
