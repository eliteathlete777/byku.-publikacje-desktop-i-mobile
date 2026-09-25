from __future__ import annotations

import json
import re
import time
from datetime import date, datetime, timedelta

from .studio_adapter import StudioAdapter

VARIANTS = {
    "calm": ("Spokojny", ["18:45"], False),
    "regular": ("Regularny", ["12:30", "18:45"], False),
    "intensive": ("Intensywny", ["07:00", "12:30", "18:45"], True),
}
_TERM = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")


def valid_term(value: str) -> bool:
    if not _TERM.match(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d %H:%M")
    except ValueError:
        return False
    return True


class ScheduleService:
    def __init__(self, adapter: StudioAdapter):
        self.adapter = adapter
        self.history = adapter.settings.data_dir / "schedule-history.json"

    def _load_history(self) -> list:
        return json.loads(self.history.read_text(encoding="utf-8")) if self.history.exists() else []

    def propose(self, brand: str, start: str | None = None) -> list[dict]:
        cards = self.adapter.list_cards(brand=brand)["items"]
        unscheduled = [x for x in cards if not x["local_target_at"] and x["next_action"]["code"] != "done"]
        occupied = {x["local_target_at"] for x in cards if x["local_target_at"]}
        begin = datetime.strptime(start, "%Y-%m-%d").date() if start else date.today() + timedelta(days=1)
        output = []
        for key, (label, slots, weekends) in VARIANTS.items():
            day, index, changes = begin, 0, []
            taken = set(occupied)
            for card in unscheduled:
                while True:
                    if not weekends and day.weekday() >= 5:
                        day += timedelta(days=1); index = 0; continue
                    target = f"{day.isoformat()} {slots[index]}"
                    index += 1
                    if index == len(slots):
                        index = 0; day += timedelta(days=1)
                    if target not in taken:
                        break
                taken.add(target)
                changes.append({"post_id": card["post_id"], "name": card["name"], "before": "", "after": target})
            last = changes[-1]["after"][:10] if changes else ""
            output.append({"id": key, "label": label, "slots": slots, "weekends": weekends,
                           "changes": changes, "until": last, "collisions": []})
        return output

    def apply(self, changes: list[dict], *, record_history: bool = True) -> dict:
        self.adapter.ensure_writes("Zapis terminów")
        for change in changes:
            after = change.get("after", "")
            if after and not valid_term(after):
                raise ValueError(f"Nieprawidłowy termin: {after}. Format: RRRR-MM-DD GG:MM")
        core = self.adapter.require_core()
        completed = []
        try:
            for change in changes:
                folder = self.adapter.folder_for(change["post_id"])
                current = self.adapter.get(change["post_id"])["local_target_at"]
                after = change.get("after", "")
                core.set_term(folder, after) if after else core.clear_term(folder)
                completed.append({"post_id": change["post_id"], "before": current, "after": after})
        except Exception:
            for change in reversed(completed):
                folder = self.adapter.folder_for(change["post_id"])
                core.set_term(folder, change["before"]) if change["before"] else core.clear_term(folder)
            raise
        if record_history and completed:
            history = self._load_history()
            history.append({"at": time.time(), "changes": completed})
            self.history.write_text(json.dumps(history[-100:], ensure_ascii=False, indent=2), encoding="utf-8")
        return {"saved": len(completed), "changes": completed}

    def undo(self) -> dict:
        history = self._load_history()
        if not history:
            return {"saved": 0, "changes": []}
        last = history[-1]
        inverse = [{"post_id": x["post_id"], "after": x["before"]} for x in reversed(last["changes"])]
        result = self.apply(inverse, record_history=False)
        # Historię skracamy dopiero po udanym cofnięciu — błąd nie gubi wpisu.
        self.history.write_text(json.dumps(history[:-1], ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    def can_undo(self) -> bool:
        return bool(self._load_history())
