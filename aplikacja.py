"""
aplikacja.py

Uruchomienie Korektora Logów HR: okno (Edge WebView2) z interfejsem z folderu ui/ i funkcjami z interfejs.py.
HR_DEBUG=1 - narzędzia programisty (F12) w oknie.
"""
import ctypes
import json
import os
import socket
import sys
import tempfile
import threading
import urllib.request

import webview
from webview.dom import DOMEventHandler

from interfejs import Api, KATALOG_DANYCH
from konfiguracja_app import VERSION, sciezka_do_zasobu

PLIK_OKNA = os.path.join(KATALOG_DANYCH, "okno.json")
# Własny port lokalnego serwera okna (pywebview domyślnie używa 42001 we wszystkich programach - przy otwartym
# Kalkulatorze Rozruchu Korektor dostawał jego interfejs). Porty programów Diamel: HR 42011, Kalkulator 42021, Akustyka 42031.
PORT_OKNA = 42011
CZEKAJ_NA_OKNO = 25  # sekund - potem awaryjne sprawdzenie aktualizacji bez interfejsu


def wolny_port(preferowany):
    """Port serwera okna: własny programu, a gdy zajęty (drugie okno, inny program) - dowolny wolny, nigdy cudzy serwer."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferowany))
            return preferowany
        except OSError:
            pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def awaryjna_aktualizacja(api):
    """
    Gdy okno programu nie wystartuje (np. błąd w wydanej wersji), aktualizację i tak da się zainstalować:
    zwykłe okienko Windows z propozycją nowszej albo zalecanej (wycofanie wadliwej) wersji.
    """
    if api.ui_gotowe.wait(CZEKAJ_NA_OKNO):
        return
    akt = api.sprawdz_aktualizacje()
    if not (akt.get("ok") and akt.get("do_instalacji")):
        return
    tekst = (f"Okno programu nie uruchomiło się poprawnie.\n\nAdministrator zaleca wersję {akt['wersja']} "
             + ("(powrót do starszej - w tej wersji wykryto błąd)." if akt["wycofana"] else "(nowsza).")
             + "\n\nPobrać i zainstalować ją teraz?")
    if ctypes.windll.user32.MessageBoxW(0, tekst, "Korektor Logów HR - aktualizacja", 0x04 | 0x30 | 0x40000) != 6:  # Tak/Nie, ostrzeżenie, na wierzchu
        return
    try:
        urllib.request.urlretrieve(akt["link"], os.path.join(tempfile.gettempdir(), "Aktualizacja_HR_Instalator.exe"))
        api.uruchom_instalator()
    except Exception as e:
        ctypes.windll.user32.MessageBoxW(0, f"Nie udało się pobrać aktualizacji:\n{e}\n\nInstalator jest też na diamel.pl/hr/aktualizacje-hr.php",
                                         "Korektor Logów HR", 0x10 | 0x40000)


def main():
    api = Api()
    try:
        okno_poz = json.load(open(PLIK_OKNA, encoding="utf-8"))
    except Exception:
        okno_poz = {}
    okno = webview.create_window(
        f"Korektor Logów HR v{VERSION}", sciezka_do_zasobu(os.path.join("ui", "index.html")), js_api=api,
        width=okno_poz.get("w", 1400), height=okno_poz.get("h", 900), min_size=(1100, 700),
        maximized=okno_poz.get("max", False), background_color="#0a1530", text_select=True,
    )
    api._okno = okno  # z podkreśleniem: pywebview nie udostępnia (i nie przegląda) tego pola dla JS

    def upuszczono(e):
        # Pełna ścieżka pliku jest dostępna tylko po stronie Pythona (pywebviewFullPath)
        pliki = [f.get("pywebviewFullPath") for f in e.get("dataTransfer", {}).get("files", []) if f.get("pywebviewFullPath")]
        stan = None
        for p in sorted(pliki, key=lambda p: not p.lower().endswith((".xls", ".xlsx"))):  # najpierw plan nieobecności
            stan = api.wczytaj_plik(p)
        if stan is not None:
            okno.evaluate_js(f"window.poUpuszczeniu({json.dumps(stan, ensure_ascii=False)})")

    def zaladowano():
        okno.dom.document.events.drop += DOMEventHandler(upuszczono, True, True)

    def zamykanie():
        api.zakoncz_sesje()
        try:
            os.makedirs(KATALOG_DANYCH, exist_ok=True)
            json.dump({"w": okno.width, "h": okno.height, "max": False}, open(PLIK_OKNA, "w", encoding="utf-8"))
        except Exception:
            pass

    threading.Thread(target=awaryjna_aktualizacja, args=(api,), daemon=True).start()
    okno.events.loaded += zaladowano
    okno.events.closing += zamykanie
    webview.start(debug=os.environ.get("HR_DEBUG") == "1", private_mode=False, http_port=wolny_port(PORT_OKNA),
                  storage_path=os.path.join(KATALOG_DANYCH, "webview"))


if __name__ == "__main__":
    sys.exit(main())
