# Korektor Logów HR

Program na Windows do weryfikacji i automatycznej korekty logów czasu pracy z czytników RCP (Roger RCP Master 4 / RACS 5) przed importem do systemu kadrowego (Comarch ERP XL HR).

> Status: **wersja 3.1.0** (2026-11-03). Instalator: [Releases](../../releases/latest)

## Możliwości

- Filtracja podwójnych odbić i anomalii z czytników, wykrywanie pomyłek wejście / wyjście
- Zaokrąglanie wejść i wyjść z logiką godzin ruchomych i ochroną wypracowanego etatu (7h / 8h)
- Zmiany (6-14, 13-21, 16-24, 8-16, 7h) i przejścia przez północ
- Nadgodziny z wyjątkami dla wybranych działów
- Ręczny menedżer danych do weryfikacji wpisów
- Raport braków odbić dla działu HR, plik poprawiony gotowy do importu
- Zgłaszanie błędów z załącznikami przez formularz na diamel.pl

## Dane pracowników

**Program nie zawiera danych pracowników ani haseł.** Lista pracowników (numer, imię i nazwisko, dział, zmiana, czy pracuje) jest w panelu HR na diamel.pl i jest pobierana przy każdym uruchomieniu programu:

1. Przy pierwszym uruchomieniu użytkownik loguje się kontem założonym przez administratora (opcja „Zapamiętaj na tym komputerze” - 30 dni; zapamiętany dostęp jest szyfrowany przez Windows i działa tylko dla tego użytkownika Windows).
2. Program pobiera aktualną listę pracowników, działów i zmian; pracownicy oznaczeni jako „nie pracuje” trafiają automatycznie do ignorowanych.
3. Przycisk „Wyloguj z bazy” usuwa zapamiętany dostęp z komputera.

Administrator edytuje pracowników i konta w panelu `diamel.pl/hr/panel/` - zmiany widać w programie przy następnym uruchomieniu, bez wydawania nowej wersji.

## Uruchomienie ze źródeł

Python 3 (Windows), zależności:

```
pip install pandas pillow
```

```
python Korektor_logow.py
```

## Wydanie nowej wersji

1. Podnieś `VERSION` i dopisz zmiany do `CHANGELOG` w `konfiguracja_app.py`, zrób commit.
2. `python kompilacja.py` buduje program (PyInstaller) i instalator (Inno Setup 6) do `<wersja>/Paczka/`.
3. Na pytanie o publikację odpowiedz `t` - skrypt wypchnie commit i utworzy wydanie `v<wersja>` na GitHub (wymaga [GitHub CLI](https://cli.github.com/) zalogowanego przez `gh auth login`).

Programy sprawdzają aktualizacje w `api.github.com/repos/Kuj0n/Diamel-HR/releases/latest`.

## Licencja

**Wszelkie prawa zastrzeżone** - © 2026 Diamel ([diamel.pl](https://diamel.pl)). Kod jest udostępniony wyłącznie do wglądu, szczegóły w [LICENSE](LICENSE).

Autor: **Mateusz Kujawa (Diamel)** - [diamel.pl](https://diamel.pl)
