import os
import sys

# ==========================================
# KONFIGURACJA I METADANE
# ==========================================
VERSION = "3.1.0"
BUILD_DATE = "2026-11-03 10:00"

CHANGELOG = """
v3.1.0 (2026-11-03)
- Lista pracowników, działy i zmiany pobierane z serwera po zalogowaniu - zawsze aktualne, bez instalowania nowych wersji.
- Logowanie kontem użytkownika z opcją zapamiętania na komputerze; przycisk "Wyloguj z bazy".
- Program nie zawiera danych pracowników ani haseł.
- Aktualizacje programu pobierane z GitHub, zgłoszenia błędów przez formularz na diamel.pl.

v3.0.9 (2026-10-22)
- Aktualizacja bazy pracowników.

v3.0.8 (2026-10-18)
- Aktualizacja bazy pracowników.

v3.0.7 (2026-10-14)
- Aktualizacja bazy pracowników.

v3.0.6 (2026-10-13)
- Aktualizacja bazy pracowników.

v3.0.5 (2026-10-08)
- Poprawa godzin północnych.
- Dodane opcjonalne ostrzeżenie w przypadku wystąpienia północnych wyjść.
- Aktualizacja bazy pracowników.

v3.0.4 (2026-09-19)
- Poprawa liczenia czasu pracy zmian nocnych przekraczających północ.
- Poprawa wykrywania błednego odbijania na wejściu lub wyjściu - wyświetlany jest odpowiedni komunikat.

v3.0.3 (2026-09-09)
- Integracja kalendarza dni roboczych.
- Święta wyliczane są wykorzystując metodę Meeusa/Jonesa/Butchera.
- Dodano sprawdzanie obecności pracownika w dniach roboczych.
- Wdrożono możliwość importu planu urlopowego/nieobecności pracowników wykorzystywanego przy analizie czasu pracy.
- Dodano polę do wybrania pracowników których nieobecność ma być ignorowana w nieprawidłowościach.

v3.0.2 (2026-08-06)
- Zmiana sposobu naliczania nadgodzin dla wybranych działów.
- Dodano rozwijane listy z wyszukiwarką zamiast ręcznych komórek do wpisywania danych pracowników.

v3.0.1 (2026-08-06)
- Poprawa błędów związanych z nieprawidłowem listowaniem północnego wyjścia.

v3.0.0 (2026-07-06)
- Zmiana struktury programu na MVC.

v2.0.0 (2026-07-06)
- Naprawiono nieprawidłowe wykrywanie ikony tkinter.
- Wdrożono automatyczne aktualizacje w tle. Program sam pobiera i instaluje nowsze wersje z serwera po kliknięciu zgody.
- Przejście na dystrybucję z instalatorem (Inno Setup), eliminując problem fałszywych wykryć wirusów OVH.

v1.7.1 (2026-06-11)
- Naprawiono problem z brakiem wyświetlania nowo dodanych pracowników: od od teraz pracownik bez żadnych odbić automatycznie trafia na listę nieprawidłowości z powodem "Brak jakichkolwiek odbić".

v1.7.0 (2026-06-11)
- Wdrożono dynamiczny system filtrowania działów (odczyt z pliku dzialy.json lub status Nieprzypisani).
- Dodano boczny panel filtrów w Menedżerze, pozwalający wyizolować konkretne grupy w locie.
- Dodano przycisk umożliwiający ręczne wygenerowanie i przypisanie brakującego pracownika (np. zgubiona karta) do danego dnia celem edycji.

v1.6.1 (2026-06-11)
- Poprawka błędu kompilacji w mechanizmie odświeżania.

v1.6.0 (2026-06-11)
- CAŁKOWITA PRZEBUDOWA SILNIKA OBLICZEŃ: Ręczne wpisy i edycje w Menedżerze są teraz na żądanie (przycisk Odśwież) poddawane wszystkim algorytmom zaokrąglającym.
- Rozwiązano problem powiększenia checkboxów (zwiększono wysokość wierszy i czytelność tabel).
- Zautomatyzowano odświeżanie - poprawiony pracownik automatycznie znika z listy "Nieprawidłowości".

v1.5.0 (2026-06-11)
- Dodano możliwość zaznaczania wpisów w tabelach Menedżera Korekt.
- Dodano funkcję generowania czytelnych, szczegółowych raportów z wybranych wpisów.

v1.4.0 (2026-06-11)
- Przebudowano Menedżer Korekt: dodano system zakładek pozwalający na podgląd, sortowanie i edycję.

v1.3.0 (2026-06-10)
- Ujednolicenie wersji aplikacji.

v1.2.5 (2026-06-10)
- Wymuszono obowiązek załączania pliku źródłowego, poprawionego oraz raportu podczas wysyłania zgłoszenia błędu.

v1.2.4 (2026-06-09)
- W Menedżerze Korekt dodano 3 kolumnę z oryginalną godziną odbicia (sprzed matematycznego zaokrąglenia), aby mieć podgląd danych źródłowych.

v1.2.3 (2026-06-09)
- Dodano paski przewijania (scrollbar) do tabel w Menedżerze Korekt.
- Dodano możliwość interaktywnego sortowania danych kliknięciem w nagłówki kolumn.
- Ustawiono domyślne sortowanie alfabetyczne wg nazwiska w raporcie nieprawidłowości.

v1.2.2 (2026-06-10)
- Usprawniono formularz zgłoszeniowy o możliwość dodawania wielu zrzutów ekranu/dodatkowych plików jednocześnie.

v1.2.1 (2026-06-09)
- Zgłoszenie błędu wysyła teraz automatycznie kopię (DW) na adres e-mail zgłaszającego.
- Zmieniono logikę nazywania plików: kolejne poprawki tworzą pliki _poprawione_1, _poprawione_2 itd., co zapobiega tworzeniu długich nazw.

v1.2.0 (2026-06-09)
- DODANO INTERAKTYWNY MENEDŻER KOREKT: Program wstrzymuje zapis, jeśli wykryje nieprawidłowości, i pozwala na pełną, ręczną edycję list odbić pracownika w oknie graficznym.

v1.1.3 (2026-06-08)
- Dodano mechanizm wczytywania list sztywnych zmian i 7h etatu z zewnętrznego pliku przy kompilacji.

v1.1.2 (2026-06-08)
- Naprawiono błąd nadpisywania wejść przy wielokrotnych odbiciach w ciągu dnia (np. przepustki).
- Usprawniono logikę statusów, by w przypadku kilku wyjść z rzędu program zachowywał ostatnie z nich.

v1.1.1 (2026-06-01)
- Dodano obsługę nowej sztywnej zmiany: 16:00 - 24:00 dla wybranych pracowników.

v1.1.0 (2026-05-28)
- Dodano moduł przypisywania sztywnych zmian (6-14, 13-21, 8-16) dla wybranych pracowników.
- Dodano obsługę dwuzmianowości przy sztywnych regułach (program sam decyduje w oparciu o godzinę wejścia).

v1.0.9 (2026-05-27)
- Rozrzerzono do 30 minut filtrację odwrotnych wejść/wyjść.

v1.0.8 (2026-05-27)
- Naprawiono problem z podwójnymi odbiciami na czytniku; rozbudowano filtr pomyłek o usuwanie błędnego wyjścia (16/25) następującego bezpośrednio (do 5 min) po wejściu (00).

v1.0.7 (2026-05-21)
- Dodano filtrowanie - program usuwa odbicia wyjścia z nocy, jeśli są pierwszym wpisem w pliku - z tolerancją do 05:00.

v1.0.6 (2026-05-20)
- Naprawiono błąd NameError w interfejsie graficznym.
- Usprawniono logikę północy: opóźnione wyjścia po północy.

v1.0.5 (2026-05-19)
- Dodano ograniczenie rozpoczęcia naliczania nadgodzin, np. od 30 min.
- Dodano funkcję skokowego naliczania nadgodzin, np. co 30 min.
- Poprawiono czytelność, przeorganowano interfejs.

v1.0.4 (2026-05-19)
- Poprawiono wykrywanie błędnego odbicia z dnia poprzedniego przy rozpoczynaniu logowania.

v1.0.3 (2026-05-19)
- Oddzielono sekrety do osobnego pliku budowania.
- Poprawiono wykrywanie i przenoszenie wyjścia o północy z dnia kolejnego zamiast bieżącego.

v1.0.2 (2026-05-18)
- Dodano zamianę końcowej przepustki (kod 25) na wyjście z pracy (kod 16).
- Wprowadzono listę pracowników, dla których ochrona i rozliczanie etatu liczy się do 7 godzin zamiast 8.
- Zmieniono granicę błędu zaokrąglenia z 3 na 2min w celu poprawy jakości wyboru kierunku zaokrąglania.

v1.0.1 (2026-05-14)
- Zmiana logiki dla godzin ruchomych.
- Usunięto błąd powielających się wyjść o 22:00.

v1.0
- Pierwsze wydanie.
"""

_ANTI_FP_SALT = "D1AM3L_H4SH_SH1FT_V183_0X9A8B7C"

# ==========================================
# SERWER: aktualizacje (GitHub), lista pracowników i zgłoszenia (diamel.pl)
# Program nie zawiera danych pracowników ani haseł - lista pracowników
# jest pobierana po zalogowaniu (panel HR: diamel.pl/hr/panel/).
# ==========================================
NAZWA_PROGRAMU = "hr"
GITHUB_REPO = "Kuj0n/Diamel-HR"
URL_HR_API = "https://diamel.pl/api/hr.php"
URL_ZGLOSZEN = "https://diamel.pl/api/zgloszenie.php"

KODY_MAPA = {
    "00": "00 - Wejście",
    "16": "16 - Wyjście",
    "18": "18 - Przerwa",
    "25": "25 - Przepustka"
}

def sciezka_do_zasobu(relatywna_sciezka):
    """ Pancerna funkcja szukająca plików zasobów w trybie .exe i developerskim """
    katalogi = [
        os.path.abspath("."),
        os.path.join(os.path.abspath("."), "_internal")
    ]
    if hasattr(sys, '_MEIPASS'):
        katalogi.insert(0, sys._MEIPASS)
        katalogi.insert(1, os.path.join(sys._MEIPASS, "_internal"))
        
    if hasattr(sys, 'executable'):
        baza_exe = os.path.dirname(sys.executable)
        katalogi.append(baza_exe)
        katalogi.append(os.path.join(baza_exe, "_internal"))
        
    for k in katalogi:
        pelna = os.path.join(k, relatywna_sciezka)
        if os.path.exists(pelna):
            return pelna
            
    return relatywna_sciezka