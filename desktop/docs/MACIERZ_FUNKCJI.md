# Macierz zgodności BYQ Studio → BYKU.PUBLIKACJE DESKTOP

Audyt statyczny `studio/gui/okno.py`, `sloty_ui.py` oraz zależności. Status `adapter` oznacza dostęp przez istniejący rdzeń bez przepisywania uploadera; `UI` oznacza bezpośredni ekran nowego desktopu. Szczegóły skryptów i hashe: `MANIFEST_SKRYPTOW.json`.

| Oryginalna akcja | Funkcja / skrypt | Odczyt i zapis | Nowy odpowiednik | Test | Status |
|---|---|---|---|---|---|
| Wybór ATLET/RIGGER | `_wybierz_marke` | filtr kolejki, profile marki | przełącznik Marka | izolacja marek | UI |
| Treść / Generator | `_pokaz_tresc`, `most_generatora.otworz_generator` | Generator 8765, kolejka | Opisy i styl / dokończanie | trwałość, konflikt | adapter |
| Import starego dropu | `_klik_import`, `importuj_z_inbox` | inbox → kolejka | Biblioteka / Import | sumy i duplikaty | adapter |
| Folder z dysku | `_klik_folder`, `importuj_folder` | media → paczka | Biblioteka / Import | rolka i karuzela | adapter |
| Telefon → karta | `_synchronizuj_telefon`, `drive_telefon` | Drive → kolejka | Paczki telefonu / Import | idempotencja, marka, sumy | adapter |
| Odśwież kolejkę | `_odswiez_kolejke`, `lista_paczek` | odczyt `studio-kolejka` | Odśwież | wybór pozostaje | UI |
| Otwórz kolejkę / inbox | `_explorer` | Explorer | Otwórz folder | ścieżka ograniczona | UI |
| Opisy kolejki | `_rysuj_opisy`, `_otworz_w_generatorze` | paczka + Generator | Do dokończenia / Treść | wersja po restarcie | UI |
| Widok kolumn platform | `_rysuj_kolumny_platform` | paczki i LIVE | Publikacje | kanały niezależne | UI |
| Widok tygodnia | `_rysuj_tydzien` | terminy | Kalendarz tydzień | przeciąganie i przycisk | adapter |
| Rolki / karuzele | `_ustaw_typ_kal` | `typ_posta`, slajdy | filtr typu | kolejność slajdów | adapter |
| Poprzedni / następny tydzień | `_przesun_tydzien` | tylko widok | nawigacja kalendarza | zmiana tygodnia | UI |
| Wróć do dziś | ustawienie `_kal_poniedzialek` | tylko widok | Dzisiaj | strefa Europe/Warsaw | UI |
| Cofnij | `_cofnij_kalendarz` | terminy | Cofnij zmianę | restart/historia | adapter |
| Wyczyść dzień | `_wyczysc_dzien` | `wyczysc_termin` | menu dnia | archiwum nietknięte | adapter |
| Przeciągnij kartę | `_tydzien_release`, `_upusc_na_dzien` | `ustaw_termin` | Kalendarz | rozbieżność platformy | adapter |
| Wybór slotu / AUTO / dzień | `sloty_ui`, `sloty.py` | termin | warianty i wybór terminu | zgodność algorytmu | adapter |
| Rozłóż szkice | `_rozloz_szkice_na_tydzien` | wiele terminów | Spokojny/regularny/intensywny | podgląd i rollback | adapter |
| Publikacja / archiwum | `_rysuj_publikacje`, `_przelacz_archiwum_publikacja` | status | Publikacje / Archiwum | historia pozostaje | UI |
| TikTok Studio / Terminarz Meta | `_otworz_*` | przeglądarka/CDP | pełne akcje kanału | właściwy profil | adapter |
| Ustaw termin | `_wybierz_termin`, `ustaw_termin` | `post.json` | Wybierz termin | conflict/rollback | adapter |
| AI warianty opisu | `_ai_warianty_opisu` | webhook, propozycja | kreator dokańczania | nie nadpisuje akceptacji | adapter |
| Zapis opis + termin + pineska | `_zapisz_plan` | `opis.txt`, `post.json` | Treść / Zapisz | wieloplikowa transakcja | UI |
| Muzyka | `_zapisz_muzyke` | `dodaj_muzyke` | Publikowanie | nie oznacza sukcesu | adapter |
| Archiwizuj / przywróć | `_archiwizuj`, `_wroc_z_archiwum` | rdzeń magazynu | menu karty | reguły oryginału | adapter |
| Usuń szkic z listy | `_usun_szkic` | bezpieczne reguły magazynu | menu karty | tylko dozwolony szkic | adapter |
| Odśwież stan paczki | `_odswiez_stan_paczki` | logi / LIVE | Sprawdź na platformie | bez haczyka | adapter |
| TikTok + Meta / TikTok + IG | `_wrzuc_tiktok_plus_*` | most publikacji | partia kanałów | sekwencyjność profilu | adapter |
| Prześlij ponownie | `_wrzuc_ponownie` | uploader + idempotencja | Diagnoza / Ponów | weryfikacja przed retry | adapter |
| TikTok | `_wrzuc(...,'tiktok')` | `tiktok_*_uploader.py` | Przygotuj TikTok | blokada 9224/9223 | adapter |
| Instagram | `_wrzuc(...,'instagram')` | `meta_*_uploader.py` | domyślnie paczka telefonu; pełna akcja w menu | ręczny CTA | adapter |
| Facebook | `_wrzuc(...,'facebook')` | `meta_*_uploader.py` | Przygotuj Facebook | niezależny stan | adapter |
| IG+FB | `_wrzuc(...,'obie')` | Meta crosspost | pełna akcja w menu z ograniczeniem muzyki | jawny cel | adapter |
| Muzyka dobrana | `_muzyka_dobrana`, `daj_sygnal_muzyki` | sygnał uploaderowi | Dokończ etap | nie uruchamia następnego | adapter |
| Ręczny haczyk | `_reczny_haczyk_publikacji`, `oznacz/cofnij_potwierdzenie_damiana` | oryginalne `platformy_stan.haczyk` | Potwierdzam wykonanie | LIVE go nie ustawia | adapter |
| HD | `_zakolejkuj_hd_cicho`, `wideo_hd.py` | plik `-hd` i sumy | status/akcja HD | bez duplikacji | adapter |
| Podgląd okładki / slajdów | `_blok_okladki_publikacji`, `_pasek_slajdow` | realne pliki | miniatura i podgląd | brak ≠ atrapa | UI |
| Otwórz folder paczki | `_otworz_folder_paczki` | Explorer | Otwórz folder | walidacja post_id | UI |
| Kopiuj opis / ścieżkę | `_kopiuj_tekst`, `_kopiuj_sciezke_okladki` | schowek | menu Treść/Podgląd | wartości z paczki | UI |
| Nadzór i błędy | `_petla_pulpit`, `pulpit_wrzutu.py`, `niezawodnosc.py` | logi/status/blokady | panel postępu | etap z logu | adapter |
| Weryfikacja platform | `_odswiez_weryfikacje`, `kalendarz_live.py` | `platformy_stan` | dowód platformy | scheduled ≠ published | adapter |
| Generator opisów | `most_generatora.otworz_generator` | ta sama `studio-kolejka`, marka ATLET/RIGGER | Opisy i styl → Otwórz pełny Generator | rzeczywisty proces i wspólny cel | UI + adapter |
| Paczka telefonu | `MobilePackages.export` | media, opis, hashtagi, manifest i SHA-256 | Paczka na telefon | kontrakt v1 i revision | UI |
| Zdarzenia telefonu | `MobilePackages.import_events` | osobny dziennik JSONL | API importu Mobile | deduplikacja; brak mutacji paczki/haczyka | adapter |
| HD / muzyka / ponowienie | `pulpit_wrzutu`, `most_publikacji` | oryginalne pliki, sygnały i logi | panel Publikowanie | adapter podłączony; blokada konfiguracji jest jawna | UI + adapter |
| Lekcje stylu/procesu/kodu | `learning/*` | SQLite, wersje i status | Uczenie | aktywacja wymaga rozwiązania i testu; cofanie | UI |
