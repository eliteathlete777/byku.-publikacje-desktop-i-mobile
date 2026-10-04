"""Wrzuć wszędzie: jednocześnie TikTok i Meta (IG + FB), każdy w osobnej przeglądarce.

Użycie (panel BYKU.PUBLIKACJE musi działać, uruchomiony ze skrótu — uploadery dziedziczą po nim sesję):
    python tools/wrzuc_wszedzie.py <post_id> [<post_id> ...]
    python tools/wrzuc_wszedzie.py --lista        # zaakceptowane rolki z terminem, które czekają na wrzut

Skrypt nie klika Zaplanuj — to nadal robisz Ty, gdy checkboxy pokażą „Gotowe”.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8902"


def call(path: str, body: dict | None = None):
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="GET" if body is None else "POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Błąd {e.code}: {json.loads(e.read() or b'{}').get('error', e.reason)}")
    except urllib.error.URLError:
        raise SystemExit("Panel nie odpowiada na 127.0.0.1:8902. Uruchom go skrótem „BYKU.PUBLIKACJE DESKTOP v2”.")


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    if argv[0] == "--lista":
        for c in call("/api/publications?brand=all")["items"]:
            if c["content"]["approved"] and c["local_target_at"] and c["assets"].get("cover_custom"):
                print(f'{c["post_id"]}  {c["brand"]:7}  {c["local_target_at"]}  {c["name"]}')
        return 0
    code = 0
    for post_id in argv:
        try:
            r = call(f"/api/publications/{post_id}/prepare-publication", {"channel": "wszedzie"})
            print(f"{post_id}: ruszyło {', '.join(r['started'])}" + (f"; problemy: {r['problems']}" if r["problems"] else ""))
        except SystemExit as e:
            print(f"{post_id}: {e}")
            code = 1
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
