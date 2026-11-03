"""
aplikacja.py

Uruchomienie Korektora Logów HR: okno (Edge WebView2) z interfejsem z folderu ui/ i funkcjami z interfejs.py.
HR_DEBUG=1 - narzędzia programisty (F12) w oknie.
"""
import json
import os
import sys

import webview
from webview.dom import DOMEventHandler

from interfejs import Api, KATALOG_DANYCH
from konfiguracja_app import VERSION, sciezka_do_zasobu

PLIK_OKNA = os.path.join(KATALOG_DANYCH, "okno.json")


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

    okno.events.loaded += zaladowano
    okno.events.closing += zamykanie
    webview.start(debug=os.environ.get("HR_DEBUG") == "1", private_mode=False,
                  storage_path=os.path.join(KATALOG_DANYCH, "webview"))


if __name__ == "__main__":
    sys.exit(main())
