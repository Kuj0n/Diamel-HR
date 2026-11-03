"""
interfejs.py

Funkcje wywoływane z okna programu (ui/app.js -> window.pywebview.api.<funkcja>).
Obliczenia: silnik.py. Serwer (logowanie, lista pracowników, reguły firmowe): serwer_hr.py.
Każda funkcja zwraca dane, które da się zamienić na JSON (słowniki, listy, teksty, liczby).
"""
import base64
import glob
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import threading
import urllib.request
from datetime import datetime

import webview

import serwer_hr
from konfiguracja_app import VERSION, BUILD_DATE, CHANGELOG, NAZWA_PROGRAMU, URL_ZGLOSZEN, KODY_MAPA
from narzedzia import pobierz_wydanie, wez_krotke, NAGLOWKI, ZALACZNIKI_MAX_MB
from silnik import Silnik, DOMYSLNE, LISTY_ZMIAN, wczytaj_plan_urlopow, format_czas_gui
from obliczenia import parse_czas_do_minut, formatuj_minuty_do_czasu
import raport_pdf

KATALOG_DANYCH = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Diamel", "Korektor HR")
PLIK_USTAWIEN = os.path.join(KATALOG_DANYCH, "ustawienia.json")
PLIK_HISTORII = os.path.join(KATALOG_DANYCH, "historia.json")
HISTORIA_MAX = 50

# Reguły, których nie ustawia się w programie: listy zmian przychodzą z panelu HR (lista pracowników),
# chk_raport (zawsze Menedżer danych) w nowym oknie nie ma znaczenia - lista do sprawdzenia jest zawsze widoczna
NIE_REGULY = set(LISTY_ZMIAN) | {"chk_raport"}
# Reguły, które zmienia tylko administrator (panel HR) - bez zmian lokalnych w programie
TYLKO_ADMIN = {"pracownicy_ignorowani"}

KODY_KROTKO = {"00": "wejście", "16": "wyjście", "18": "przerwa", "25": "przepustka"}
PULS_SEKUNDY = 120  # sygnał "program otwarty" dla panelu HR (Status -> Teraz)

USTAWIENIA_PROGRAMU = {
    "motyw": "system",          # jasny / ciemny / system
    "rozmiar": "normalny",      # maly / normalny / duzy
    "eksport_txt": False,
    "eksport_pdf": True,
    "pdf_podpisy": False,
    "pdf_kratki": True,
    "pdf_przy_zapisie": False,  # raport PDF zapisywany automatycznie razem z plikiem ERP
    "folder_zapisu": "",        # pusty = obok pliku źródłowego
    "otworz_folder": True,
}


def _czytaj_json(sciezka, domyslnie):
    try:
        with open(sciezka, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return domyslnie


def _zapisz_json(sciezka, dane):
    os.makedirs(os.path.dirname(sciezka), exist_ok=True)
    tymczasowy = sciezka + ".tmp"
    with open(tymczasowy, "w", encoding="utf-8") as f:
        json.dump(dane, f, ensure_ascii=False, indent=2)
    os.replace(tymczasowy, sciezka)


def rodzaj_uwagi(uwaga):
    """Rodzaj pozycji do sprawdzenia: blad / niepelny / ostrzezenie / nieobecnosc."""
    czesci = [u.strip() for u in uwaga.split(",") if u.strip()]
    if any(c == "Nieobecność" for c in czesci):
        return "nieobecnosc"
    if any(not (c.startswith("Ostrzeżenie") or c.startswith("Niepełne")) for c in czesci):
        return "blad"
    if any(c.startswith("Niepełne") for c in czesci):
        return "niepelny"
    return "ostrzezenie"


class Api:
    def __init__(self):
        self._okno = None
        self.dane_serwera = {}
        self.reguly_firmowe = {}
        self.reguly_wersja = ""
        # Reguły firmowe przychodzą z serwera; tu tylko zmiany lokalne użytkownika i ustawienia programu
        zapis = _czytaj_json(PLIK_USTAWIEN, {})
        self.reguly_lokalne = {k: v for k, v in zapis.get("reguly_lokalne", {}).items() if k not in TYLKO_ADMIN}
        self.program = {**USTAWIENIA_PROGRAMU, **zapis.get("program", {})}
        self._wyczysc_sesje()

    def _wyczysc_sesje(self):
        self.plik_rcp = ""
        self.linie_rcp = []
        self.plik_urlopow = ""
        self.urlopy = {}
        self._silnik = None
        self.reczne = {}      # (data, nr) -> lista zdarzeń poprawionych ręcznie (zachowane przy ponownym przetworzeniu)
        self.statusy = {}     # (data, nr) -> 'sprawdzone' / 'pominiete'
        self.anomalie = []
        self.linie_raportu = []
        self.id_historii = None

    # ------------------------------------------------------------------ start, aktualizacje, logowanie

    def informacje(self):
        return {"wersja": VERSION, "data": BUILD_DATE[:10], "program": self.program, "komputer": platform.node(),
                "changelog": CHANGELOG.strip()}

    def sprawdz_aktualizacje(self):
        """Najnowsze wydanie z GitHub. Działa bez logowania - poprawkę da się zainstalować, nawet gdy logowanie nie działa."""
        try:
            dane, zalaczniki = pobierz_wydanie()
        except Exception as e:
            return {"ok": False, "blad": str(e)}
        wersja = dane.get("tag_name", "0.0.0").lstrip("vV")
        link = next((u for n, u in zalaczniki.items() if n.lower().endswith(".exe")), "")
        try:
            nowsza = bool(link) and wez_krotke(wersja) > wez_krotke(VERSION)
        except ValueError:
            nowsza = False
        return {"ok": True, "nowsza": nowsza, "wersja": wersja, "opis": dane.get("body") or "", "link": link}

    def pobierz_aktualizacje(self, link):
        """Pobiera instalator w tle; postęp: window.postepAktualizacji(procent), koniec: window.aktualizacjaPobrana(ok, tekst)."""
        cel = os.path.join(tempfile.gettempdir(), "Aktualizacja_HR_Instalator.exe")

        def postep(bloki, rozmiar_bloku, calosc):
            if calosc > 0 and self._okno:
                self._okno.evaluate_js(f"window.postepAktualizacji && window.postepAktualizacji({min(100, int(bloki * rozmiar_bloku * 100 / calosc))})")

        def watek():
            try:
                urllib.request.urlretrieve(link, cel, postep)
                self._okno.evaluate_js("window.aktualizacjaPobrana(true, '')")
            except Exception as e:
                self._okno.evaluate_js(f"window.aktualizacjaPobrana(false, {json.dumps(str(e))})")
        threading.Thread(target=watek, daemon=True).start()
        return {"ok": True}

    def uruchom_instalator(self):
        cel = os.path.join(tempfile.gettempdir(), "Aktualizacja_HR_Instalator.exe")
        subprocess.run(["powershell", "-NoProfile", "-Command", f"Unblock-File -Path '{cel}'"], shell=True)
        subprocess.Popen([cel, "/FORCECLOSEAPPLICATIONS", "/NOCANCEL"])
        os._exit(0)

    def zaloguj(self, login, haslo, zapamietaj):
        try:
            odp = serwer_hr.zapytanie({"akcja": "zaloguj", "login": login.strip(), "haslo": haslo,
                                       "zapamietaj": bool(zapamietaj), "komputer": platform.node()})
        except Exception as e:
            return {"ok": False, "blad": f"Brak połączenia z serwerem: {e}"}
        if not odp.get("ok"):
            return {"ok": False, "blad": odp.get("blad", "Logowanie nie powiodło się.")}
        self._token = odp["token"]
        self.program["login"] = login.strip()
        self._zapisz_ustawienia()
        if zapamietaj:
            serwer_hr.zapisz_token(odp["token"])
        return {"ok": True}

    def nie_pamietam_hasla(self, login):
        try:
            odp = serwer_hr.zapytanie({"akcja": "przypomnij", "login": login.strip(), "komputer": platform.node()})
        except Exception as e:
            return {"ok": False, "blad": f"Brak połączenia z serwerem: {e}"}
        return {"ok": bool(odp.get("ok")), "blad": odp.get("blad", "")}

    def pobierz_dane(self):
        """Lista pracowników, działy, zmiany i reguły firmowe z serwera. {'ok', 'zaloguj': True gdy trzeba się zalogować}."""
        token = getattr(self, "_token", None) or serwer_hr.wczytaj_token()
        if not token:
            return {"ok": False, "zaloguj": True}
        try:
            odp = serwer_hr.zapytanie({"akcja": "dane", "token": token})
        except Exception as e:
            return {"ok": False, "blad": f"Brak połączenia z serwerem: {e}"}
        if not odp.get("ok"):
            serwer_hr.usun_token()
            self._token = None
            return {"ok": False, "zaloguj": bool(odp.get("zaloguj")), "blad": odp.get("blad", "")}
        self._token = token
        self.dane_serwera = odp
        self._start_puls()
        self.reguly_firmowe = {k: v for k, v in (odp.get("reguly") or {}).items() if k in DOMYSLNE and k not in NIE_REGULY}
        self.reguly_wersja = odp.get("reguly_wersja", "")
        # Zmiany lokalne równe regułom firmowym przestają być zmianami
        if self.reguly_firmowe:
            self.reguly_lokalne = {k: v for k, v in self.reguly_lokalne.items() if self.reguly_firmowe.get(k, DOMYSLNE[k]) != v}
            self._zapisz_ustawienia()
        return {"ok": True, "pracownikow": len(odp.get("pracownicy", {})), "wersja_bazy": odp.get("wersja", ""),
                "login": odp.get("login") or self.program.get("login", ""), "reguly_wersja": self.reguly_wersja}

    def _start_puls(self):
        """Co 2 minuty informuje serwer, że program jest otwarty (panel HR pokazuje "sesja otwarta")."""
        if getattr(self, "_puls", None):
            return
        self._puls = threading.Event()

        def watek():
            while not self._puls.is_set():
                token = getattr(self, "_token", None)
                if token:
                    try:
                        serwer_hr.zapytanie({"akcja": "obecnosc", "token": token, "otwarta": True}, timeout=10.0)
                    except Exception:
                        pass
                self._puls.wait(PULS_SEKUNDY)
        threading.Thread(target=watek, daemon=True).start()

    def zakoncz_sesje(self):
        """Przy zamknięciu okna: sesja w panelu od razu jako zamknięta (bez czekania 5 minut)."""
        if getattr(self, "_puls", None):
            self._puls.set()
        token = getattr(self, "_token", None)
        if token:
            try:
                serwer_hr.zapytanie({"akcja": "obecnosc", "token": token, "otwarta": False}, timeout=3.0)
            except Exception:
                pass

    def wyloguj(self):
        serwer_hr.wyloguj()
        self._token = None
        self.dane_serwera, self.reguly_firmowe, self.reguly_wersja = {}, {}, ""
        return {"ok": True}

    # ------------------------------------------------------------------ ustawienia programu

    def _zapisz_ustawienia(self):
        _zapisz_json(PLIK_USTAWIEN, {"reguly_lokalne": self.reguly_lokalne, "program": self.program})

    def ustaw_program(self, klucz, wartosc):
        if klucz in USTAWIENIA_PROGRAMU:
            self.program[klucz] = wartosc
            self._zapisz_ustawienia()
        return self.program

    def wybierz_folder_zapisu(self):
        wynik = self._okno.create_file_dialog(webview.FileDialog.FOLDER)
        if wynik:
            self.ustaw_program("folder_zapisu", wynik[0])
        return self.program

    # ------------------------------------------------------------------ reguły korekty (firmowe + zmiany lokalne)

    def reguly_aktualne(self):
        return {**DOMYSLNE, **self.reguly_firmowe, **self.reguly_lokalne}

    def reguly(self):
        aktualne = self.reguly_aktualne()
        return {
            "aktualne": aktualne,
            "firmowe": {**DOMYSLNE, **self.reguly_firmowe},
            "lokalne": self.reguly_lokalne,
            "sa_firmowe": bool(self.reguly_firmowe),
            "wersja": self.reguly_wersja,
            "listy_z_panelu": {k: aktualne[k] for k in LISTY_ZMIAN},
            "niepracujacy_z_panelu": self.dane_serwera.get("ignorowani", ""),
        }

    def zmien_regule(self, klucz, wartosc):
        if klucz in DOMYSLNE and klucz not in NIE_REGULY and klucz not in TYLKO_ADMIN:
            if {**DOMYSLNE, **self.reguly_firmowe}[klucz] == wartosc:
                self.reguly_lokalne.pop(klucz, None)
            else:
                self.reguly_lokalne[klucz] = wartosc
            self._zapisz_ustawienia()
        return self.reguly()

    def przywroc_firmowe(self, klucz=None):
        if klucz:
            self.reguly_lokalne.pop(klucz, None)
        else:
            self.reguly_lokalne = {}
        self._zapisz_ustawienia()
        return self.reguly()

    def zaproponuj_reguly(self, klucze, komentarz):
        token = getattr(self, "_token", None) or serwer_hr.wczytaj_token()
        zmiany = {k: self.reguly_lokalne[k] for k in klucze if k in self.reguly_lokalne}
        if not zmiany:
            return {"ok": False, "blad": "Brak zmian do zaproponowania."}
        try:
            odp = serwer_hr.zapytanie({"akcja": "zaproponuj_reguly", "token": token, "zmiany": zmiany, "komentarz": komentarz})
        except Exception as e:
            return {"ok": False, "blad": f"Brak połączenia z serwerem: {e}"}
        return {"ok": bool(odp.get("ok")), "blad": odp.get("blad", "")}

    # ------------------------------------------------------------------ pliki

    def wybierz_plik_rcp(self):
        wynik = self._okno.create_file_dialog(webview.FileDialog.OPEN, file_types=("Pliki RCP (*.txt)",))
        return self.wczytaj_plik(wynik[0]) if wynik else None

    def wybierz_plik_urlopow(self):
        wynik = self._okno.create_file_dialog(webview.FileDialog.OPEN, file_types=("Plan nieobecności (*.xls;*.xlsx)",))
        return self.wczytaj_plik(wynik[0]) if wynik else None

    def wczytaj_plik(self, sciezka):
        """Plik RCP (.txt) albo plan nieobecności (.xls/.xlsx) - także po przeciągnięciu na okno."""
        if not sciezka or not os.path.isfile(sciezka):
            return {"ok": False, "blad": "Nie znaleziono pliku."}
        if sciezka.lower().endswith((".xls", ".xlsx")):
            try:
                self.urlopy = wczytaj_plan_urlopow(sciezka)
            except ImportError:
                return {"ok": False, "blad": "Brak biblioteki do odczytu Excela (pandas, xlrd, openpyxl)."}
            except Exception as e:
                return {"ok": False, "blad": f"Nie udało się odczytać planu nieobecności: {e}"}
            self.plik_urlopow = sciezka
        else:
            try:
                with open(sciezka, encoding="utf-8") as f:
                    linie = f.readlines()
            except UnicodeDecodeError:
                with open(sciezka, encoding="cp1250") as f:
                    linie = f.readlines()
            if not any(len(l.strip().split(";")) == 3 for l in linie):
                return {"ok": False, "blad": "To nie wygląda na plik RCP (data.godzina;numer;kod)."}
            if os.path.abspath(sciezka) != os.path.abspath(self.plik_rcp or ""):
                self.reczne, self.statusy, self.id_historii = {}, {}, None
            self.plik_rcp, self.linie_rcp = sciezka, linie
        return self.przetworz()

    # ------------------------------------------------------------------ przetwarzanie

    def przetworz(self):
        if not self.linie_rcp:
            return self.stan()
        s = Silnik(self.reguly_aktualne(), self.dane_serwera, self.urlopy)
        s.przetworz(self.linie_rcp)
        for klucz, zdarzenia in self.reczne.items():
            s.dane_do_zapisu[klucz] = [dict(z) for z in zdarzenia]
        self._silnik = s
        self._odswiez_anomalie()
        self._zapisz_historie()
        return self.stan()

    def _odswiez_anomalie(self):
        wpisy, _, self.linie_raportu = self._silnik.generuj_raporty()
        self.anomalie = []
        for w in wpisy:
            klucz = (w["data"], w["pracownik"])
            self.anomalie.append({**w, "id": f"{w['data']}|{w['pracownik']}", "rodzaj": rodzaj_uwagi(w["uwaga"]),
                                  "status": self.statusy.get(klucz, ""), "reczna": klucz in self.reczne})

    def _statystyki(self):
        zrodlo = [l for l in self.linie_rcp if len(l.strip().split(";")) == 3]
        wynik = [z for zdarzenia in self._silnik.dane_do_zapisu.values() for z in zdarzenia] if self._silnik else []
        zmienione = sum(1 for z in wynik if z.get("czas_oryg") != z["czas"])
        daty = sorted({l[:10] for l in zrodlo})
        licz = lambda r: sum(1 for a in self.anomalie if a["rodzaj"] == r)
        do_spr = [a for a in self.anomalie if a["rodzaj"] != "nieobecnosc" and not a["status"]]
        return {
            "pracownikow": len({l.strip().split(";")[1] for l in zrodlo}),
            "zdarzen": len(zrodlo), "w_pliku_erp": len(wynik), "skorygowane": zmienione,
            "usuniete": max(0, len(zrodlo) - len(wynik)),
            "od": daty[0] if daty else "", "do": daty[-1] if daty else "",
            "bledy": licz("blad"), "niepelne": licz("niepelny"), "ostrzezenia": licz("ostrzezenie"), "nieobecnosci": licz("nieobecnosc"),
            # Gotowe = oznaczone jako sprawdzone + poprawione ręcznie (poprawiony dzień zwykle znika z listy)
            "do_sprawdzenia": len(do_spr),
            "sprawdzone": sum(1 for a in self.anomalie if a["status"]) + sum(1 for k in self.reczne if k not in {(a["data"], a["pracownik"]) for a in self.anomalie}),
        }

    def stan(self):
        """Wszystko, czego potrzebuje pulpit."""
        rcp = {"sciezka": self.plik_rcp, "nazwa": os.path.basename(self.plik_rcp)} if self.plik_rcp else None
        urlopy = ({"sciezka": self.plik_urlopow, "nazwa": os.path.basename(self.plik_urlopow),
                   "pracownikow": len(self.urlopy), "dni": sum(len(v) for v in self.urlopy.values())} if self.plik_urlopow else None)
        return {"ok": True, "rcp": rcp, "urlopy": urlopy, "statystyki": self._statystyki() if self._silnik else None,
                "anomalie": self.anomalie, "reczne": len(self.reczne), "zmienione_reguly": len(self.reguly_lokalne),
                "dzialy": sorted({a["dzial"] for a in self.anomalie})}

    # ------------------------------------------------------------------ korekta dnia

    def _klucz(self, id_):
        data, nr = id_.split("|", 1)
        return data, nr

    def dzien(self, id_):
        klucz = self._klucz(id_)
        s = self._silnik
        zdarzenia = [dict(z) for z in s.dane_do_zapisu.get(klucz, [])]
        ctx = s.kontekst_pracownikow.get(klucz, {})
        anomalia = next((a for a in self.anomalie if a["id"] == id_), None)
        typ = ctx.get("typ_zmiany", "---")
        wymiar = ctx.get("wymiar", 420 if klucz[1] in [x.strip() for x in s.u["pracownicy_7h"].replace(";", ",").split(",")] else 480)
        return {
            "id": id_, "data": klucz[0], "nr": klucz[1],
            "nazwisko": s.baza_pracownikow.get(klucz[1], "---"), "dzial": s.pobierz_dzial_pracownika(klucz[1]),
            "typ_zmiany": typ, "wymiar": wymiar, "uwaga": anomalia["uwaga"] if anomalia else "",
            "rodzaj": anomalia["rodzaj"] if anomalia else "", "status": self.statusy.get(klucz, ""),
            "zdarzenia": [{"czas": z["czas"], "czas_oryg": z.get("czas_oryg", ""), "kod": z["kod"],
                           "czas_gui": format_czas_gui(z["czas"]), "oryg_gui": format_czas_gui(z.get("czas_oryg", "---")),
                           "opis": KODY_MAPA.get(z["kod"], z["kod"])} for z in zdarzenia],
            "propozycje": self._propozycje(zdarzenia, typ, wymiar, anomalia["uwaga"] if anomalia else ""),
            "kody": KODY_MAPA, "reczna": klucz in self.reczne,
        }

    @staticmethod
    def _godziny_zmiany(typ):
        if typ.startswith("Sztywna "):
            od, do = typ[len("Sztywna "):].split("-")
            return od, ("24:00" if do == "00:00" else do)
        return {"Zmiana 1": ("06:00", "14:00"), "Zmiana 2": ("14:00", "22:00")}.get(typ, (None, None))

    def _propozycje(self, zdarzenia, typ, wymiar, uwaga):
        """Gotowe poprawki do zatwierdzenia jednym kliknięciem (nic nie zmieniają, dopóki użytkownik ich nie przyjmie)."""
        wynik = []
        od, do = self._godziny_zmiany(typ)
        wejscia = [z for z in zdarzenia if z["kod"] == "00"]
        wyjscia = [z for z in zdarzenia if z["kod"] in ("16", "25")]
        if "Brak wyjścia" in uwaga and wejscia:
            ost = wejscia[-1]["czas"]
            czas = do if do and parse_czas_do_minut(do) > parse_czas_do_minut(ost) else formatuj_minuty_do_czasu(parse_czas_do_minut(ost) + wymiar)
            wynik.append({"akcja": "dodaj", "czas": czas, "kod": "16",
                          "opis": f"Wyjście (16) o {format_czas_gui(czas)} - " + ("koniec zmiany " + typ.replace("Sztywna ", "") if do else f"wejście + {wymiar // 60}h")})
        if "Brak wejścia" in uwaga and wyjscia:
            pierwsze = wyjscia[0]["czas"]
            czas = od if od and parse_czas_do_minut(od) < parse_czas_do_minut(pierwsze) else formatuj_minuty_do_czasu(max(0, parse_czas_do_minut(pierwsze) - wymiar))
            wynik.append({"akcja": "dodaj", "czas": czas, "kod": "00",
                          "opis": f"Wejście (00) o {format_czas_gui(czas)} - " + ("początek zmiany" if od else f"wyjście - {wymiar // 60}h")})
        for i in range(len(zdarzenia) - 1):
            a, b = zdarzenia[i], zdarzenia[i + 1]
            if "Powielone wejście" in uwaga and a["kod"] == b["kod"] == "00":
                wynik.append({"akcja": "usun", "indeks": i + 1, "opis": f"Usuń powtórzone wejście {format_czas_gui(b['czas'])}"})
                break
            if "Powielone wyjście" in uwaga and a["kod"] in ("16", "25") and b["kod"] in ("16", "25"):
                wynik.append({"akcja": "usun", "indeks": i, "opis": f"Usuń wcześniejsze wyjście {format_czas_gui(a['czas'])}"})
                break
        return wynik

    def zapisz_dzien(self, id_, zdarzenia, status="sprawdzone"):
        """Ręczna korekta dnia: zdarzenia [{czas 'HH:MM' (24+ = po północy), kod}] w kolejności czasu."""
        klucz = self._klucz(id_)
        oryginal = {(z["czas"], z["kod"]): z.get("czas_oryg", z["czas"]) for z in self._silnik.dane_do_zapisu.get(klucz, [])}
        nowe = []
        for z in sorted(zdarzenia, key=lambda z: parse_czas_do_minut(z["czas"])):
            nowe.append({"czas": z["czas"], "kod": z["kod"], "czas_oryg": oryginal.get((z["czas"], z["kod"]), z.get("czas_oryg") or z["czas"])})
        self.reczne[klucz] = nowe
        self._silnik.dane_do_zapisu[klucz] = [dict(z) for z in nowe]
        if status:
            self.statusy[klucz] = status
        self._odswiez_anomalie()
        self._zapisz_historie()
        return self.stan()

    def oznacz(self, id_, status):
        klucz = self._klucz(id_)
        if status:
            self.statusy[klucz] = status
        else:
            self.statusy.pop(klucz, None)
        self._odswiez_anomalie()
        return self.stan()

    def cofnij_reczna(self, id_):
        klucz = self._klucz(id_)
        self.reczne.pop(klucz, None)
        self.statusy.pop(klucz, None)
        return self.przetworz()

    def dodaj_zdarzenie(self, nr, data, czas, kod):
        """Zdarzenie w dniu, którego nie ma na liście (np. pracownik bez odbić)."""
        klucz = (data, nr)
        if not self._silnik:
            return {"ok": False, "blad": "Najpierw wczytaj plik RCP."}
        lista = [dict(z) for z in self._silnik.dane_do_zapisu.get(klucz, [])] + [{"czas": czas, "kod": kod, "czas_oryg": czas}]
        return self.zapisz_dzien(f"{data}|{nr}", lista)

    def pracownicy(self):
        s = self._silnik
        nr = set(s.baza_pracownikow) | {p for _, p in s.dane_do_zapisu} if s else set(self.dane_serwera.get("pracownicy", {}))
        baza = self.dane_serwera.get("pracownicy", {})
        return [{"nr": n, "nazwisko": baza.get(n, "---")} for n in sorted(nr)]

    def dzialy(self):
        return sorted({d for d in self.dane_serwera.get("dzialy", {}).values() if d})

    def wpisy(self, nr=None, data=None):
        """Wszystkie wpisy (jak 'Wszystkie wpisy' w Menedżerze danych) - filtr po pracowniku i/lub dniu."""
        s = self._silnik
        if not s:
            return []
        wynik = []
        for (d, p), zdarzenia in sorted(s.dane_do_zapisu.items()):
            if (nr and p != nr) or (data and d != data):
                continue
            wynik.append({"id": f"{d}|{p}", "data": d, "nr": p, "nazwisko": s.baza_pracownikow.get(p, "---"),
                          "dzial": s.pobierz_dzial_pracownika(p), "typ_zmiany": s.kontekst_pracownikow.get((d, p), {}).get("typ_zmiany", "---"),
                          "zdarzenia": " · ".join(f"{format_czas_gui(z['czas'])} {KODY_KROTKO.get(z['kod'], z['kod'])}" for z in zdarzenia)})
        return wynik

    # ------------------------------------------------------------------ zapis do ERP i raporty

    def _do_pominiecia(self):
        return {(a["data"], a["pracownik"]) for a in self.anomalie if a["rodzaj"] == "blad" and not a["status"]}

    def zapisz_erp(self, tryb=None):
        """
        tryb None: gdy zostały niesprawdzone pozycje -> {'pytanie': ...} (okno wyboru w programie).
        tryb 'wszystko': zapis z niepoprawionymi wpisami; 'pomin': bez dni z niepoprawionymi błędami.
        """
        if not self._silnik:
            return {"ok": False, "blad": "Najpierw wczytaj plik RCP."}
        niesprawdzone = [a for a in self.anomalie if a["rodzaj"] != "nieobecnosc" and not a["status"]]
        if tryb is None and niesprawdzone:
            return {"ok": False, "pytanie": True, "bledy": sum(1 for a in niesprawdzone if a["rodzaj"] == "blad"),
                    "ostrzezenia": sum(1 for a in niesprawdzone if a["rodzaj"] != "blad")}
        pomijane = self._do_pominiecia() if tryb == "pomin" else set()
        dane = {k: v for k, v in self._silnik.dane_do_zapisu.items() if k not in pomijane}
        folder = self.program["folder_zapisu"] or os.path.dirname(self.plik_rcp)
        path_wynik, path_raport = self._silnik.generuj_nazwy_plikow(os.path.join(folder, os.path.basename(self.plik_rcp)))
        with open(path_wynik, "w", encoding="utf-8") as f:
            f.write(self._silnik.tresc_pliku_erp(dane))
        zapisane = [path_wynik]
        if self.program["eksport_txt"] and self.linie_raportu:
            with open(path_raport, "w", encoding="utf-8") as f:
                f.write(self._tresc_txt(pomijane))
            zapisane.append(path_raport)
        if self.program["eksport_pdf"] and self.program["pdf_przy_zapisie"]:
            zapisane.append(self._zapisz_pdf(path_raport[:-4] + ".pdf", pomijane))
        self._zapisz_historie(zapisane=zapisane, pominieto=len(pomijane))
        if self.program["otworz_folder"]:
            self.otworz_folder(path_wynik)
        return {"ok": True, "pliki": zapisane, "pominieto": len(pomijane)}

    def _tresc_txt(self, pomijane=()):
        tresc = Silnik.tresc_raportu_brakow(self.linie_raportu)
        if pomijane:
            tresc += "\n\n--- POMINIĘTE W PLIKU ERP (niepoprawione błędy) ---\n" + "\n".join(
                f"{d} | Pracownik {p} ({self._silnik.baza_pracownikow.get(p, '---')})" for d, p in sorted(pomijane))
        return tresc

    def _zapisz_pdf(self, sciezka, pomijane=()):
        def odbicia(a):
            zd = self._silnik.dane_do_zapisu.get((a["data"], a["pracownik"]), [])
            return " · ".join(f"{KODY_KROTKO.get(z['kod'], z['kod'])} {format_czas_gui(z['czas'])}"
                              + (f" (RCP {format_czas_gui(z['czas_oryg'])})" if z.get("czas_oryg") not in (None, "", "---", z["czas"]) else "") for z in zd)
        # Raport PDF = to, co zaznaczone w filtrach listy (rodzaje problemów i działy); bez filtra - wszystko
        rodzaje, dzialy = getattr(self, "_filtr_raportu", (None, None))
        wybrane = [a for a in self.anomalie if (not rodzaje or a["rodzaj"] in rodzaje) and (not dzialy or a["dzial"] in dzialy)]
        zakres = []
        if dzialy:
            nazwy_dzialow = sorted(d for d in dzialy if d in {a["dzial"] for a in self.anomalie})
            zakres.append("działy: " + ", ".join(nazwy_dzialow) if nazwy_dzialow else "żaden dział")
        if rodzaje and set(rodzaje) != {"blad", "niepelny", "ostrzezenie", "nieobecnosc"}:
            nazwy = {"blad": "błędy", "niepelny": "niepełne", "ostrzezenie": "ostrzeżenia", "nieobecnosc": "nieobecności"}
            zakres.append("tylko " + ", ".join(nazwy[r] for r in nazwy if r in rodzaje))
        raport_pdf.zapisz(sciezka, anomalie=[{**a, "odbicia": odbicia(a)} for a in wybrane if a["rodzaj"] != "nieobecnosc"], zakres="; ".join(zakres),
                          statystyki=self._statystyki(), plik=os.path.basename(self.plik_rcp), uzytkownik=self.dane_serwera.get("login") or self.program.get("login", ""),
                          wersja=VERSION, podpisy=self.program["pdf_podpisy"],
                          kratki=self.program["pdf_kratki"], pominiete=sorted(pomijane), nazwiska=self._silnik.baza_pracownikow,
                          nieobecnosci=[a for a in wybrane if a["rodzaj"] == "nieobecnosc"])
        return sciezka

    def ustaw_filtr_raportu(self, rodzaje, dzialy):
        """Filtry z listy na pulpicie - raport PDF zawiera tylko zaznaczone rodzaje problemów i działy (puste = wszystkie)."""
        self._filtr_raportu = (set(rodzaje or []), set(dzialy or []))
        return {"ok": True}

    def eksport_raportu(self, format_):
        """Raport zapisywany od razu w folderze zapisu (domyślnie obok pliku z RCP): <plik>_RAPORT_BRAKOW_<n>.<txt|pdf>."""
        if not self._silnik:
            return {"ok": False, "blad": "Najpierw wczytaj plik RCP."}
        folder = self.program["folder_zapisu"] or os.path.dirname(self.plik_rcp)
        rdzen = os.path.splitext(os.path.basename(self.plik_rcp))[0]
        n = 1
        while os.path.exists(sciezka := os.path.join(folder, f"{rdzen}_RAPORT_BRAKOW_{n}.{format_}")):
            n += 1
        if format_ == "pdf":
            self._zapisz_pdf(sciezka)
        else:
            with open(sciezka, "w", encoding="utf-8") as f:
                f.write(self._tresc_txt())
        os.startfile(sciezka)
        return {"ok": True, "plik": sciezka}

    def otworz_folder(self, sciezka):
        if os.path.isfile(sciezka):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(sciezka)])
        elif os.path.isdir(sciezka):
            os.startfile(sciezka)
        return {"ok": True}

    def otworz_strone(self, adres):
        import webbrowser
        webbrowser.open(adres)
        return {"ok": True}

    # ------------------------------------------------------------------ historia przetworzeń

    def _zapisz_historie(self, zapisane=None, pominieto=None):
        if not self._silnik:
            return
        historia = _czytaj_json(PLIK_HISTORII, [])
        st = self._statystyki()
        wpis = next((w for w in historia if w.get("id") == self.id_historii), None)
        if wpis is None:
            self.id_historii = datetime.now().strftime("%Y%m%d%H%M%S%f")
            wpis = {"id": self.id_historii, "start": datetime.now().strftime("%Y-%m-%d %H:%M")}
            historia.insert(0, wpis)
        wpis.update({"kiedy": datetime.now().strftime("%Y-%m-%d %H:%M"), "plik": self.plik_rcp, "urlopy": self.plik_urlopow,
                     "okres": f"{st['od']} - {st['do']}", "zdarzen": st["zdarzen"], "skorygowane": st["skorygowane"],
                     "do_sprawdzenia": st["do_sprawdzenia"], "reczne": len(self.reczne), "wersja": VERSION})
        if zapisane:
            wpis.setdefault("zapisy", []).append({"kiedy": datetime.now().strftime("%Y-%m-%d %H:%M"), "pliki": zapisane, "pominieto": pominieto})
        _zapisz_json(PLIK_HISTORII, historia[:HISTORIA_MAX])

    def pliki_wynikowe(self, plik_bazowy):
        """Pliki zapisane z danego pliku RCP (także przez starsze wersje): <plik>_poprawione_N.txt, <plik>_RAPORT_BRAKOW_N.txt/.pdf
        w jego folderze i w folderze zapisu z ustawień. Od najnowszego."""
        rdzen = os.path.splitext(os.path.basename(plik_bazowy))[0]
        foldery = {os.path.dirname(plik_bazowy)} | ({self.program["folder_zapisu"]} if self.program["folder_zapisu"] else set())
        wynik = []
        for folder in foldery:
            for sciezka in glob.glob(os.path.join(glob.escape(folder), glob.escape(rdzen) + "_*")):
                m = re.fullmatch(re.escape(rdzen) + r"_(poprawione|RAPORT_BRAKOW)_(\d+)\.(txt|pdf)", os.path.basename(sciezka), re.IGNORECASE)
                if not m or not os.path.isfile(sciezka):
                    continue
                wynik.append({"sciezka": sciezka, "nazwa": os.path.basename(sciezka), "numer": int(m.group(2)),
                              "rodzaj": "erp" if m.group(1).lower() == "poprawione" else m.group(3).lower(),
                              "kiedy": datetime.fromtimestamp(os.path.getmtime(sciezka)).strftime("%Y-%m-%d %H:%M"),
                              "kb": max(1, round(os.path.getsize(sciezka) / 1024))})
        return sorted(wynik, key=lambda p: (-p["numer"], p["rodzaj"] != "erp", p["nazwa"]))

    def historia(self):
        return [{**w, "istnieje": os.path.isfile(w.get("plik", "")), "pliki": self.pliki_wynikowe(w.get("plik", ""))}
                for w in _czytaj_json(PLIK_HISTORII, [])]

    def otworz_plik(self, sciezka):
        if os.path.isfile(sciezka):
            os.startfile(sciezka)
            return {"ok": True}
        return {"ok": False, "blad": "Nie znaleziono pliku - został przeniesiony albo usunięty."}

    def otworz_z_historii(self, id_):
        wpis = next((w for w in _czytaj_json(PLIK_HISTORII, []) if w.get("id") == id_), None)
        if not wpis:
            return {"ok": False, "blad": "Nie znaleziono wpisu."}
        self._wyczysc_sesje()
        if wpis.get("urlopy") and os.path.isfile(wpis["urlopy"]):
            self.wczytaj_plik(wpis["urlopy"])
        return self.wczytaj_plik(wpis["plik"])

    # ------------------------------------------------------------------ zgłoszenie błędu

    def wybierz_zalaczniki(self):
        wynik = self._okno.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=True)
        return list(wynik or [])

    def pliki_do_zgloszenia(self):
        """Proponowane załączniki zgłoszenia: wczytany plik RCP, plan nieobecności i pliki zapisane z tego RCP
        (zaznaczone domyślnie: najnowszy plik poprawiony i najnowsze raporty)."""
        wynik = []
        if self.plik_rcp and os.path.isfile(self.plik_rcp):
            wynik.append({"sciezka": self.plik_rcp, "opis": "plik z Roger RCP (przed korektą)", "zaznacz": True})
        if self.plik_urlopow and os.path.isfile(self.plik_urlopow):
            wynik.append({"sciezka": self.plik_urlopow, "opis": "plan nieobecności", "zaznacz": True})
        if self.plik_rcp:
            pliki = self.pliki_wynikowe(self.plik_rcp)
            najnowszy = {}
            for p in pliki:
                najnowszy.setdefault(p["rodzaj"], p["numer"])
            for p in pliki:
                opis = f"plik poprawiony dla ERP, wersja {p['numer']}" if p["rodzaj"] == "erp" else f"raport {p['rodzaj'].upper()}, wersja {p['numer']}"
                wynik.append({"sciezka": p["sciezka"], "opis": f"{opis} · {p['kiedy']}", "zaznacz": p["numer"] == najnowszy[p["rodzaj"]]})
        for w in wynik:
            w["nazwa"] = os.path.basename(w["sciezka"])
            w["kb"] = max(1, round(os.path.getsize(w["sciezka"]) / 1024))
        return {"pliki": wynik, "limit_mb": ZALACZNIKI_MAX_MB}

    def zglos_blad(self, email, opis, zalaczone, dodatkowe):
        pliki = [p for p in list(dict.fromkeys(list(zalaczone) + list(dodatkowe))) if p and os.path.isfile(p)]
        rozmiar = sum(os.path.getsize(p) for p in pliki)
        if rozmiar > ZALACZNIKI_MAX_MB * 1024 * 1024:
            return {"ok": False, "blad": f"Załączniki mają razem {rozmiar / 1048576:.1f} MB - limit to {ZALACZNIKI_MAX_MB} MB."}
        zalaczniki = [{"nazwa": os.path.basename(p), "dane": base64.b64encode(open(p, "rb").read()).decode("ascii")} for p in pliki]
        zgloszenie = {"program": NAZWA_PROGRAMU, "wersja": VERSION, "email": email, "kategoria": "Błąd programu",
                      "nazwa": f"Zgłoszenie błędu Korektora v{VERSION}",
                      "opis": f"Data zgłoszenia: {datetime.now():%Y-%m-%d %H:%M:%S}\nKomputer: {platform.node()}\n\n{opis}", "zalaczniki": zalaczniki}
        req = urllib.request.Request(URL_ZGLOSZEN, data=json.dumps(zgloszenie).encode("utf-8"), headers={**NAGLOWKI, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as odp:
                wynik = json.loads(odp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                wynik = json.loads(e.read().decode("utf-8"))
            except Exception:
                return {"ok": False, "blad": str(e)}
        except Exception as e:
            return {"ok": False, "blad": f"Brak połączenia z serwerem: {e}"}
        return {"ok": bool(wynik.get("ok")), "blad": wynik.get("blad", "")}
