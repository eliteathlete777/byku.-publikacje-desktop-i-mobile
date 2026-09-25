from __future__ import annotations

from .studio_adapter import StudioAdapter


class LegacyBridge:
    """Jawny adapter do dojrzałych funkcji starego Studio; bez atrap i duplikacji."""

    def __init__(self, adapter: StudioAdapter):
        self.adapter = adapter

    def available(self) -> bool:
        return bool(self.adapter.core is not None and getattr(self.adapter.core, "legacy", False))

    def _require(self, what: str) -> None:
        if not self.available():
            raise NotImplementedError(f"{what} wymaga rdzenia BYQ Studio (source_root). Obecny rdzeń: "
                                      f"{getattr(self.adapter.core, 'name', 'brak')}.")

    def open_generator(self, brand: str) -> dict:
        self._require("Pełny Generator")
        from studio.rdzen.most_generatora import otworz_generator, zapisz_marke_generatora
        zapisz_marke_generatora(brand)
        result = otworz_generator()
        if not result.get("ok"):
            raise RuntimeError(result.get("blad") or "Nie udało się uruchomić Generatora")
        return result

    def publication_capabilities(self, post_id: str) -> dict:
        if not self.available():
            card = self.adapter.get(post_id)
            return {"hd": {"stan": "niedostępny", "etykieta": "brak rdzenia Studio", "sciezka": ""}, "awaiting_music": False,
                    "is_carousel": card["assets"]["type"] == "carousel",
                    "channels": [k for k, v in card["channels"].items() if v.get("enabled")],
                    "adapter": None, "final_click": "manual", "legacy": False}
        from studio.rdzen.magazyn import wczytaj_paczke
        from studio.rdzen.pulpit_wrzutu import czeka_na_muzyke, stan_hd_paczki
        folder = self.adapter.folder_for(post_id)
        package = wczytaj_paczke(folder, sprawdz_sumy=False)
        hd = stan_hd_paczki(folder, package)
        return {
            "hd": {**hd, "sciezka": str(hd.get("sciezka") or "")},
            "awaiting_music": bool(czeka_na_muzyke(post_id)),
            "is_carousel": bool(package.jest_karuzela),
            "channels": list(package.platformy),
            "adapter": "studio.rdzen.most_publikacji",
            "final_click": "manual",
            "legacy": True,
        }

    def prepare_publication(self, post_id: str, channel: str, retry: bool = False) -> dict:
        if not self.adapter.settings.allow_publication:
            raise PermissionError("Publikowanie jest zablokowane (allow_publication=false). Końcowe kliknięcie i tak zawsze wykonujesz ręcznie.")
        if channel not in {"tiktok", "instagram", "facebook", "obie"}:
            raise ValueError("Nieprawidłowy kanał")
        self._require("Przygotowanie publikacji")
        from studio.rdzen.most_publikacji import przygotuj_wrzut, uruchom_uploader
        prepared = przygotuj_wrzut(post_id, channel, root=self.adapter.settings.queue, ponownie=retry)
        if not prepared.get("ok"):
            raise RuntimeError("; ".join(prepared.get("problemy") or ["Nie udało się przygotować wrzutu"]))
        process = uruchom_uploader(prepared["cmd"], post_id=post_id, platforma=channel)
        return {"ok": True, "pid": process.pid, "post_id": post_id, "channel": channel,
                "retry": retry, "stage": "awaiting_manual_final_click", "folder": prepared.get("folder"),
                "media": prepared.get("wideo")}

    def music_ready(self, post_id: str) -> dict:
        if not self.adapter.settings.allow_publication:
            raise PermissionError("Sygnał muzyki jest zablokowany do czasu jawnego włączenia publikowania.")
        self._require("Sygnał muzyki")
        from studio.rdzen.pulpit_wrzutu import daj_sygnal_muzyki
        return {"ok": True, "path": str(daj_sygnal_muzyki(post_id))}

    def verify(self, post_id: str) -> dict:
        self._require("Weryfikacja na platformach")
        from studio.rdzen.magazyn import wczytaj_paczke
        from studio.rdzen.weryfikacja_statusu import raport_paczki
        folder = self.adapter.folder_for(post_id)
        return raport_paczki(wczytaj_paczke(folder, sprawdz_sumy=False))
