from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta

from .studio_adapter import StudioAdapter


VARIANTS = {"calm": (["18:45"], False), "regular": (["12:30", "18:45"], False), "intensive": (["07:00", "12:30", "18:45"], True)}


class ScheduleService:
    def __init__(self, adapter: StudioAdapter):
        self.adapter = adapter
        self.history = adapter.settings.data_dir / "schedule-history.json"

    def propose(self, brand: str, start: str | None = None) -> list[dict]:
        cards = self.adapter.list_cards(brand=brand)["items"]
        unscheduled = [x for x in cards if not x["local_target_at"]]
        occupied = {x["local_target_at"] for x in cards if x["local_target_at"]}
        begin = datetime.strptime(start, "%Y-%m-%d").date() if start else date.today()
        output = []
        for key, (slots, weekends) in VARIANTS.items():
            day, index, changes = begin, 0, []
            for card in unscheduled:
                while True:
                    if not weekends and day.weekday() >= 5:
                        day += timedelta(days=1); index = 0; continue
                    target = f"{day.isoformat()} {slots[index]}"
                    index += 1
                    if index == len(slots): index = 0; day += timedelta(days=1)
                    if target not in occupied and target not in {x['after'] for x in changes}: break
                changes.append({"post_id": card["post_id"], "before": "", "after": target})
            output.append({"id": key, "changes": changes, "collisions": []})
        return output

    def apply(self, changes: list[dict], *, record_history: bool = True) -> dict:
        if self.adapter.settings.mode == "production" and not self.adapter.settings.allow_production_writes:
            raise PermissionError("Zapis produkcyjny nie został włączony")
        from studio.rdzen.magazyn import ustaw_termin, wyczysc_termin
        completed = []
        try:
            for change in changes:
                folder = self.adapter.folder_for(change["post_id"])
                current = self.adapter.get(change["post_id"])["local_target_at"]
                after = change.get("after", "")
                (ustaw_termin(folder, after) if after else wyczysc_termin(folder))
                completed.append({"post_id": change["post_id"], "before": current, "after": after})
        except Exception:
            for change in reversed(completed):
                folder = self.adapter.folder_for(change["post_id"])
                (ustaw_termin(folder, change["before"]) if change["before"] else wyczysc_termin(folder))
            raise
        if record_history:
            history = json.loads(self.history.read_text(encoding="utf-8")) if self.history.exists() else []
            history.append({"at": time.time(), "changes": completed})
            self.history.write_text(json.dumps(history[-100:], ensure_ascii=False, indent=2), encoding="utf-8")
        return {"saved": len(completed)}

    def undo(self) -> dict:
        history = json.loads(self.history.read_text(encoding="utf-8")) if self.history.exists() else []
        if not history: return {"saved": 0}
        last = history.pop()
        inverse = [{"post_id": x["post_id"], "after": x["before"]} for x in reversed(last["changes"])]
        self.history.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.apply(inverse, record_history=False)
