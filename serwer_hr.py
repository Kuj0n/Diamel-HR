import os
import json
import ctypes
import ctypes.wintypes
import platform
import urllib.request
import urllib.error
import tkinter as tk
from tkinter import messagebox

from konfiguracja_app import VERSION, NAZWA_PROGRAMU, URL_HR_API

# Lista pracowników, działy i zmiany nie są wbudowane w program - pobierane są z diamel.pl po zalogowaniu.
# Zapamiętany dostęp (token) jest szyfrowany przez Windows (DPAPI): odczyta go tylko ten sam użytkownik Windows.

NAGLOWKI = {'User-Agent': f'Diamel-{NAZWA_PROGRAMU}/{VERSION}', 'Content-Type': 'application/json'}
PLIK_TOKENU = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Diamel", "Korektor HR", "sesja.dat")


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

def _dpapi(dane, szyfruj):
    bufor = ctypes.create_string_buffer(dane, len(dane))
    wej = _DATA_BLOB(len(dane), ctypes.cast(bufor, ctypes.POINTER(ctypes.c_char)))
    wyj = _DATA_BLOB()
    funkcja = ctypes.windll.crypt32.CryptProtectData if szyfruj else ctypes.windll.crypt32.CryptUnprotectData
    if not funkcja(ctypes.byref(wej), None, None, None, None, 0, ctypes.byref(wyj)):
        raise OSError("Błąd szyfrowania DPAPI")
    try:
        return ctypes.string_at(wyj.pbData, wyj.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(wyj.pbData)

def wczytaj_token():
    try:
        with open(PLIK_TOKENU, "rb") as f:
            return _dpapi(f.read(), szyfruj=False).decode("ascii")
    except Exception:
        return None

def zapisz_token(token):
    try:
        os.makedirs(os.path.dirname(PLIK_TOKENU), exist_ok=True)
        with open(PLIK_TOKENU, "wb") as f:
            f.write(_dpapi(token.encode("ascii"), szyfruj=True))
    except Exception:
        pass  # bez zapamiętania - przy następnym uruchomieniu program poprosi o hasło

def usun_token():
    try: os.remove(PLIK_TOKENU)
    except OSError: pass

def zapytanie(dane, timeout=10.0):
    """Zapytanie do API HR. Odpowiedź serwera (także z kodem błędu) jako słownik; brak sieci -> wyjątek."""
    req = urllib.request.Request(URL_HR_API, data=json.dumps(dane).encode("utf-8"), headers=NAGLOWKI)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as http_err:
        try: return json.loads(http_err.read().decode("utf-8"))
        except Exception: raise http_err


def okno_logowania(root):
    """Okno logowania do bazy pracowników. Zwraca token albo None (Anuluj)."""
    wynik = {"token": None}
    okno = tk.Toplevel(root)
    okno.title("Logowanie - baza pracowników")
    okno.resizable(False, False)
    okno.geometry(f"+{root.winfo_screenwidth() // 2 - 170}+{root.winfo_screenheight() // 2 - 130}")
    okno.attributes("-topmost", True)
    okno.grab_set()

    tk.Label(okno, text="Zaloguj się, aby pobrać listę pracowników", font=("Arial", 10, "bold")).pack(padx=25, pady=(18, 10))
    tk.Label(okno, text="Login:").pack(anchor="w", padx=25)
    v_login = tk.StringVar()
    e_login = tk.Entry(okno, textvariable=v_login, width=36)
    e_login.pack(padx=25)
    tk.Label(okno, text="Hasło:").pack(anchor="w", padx=25, pady=(8, 0))
    v_haslo = tk.StringVar()
    e_haslo = tk.Entry(okno, textvariable=v_haslo, width=36, show="•")
    e_haslo.pack(padx=25)
    v_zapamietaj = tk.BooleanVar(value=True)
    tk.Checkbutton(okno, text="Zapamiętaj na tym komputerze (30 dni)", variable=v_zapamietaj).pack(anchor="w", padx=20, pady=8)
    lbl_blad = tk.Label(okno, text="", fg="#B71C1C", wraplength=300)
    lbl_blad.pack(padx=25)

    def zaloguj(*_):
        if not v_login.get().strip() or not v_haslo.get():
            lbl_blad.config(text="Podaj login i hasło.")
            return
        okno.config(cursor="watch"); okno.update()
        try:
            odp = zapytanie({"akcja": "zaloguj", "login": v_login.get().strip(), "haslo": v_haslo.get(),
                             "zapamietaj": v_zapamietaj.get(), "komputer": platform.node()})
        except Exception as e:
            odp = {"ok": False, "blad": f"Brak połączenia z serwerem.\n{e}"}
        okno.config(cursor="")
        if not odp.get("ok"):
            lbl_blad.config(text=odp.get("blad", "Logowanie nie powiodło się."))
            v_haslo.set("")
            return
        if v_zapamietaj.get():
            zapisz_token(odp["token"])
        wynik["token"] = odp["token"]
        okno.destroy()

    def nie_pamietam():
        if not v_login.get().strip():
            lbl_blad.config(text="Wpisz swój login, a potem kliknij \"Nie pamiętam hasła\".")
            e_login.focus_set()
            return
        okno.config(cursor="watch"); okno.update()
        try:
            odp = zapytanie({"akcja": "przypomnij", "login": v_login.get().strip(), "komputer": platform.node()})
        except Exception as e:
            odp = {"ok": False, "blad": f"Brak połączenia z serwerem.\n{e}"}
        okno.config(cursor="")
        if odp.get("ok"):
            messagebox.showinfo("Nie pamiętam hasła",
                                "Administrator dostał prośbę o reset hasła.\n\n"
                                "Wkrótce otrzymasz e-mail z linkiem do ustawienia nowego hasła.", parent=okno)
        else:
            lbl_blad.config(text=odp.get("blad", "Nie udało się wysłać prośby."))

    f_btn = tk.Frame(okno)
    f_btn.pack(pady=(8, 4))
    tk.Button(f_btn, text="Zaloguj", command=zaloguj, bg="#2196F3", fg="white", font=("Arial", 10, "bold"), width=12).pack(side="left", padx=5)
    tk.Button(f_btn, text="Anuluj", command=okno.destroy, width=10).pack(side="left", padx=5)
    tk.Button(okno, text="Nie pamiętam hasła", command=nie_pamietam, fg="#555555", relief="flat",
              font=("Arial", 9, "underline"), cursor="hand2").pack(pady=(0, 14))
    okno.bind("<Return>", zaloguj)
    e_login.focus_set()
    root.wait_window(okno)
    return wynik["token"]


def pobierz_dane_pracownikow(root):
    """
    Pobiera z serwera pracowników, działy, listy zmian i niepracujących.
    Zwraca słownik albo None (użytkownik zrezygnował - program działa bez listy pracowników).
    """
    token = wczytaj_token()
    while True:
        if not token:
            token = okno_logowania(root)
            if not token:
                return None
        try:
            odp = zapytanie({"akcja": "dane", "token": token})
        except Exception as e:
            if messagebox.askretrycancel("Brak połączenia",
                                         f"Nie udało się pobrać listy pracowników z serwera.\n\n{e}\n\n"
                                         "Ponowić?  (Anuluj = praca bez listy pracowników)"):
                continue
            return None
        if odp.get("ok"):
            return odp
        usun_token()
        token = None
        if not odp.get("zaloguj"):
            messagebox.showerror("Błąd serwera", odp.get("blad", "Nie udało się pobrać listy pracowników."))
            return None

def wyloguj():
    """Unieważnia zapamiętany dostęp na tym komputerze (także na serwerze)."""
    token = wczytaj_token()
    usun_token()
    if token:
        try: zapytanie({"akcja": "wyloguj", "token": token}, timeout=5.0)
        except Exception: pass
