---
name: byku-wrzut-platformy
description: Wrzut rolek BYKU (Rigger i Atlet) na TikTok i Meta (Instagram + Facebook) skryptami Pythona z panelu BYKU.PUBLIKACJE albo BYQ Studio — kolejność kroków, twarde zasady Damiana, bramki przed terminem, znane pułapki stron i jak je naprawiać. Użyj ZAWSZE, gdy Damian mówi „wrzuć/wrzut/opublikuj/zaplanuj rolkę”, „Wrzuć TikTok / IG + FB”, „przeprowadź wrzut do końca”, gdy uploader stoi na etapie (film, opis, okładka, lokalizacja, termin), albo gdy trzeba poprawić tiktok_uploader.py / meta_uploader.py.
---

# Wrzut rolek BYKU na TikTok i Meta

## Najważniejsze zasady (Damian, 29.09.2026)
1. **Końcowe „Zaplanuj” klika zawsze Damian.** Skrypt dochodzi do ekranu z ustawioną datą i zostawia okno.
2. **Ekran z datą = „wszystko gotowe, klikam”.** Damian klika Zaplanuj od razu. Każda poprawka musi się dziać PRZED krokiem terminu. Nigdy „wróćmy i poprawmy” po ustawieniu daty.
3. **Pominięty krok (opis, okładka, lokalizacja) naprawiaj do 3 razy** (`PROBY_NAPRAWY = 3` w obu uploaderach). Jeśli dalej brak: STOP przed terminem/Dalej, formularz zostaje otwarty.
4. **Klikaj elementy i napisy, nigdy zapamiętane współrzędne.** Współrzędne z `evaluate` bywają sprzed przewinięcia i trafiają obok. Oznaczaj element atrybutem (`data-byq-…`) i klikaj `locator`.
5. **Sprawdzaj tylko WIDOCZNE elementy** (`text=/…/ >> visible=true`). Teksty „Lokalizacja”, „jest w:” są też w ukrytych węzłach i dają fałszywe „ok”.
6. Jeśli Python nie daje rady — Damian pozwala użyć zdalnej kontroli przeglądarki (Chrome „Browser 1” / computer-use) na tym samym oknie. Po udanym wrzucie **każdą poprawkę wpisz do skryptów Pythona** (wrzut za wrzutem).
7. Damian pozwolił: klikać „Wrzuć” w panelu, zamykać zepsute okno wrzutu i ponawiać. Kluczy API/haseł nie wpisujesz nigdy.
8. Uploadery **nie są uruchamiane z terminala Claude**. Panel startuje ze skrótu przez `explorer.exe "C:\Users\DELL\Desktop\BYKU.PUBLIKACJE DESKTOP v2.lnk"` (rodzic = explorer, jak BYQ Studio).

## Gdzie co jest
- Skrypty: `C:\Users\DELL\Desktop\aplikacje\05_APLIKACJE_SKRYPTY\byku-publisher-desktop\`
  - `tiktok_uploader.py`, `meta_uploader.py` (+ `*_karuzela_uploader.py`), `szukaj_miejsca.py`, `niezawodnosc.py`
  - `studio/rdzen/most_publikacji.py` (składa komendę), `pineski.py`, `kalendarz_live.py`
  - kolejka paczek: `studio-kolejka\<post_id>\` (wideo, `*-hd.mp4`, `miniaturka.png`, `opis.txt`, `post.json`)
  - logi: `status\<post_id>-<tiktok|obie>-konsola.log` (poprzednie jako `…-konsola-<data>.log`), blokady: `wysylka_w_toku\`
  - kopie oryginałów przed poprawkami: `*.przed-poprawka-2026-09-29.py`
  - testy: `python -m unittest discover -s studio/testy -t .` (135 testów, muszą przejść)
- Przeglądarki (CDP): TikTok Rigger = Edge `:9223` (`browser-profile-edge-rigger\User Data`), TikTok Atlet = Edge `:9224`, Meta Atlet = Edge `:9222`, Meta Rigger = Chrome `:9333` (`browser-profile-chrome-rigger`).
- Panel: przycisk **Wrzuć TikTok / Wrzuć IG + FB** na Stole publikacji (skill `byku-publikacje-panel`). Postęp = checkboxy etapów z linii `BYQ_STATUS:` w logu.

## Kolejność kroków
**TikTok:** film → opis → okładka → lokalizacja → [BRAMKA] → Zaplanuj + data/godzina → dźwięk (Damian dobiera ręcznie, skrypt czeka) → okno zostaje, Damian klika Zaplanuj.

**Meta (IG + FB razem, kompozytor „Utwórz rolkę”):** film → opis → lokalizacja → okładka → **bez znaczników** → przełącznik „Dostosuj post na Facebooka i Instagram” WYŁĄCZONY → [BRAMKA] → Dalej → **bez muzyki** (Edytuj → Dalej) → „Opcje planowania”: kafelek **Zaplanuj** → data i godzina dla Facebooka i Instagrama → Damian klika dolny Zaplanuj.

## Bramki (już w kodzie)
- TikTok, przed `ustaw_harmonogram`: opis, okładka (`ustaw_okladke` zwraca True/False), lokalizacja — każde do 3 prób, inaczej `RuntimeError` bez daty.
- Meta, przed Dalej: opis_ok, widoczny chip „jest w: …” (`_chip_jest_w`), widoczne „Zmień obraz” (`_okladka_jest_wgrana`) — do 3 napraw, inaczej `RuntimeError` bez Dalej.

## Znane pułapki i rozwiązania (29.09)
- **„Film nie wgrany”, a film jest**: TikTok/Meta podmieniają dropzone po wstawieniu pliku, Patchright zgłasza Timeout. Sukces sprawdzaj stanem strony: TikTok `_film_wszedl` (widać edytor/„Edytuj okładkę”), Meta `_wgranie_ruszylo` (.mp4 / % / podgląd). Przy ponowieniu NIE wgrywaj drugi raz.
- **Okno Windows „Otwieranie”**: wypełniaj bez klawiatury — `WM_SETTEXT` pełnej ścieżki + `BM_CLICK` Otwórz (`_dialog_wstaw_sciezke_bez_klawiatury`). `keybd_event` trafia w okno na wierzchu (nie w dialog).
- **Okładka Meta**: pewny spust to LINK `<a>` „Prześlij obraz” w szarym pasku sekcji Miniatura (`a:text-is("Prześlij obraz")`) → zwykły filechooser. Napis zakładki „Prześlij obraz” nic nie otwiera (w wąskim oknie leży bardziej w prawo i heurystyka po x go wybierała).
- **Pinezka lokalizacji Meta**: ikona BEZ aria-label w rzędzie pod opisem: emoji · PIN · „Zachęć do wysyłania wiadomości” · „Oznacz markę”. Bierz przycisk tuż na lewo od „Zachęć…”, najedź, sprawdź widoczny dymek „Lokalizacja”, kliknij (`_pin_obok_ikon_opisu`).
- **Lista miejsc Meta**: czytaj tylko listę z `aria-controls` pola albo opcje w oknie Lokalizacja. Globalne `[role=option]` łapie boczne menu („Rozliczenia i płatności”, „Odbiorcy”).
- **Wybór miejsca** (`szukaj_miejsca.py`): kolejność prób: dokładny wpis → miasto po przecinku → miasto z internetu (Wikipedia, potem OSM; cache `status/miejsca_cache.json`). Podpowiedź musi zawierać wszystkie słowa szukanego (`pasuje`); z pasujących: dokładne miasto > miasto na początku > najkrótsza etykieta (`lepsza_dla_miasta`). „Warszawa” = Warszawa, NIE Plac Defilad / Pałac Kultury. Plac Defilad tylko gdy wpisany wprost. Puste pole = Warszawa.
- **Termin Meta**: nowy układ „Opcje planowania” (kafelki Udostępnij teraz | Zaplanuj | Zapisz jako wersję roboczą) → klik napisu „Zaplanuj” w tej sekcji (`_kliknij_kafel_zaplanuj_w_opcjach`), potem pola `dd.mm.rrrr` + spinbuttony `godz.`/`min` ×2 (FB, IG).
- **Godzina Meta (spinbuttony `godz.`/`min`)**: przyjmują tylko strzałki od `aria-valuenow`. Był limit 45 naciśnięć — 30.09 minuta stanęła na 12 zamiast 7 (57 → 7). Teraz `_ustaw_spinbutton_do` idzie krótszą drogą z zawijaniem (mod 24/60), a gdy pole się nie zawija, dochodzi wprost bez limitu. Weryfikacja `aria-valuenow` przed stopką zostaje.
- **Polskie litery w nazwie filmu** („przytyło”): lista procesów w panelu czytana jako bajty UTF-8 (`_python_processes`), inaczej „'NoneType' … splitlines” przy Wrzuć. Panel po restarcie przejmuje żywe uploadery (lista etapów i „Muzyka dobrana” wracają).
- **Blokada `wysylka_w_toku\<post>-<kanal>.lock`**: po martwym uploaderze panel zdejmuje ją sam (tylko gdy Zaplanuj nie było klikane — `zdejmij_osierocona_blokade`). Blokada uploadera jest per kanał: TikTok i Meta tej samej rolki mogą iść równolegle.
- **Strażnik**: 2 min bez nowej linii w logu i nie czeka na Damiana (muzyka/Zaplanuj) → panel przerywa proces i zdejmuje blokadę.
- **Odśwież kalendarz** przełącza okno Meta na Terminarz — nigdy w trakcie wrzutu.

## Potwierdzanie: co jest już na platformach (Damian 30.09–03.10)
- **Źródło prawdy = listy postów, nie siatka Terminarza.** TikTok Studio → Posty (`https://www.tiktok.com/tiktokstudio/content`: opis + plakietka „6 paź 8:05 PM” = zaplanowane, sama data = opublikowane). Meta → Zawartość → **Zaplanowane** / **Opublikowane** (`…/latest/posts/scheduled_posts|published_posts?asset_id=…`): wiersz `[role=row]` z pełnym opisem, „Rolka · Byku.Rigger” = Facebook, „Rolka · byku.rigger” = Instagram, data „6 października 20:12”. Odczyt: `studio/rdzen/kalendarz_live.py` (`JS_WIERSZE_META`, dopasowanie po pierwszych słowach opisu + DZIEŃ z listy).
- **Checkboxy nóg w panelu**: TikTok i Meta (IG + FB jednym kliknięciem). Wrzut z panelu z ✓ na wszystkich etapach (muzyka się nie liczy) odhacza nogę sam.
- **Rozbieżności** (Damian ✓, lista nie widzi — albo odwrotnie): `desktop/data/rozbieznosci.json`, `GET /api/legs/mismatches`, lista „Do sprawdzenia przez agenta” na Stole. Agent sam otwiera listy zdalnie, znajduje wpis, poprawia odczyt albo checkbox i zapisuje wniosek tutaj.
- Otwarte 03.10: lista Meta „Zaplanowane” wróciła pusta przy ostatnim odczycie (Opublikowane OK) — prawdopodobnie za krótkie czekanie albo tabela przewija się we własnym kontenerze. W panelu odczyt Riggera padł „Connection closed while reading from the driver”, uruchomiony osobno działał.

## Jak prowadzić wrzut samodzielnie (Claude)
1. Sprawdź kartę: `GET http://127.0.0.1:8902/api/publications?brand=rigger` (approved, termin w przyszłości, lokalizacja).
2. Start: `POST /api/publications/<post_id>/prepare-publication {"channel":"tiktok"|"obie"}`; obserwuj `GET /api/uploads` (checkboxy etapów).
3. Etap `error` → przeczytaj log konsoli, podłącz się przez CDP (Patchright `connect_over_cdp`, na koniec `os._exit(0)`, NIE `close()`), zrób zrzut, znajdź przyczynę, popraw skrypt, ponów krok — ZAWSZE przed terminem.
4. Zatrzymaj na ekranie z datą. Zgłoś Damianowi: co wypełnione, lokalizacja, okładka, termin.
5. Po wrzucie: poprawki do skryptów, `py_compile`, testy Studio, notatka w pamięci.
