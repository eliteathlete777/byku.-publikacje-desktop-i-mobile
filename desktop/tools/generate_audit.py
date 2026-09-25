from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CFG=json.loads((ROOT/"config.json").read_text(encoding="utf-8"))
SOURCES=[Path(CFG["source_root"]),Path(r"C:\Users\DELL\Desktop\aplikacje\05_APLIKACJE_SKRYPTY\generator-opisow-dropa")]


def classify(path: Path, tree: ast.AST) -> str:
    name=path.name.lower()
    if name.startswith("_"): return "jednorazowy/historyczny — nie uruchamiać automatycznie"
    if "test" in path.parts or name.startswith("test_"): return "test"
    if "uploader" in name: return "publikowanie — tylko przez most"
    if name in {"automat.py","planer.py","app.py"}: return "aplikacja/scheduler — wymaga koordynacji"
    if "studio\\rdzen" in str(path).lower(): return "rdzeń"
    if "studio\\gui" in str(path).lower(): return "GUI"
    if path.parent.name=="generator-opisow-dropa": return "generator"
    return "pomocniczy"


items=[]
for base in SOURCES:
    for path in base.rglob("*.py"):
        if any(x in path.parts for x in ("browser-profile-edge","browser-profile-chrome","build","dist","__pycache__")): continue
        raw=path.read_bytes(); entry={"path":str(path),"sha256":hashlib.sha256(raw).hexdigest(),"size":len(raw)}
        try:
            tree=ast.parse(raw.decode("utf-8-sig")); entry["classification"]=classify(path,tree)
            entry["imports"]=sorted({(n.module or "") if isinstance(n,ast.ImportFrom) else a.name for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom)) for a in ([n.names[0]] if isinstance(n,ast.Import) else [ast.alias(name=n.module or "")])})
            entry["functions"]=[n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
            entry["top_level_calls"]=[ast.unparse(n.value.func) for n in tree.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)]
        except Exception as exc: entry.update({"classification":"nieparsowalny","error":str(exc)})
        items.append(entry)
(ROOT/"docs"/"MANIFEST_SKRYPTOW.json").write_text(json.dumps({"generated":"2026-09-24","count":len(items),"items":items},ensure_ascii=False,indent=2),encoding="utf-8")
print(f"Zapisano {len(items)} wpisów")

