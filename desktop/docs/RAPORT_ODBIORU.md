# Raport odbioru — BYKU.PUBLIKACJE DESKTOP

Data: 24.09.2026

## Wynik bieżącego odbioru

- Aplikacja działa lokalnie pod `http://127.0.0.1:8902` i ma skrót `BYKU.PUBLIKACJE DESKTOP.lnk` na pulpicie.
- Adapter odczytał 46 rzeczywistych paczek z produkcyjnego `studio-kolejka`; nie zgłosił chorej paczki.
- Stół ATLET pokazał 20 aktywnych kart i rzeczywiste miniaturki. Widoki 1440, 1280 i 1024 px przeszły test przeglądarkowy.
- Kod Python przeszedł kompilację. Zestaw 5 testów kontraktów stanu i uczenia przeszedł bez błędów.
- Statyczny rejestr obejmuje 110 skryptów Python z oryginału i Generatora. Skryptów nie importowano podczas rozpoznania.
- Dowód platformy i ręczny haczyk są osobnymi polami. `potwierdzony` z danych historycznych jest pokazywany konserwatywnie jako wykrycie w kalendarzu, nie jako automatyczny haczyk.
- TikTok, Instagram i Facebook zachowują oddzielne stany. Instagram nie ustawia stanu Facebooka.
- Blokada uruchomień jest przypisana do profilu/konta (portu CDP), nie tylko do publikacji.
- Edycja treści używa rewizji wyliczanej z realnych plików, zwraca konflikt 409 i zapisuje dziennik transakcji.
- Paczka telefonu zawiera manifest: wersję schematu, post_id, markę, rewizję treści, kanał, listę plików i sumy SHA-256.

## Świadomie zablokowane

Aktualna konfiguracja ma `allow_production_writes=false` oraz `allow_publication=false`. Dzięki temu panel można bezpiecznie testować na prawdziwych danych bez zmiany kolejki i bez uruchomienia uploadu. Przyciski zapisu pokazują konkretny komunikat zamiast udawać sukces.

Nie potwierdzono w tym odbiorze realnego publikowania, odczytu zalogowanych kont Meta/TikTok, Drive/Hostinger ani końcowych kliknięć użytkownika. Tych pozycji nie oznaczono jako ukończone.

## Wyniki automatyczne

```text
compileall: OK
manifest: 110 skryptów
unittest: 7/7 OK
real queue: 46 kart, 0 błędów odczytu
Playwright: 20 wierszy ATLET, 21 obrazów, 0 błędów konsoli
viewport: 1440 / 1280 / 1024 OK
```

## Start i cofnięcie

Start: skrót `BYKU.PUBLIKACJE DESKTOP` na pulpicie albo `start.cmd` w katalogu projektu. Aplikacja pilnuje jednej własnej instancji.

Cofnięcie tej wersji nie wymaga ruszania oryginału: zamknij nowy panel i uruchom dotychczasowy skrót `BYQ Studio`. Nowy projekt nie zastąpił plików oryginalnego Studio.
