import os
import json
import urllib.request
import threading
import subprocess
import tempfile
import base64
import urllib.error
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk

from konfiguracja_app import VERSION, NAZWA_PROGRAMU, GITHUB_REPO, URL_ZGLOSZEN

NAGLOWKI = {'User-Agent': f'Diamel-{NAZWA_PROGRAMU}/{VERSION}'}
ZALACZNIKI_MAX_MB = 5  # limit serwera zgłoszeń (diamel.pl/api/zgloszenie.php)

def wez_krotke(v): return tuple(map(int, (v.lstrip("vV").split(" ")[0]).split(".")))

def pobierz_wydanie():
    """Najnowsze wydanie z GitHub Releases. Zwraca (dane wydania, {nazwa załącznika: link})."""
    req = urllib.request.Request(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest", headers=NAGLOWKI)
    with urllib.request.urlopen(req, timeout=4.0) as response:
        dane = json.loads(response.read().decode('utf-8'))
    zalaczniki = {a["name"]: a["browser_download_url"] for a in dane.get("assets", [])}
    return dane, zalaczniki

def sprawdz_aktualizacje(root, tryb="recznie"):
    def task():
        try:
            dane, zalaczniki = pobierz_wydanie()
            wersja_serwera = dane.get("tag_name", "0.0.0").lstrip("vV")
            changelog = dane.get("body") or "Brak informacji o nowościach."
            link = next((url for nazwa, url in zalaczniki.items() if nazwa.lower().endswith(".exe")), "")

            if wez_krotke(wersja_serwera) > wez_krotke(VERSION) and link:
                root.after(0, lambda: pokaz_monit_aktualizacji(root, wersja_serwera, link, changelog))
            elif tryb == "recznie":
                msg = f"Posiadasz najnowszą dostępną wersję programu!\n\nTwoja wersja: {VERSION}\nWersja na serwerze: {wersja_serwera}"
                root.after(0, lambda: messagebox.showinfo("Aktualizacje", msg, parent=root))
        except Exception as e:
            if tryb == "recznie":
                blad_msg = f"Nie udało się połączyć z serwerem aktualizacji.\nSprawdź połączenie z internetem.\n\nSzczegóły: {e}"
                root.after(0, lambda: messagebox.showerror("Błąd połączenia", blad_msg, parent=root))

    threading.Thread(target=task, daemon=True).start()

def pokaz_monit_aktualizacji(root, nowa_wersja, link, changelog):
    odp = messagebox.askyesno(
        "Dostępna nowa wersja!",
        f"Hej! Dostępna jest nowa wersja programu: {nowa_wersja} (Twoja: {VERSION})\n\n"
        f"CO NOWEGO:\n{changelog}\n\n"
        f"Czy chcesz, abym pobrał i uruchomił instalator nowej wersji?",
        parent=root
    )
    if odp:
        pobierz_i_zainstaluj(root, link)

def sprawdz_aktualizacje_przed_startem(root):
    """
    Sprawdza aktualizację przed logowaniem do bazy pracowników - poprawkę da się zainstalować,
    nawet gdy logowanie nie działa. Brak internetu / GitHub niedostępny: program startuje normalnie.
    """
    try:
        dane, zalaczniki = pobierz_wydanie()
    except Exception:
        return
    wersja_serwera = dane.get("tag_name", "0.0.0").lstrip("vV")
    link = next((url for nazwa, url in zalaczniki.items() if nazwa.lower().endswith(".exe")), "")
    if not link or wez_krotke(wersja_serwera) <= wez_krotke(VERSION):
        return
    odp = messagebox.askyesno(
        "Dostępna nowa wersja!",
        f"Dostępna jest nowa wersja programu: {wersja_serwera} (Twoja: {VERSION})\n\n"
        f"CO NOWEGO:\n{dane.get('body') or 'Brak informacji o nowościach.'}\n\n"
        f"Czy chcesz, abym pobrał i uruchomił instalator nowej wersji?")
    if odp:
        # Instalator kończy program; gdy pobieranie się nie uda, okno się zamyka i program startuje dalej
        root.wait_window(pobierz_i_zainstaluj(root, link))

def pobierz_i_zainstaluj(root, link):
    okno_pob = tk.Toplevel(root)
    okno_pob.title("Aktualizacja HR")
    okno_pob.geometry("400x180")

    root.update_idletasks()
    if root.winfo_viewable():
        x = root.winfo_x() + (root.winfo_width() // 2) - 200
        y = root.winfo_y() + (root.winfo_height() // 2) - 90
        okno_pob.transient(root)
    else:
        # Przed startem okno główne jest ukryte - pobieranie na środku ekranu
        x = root.winfo_screenwidth() // 2 - 200
        y = root.winfo_screenheight() // 2 - 90
        okno_pob.attributes("-topmost", True)
    okno_pob.geometry(f"+{x}+{y}")
    okno_pob.grab_set()

    lbl = tk.Label(okno_pob, text="Trwa pobieranie aktualizacji...", font=("Arial", 10, "bold"))
    lbl.pack(pady=15)
    
    pasek = ttk.Progressbar(okno_pob, mode='indeterminate', length=300)
    pasek.pack(pady=5)
    pasek.start()

    def start_update():
        sciezka_temp = os.path.join(tempfile.gettempdir(), "Aktualizacja_HR_Instalator.exe")
        try:
            subprocess.run(['powershell', '-Command', f'Unblock-File -Path \'{sciezka_temp}\''], shell=True)
            subprocess.Popen([sciezka_temp, "/FORCECLOSEAPPLICATIONS", "/NOCANCEL"])
            os._exit(0)
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie udało się uruchomić: {e}", parent=okno_pob)

    btn_start = tk.Button(okno_pob, text="URUCHOM INSTALATOR", command=start_update, 
                          bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), height=2)

    def download_thread():
        try:
            sciezka_temp = os.path.join(tempfile.gettempdir(), "Aktualizacja_HR_Instalator.exe")
            urllib.request.urlretrieve(link, sciezka_temp)
            
            def pokaz_przycisk():
                pasek.stop()
                pasek.pack_forget()
                lbl.config(text="Aktualizacja pobrana pomyślnie!")
                btn_start.pack(pady=15, fill="x", padx=40)
            
            okno_pob.after(0, pokaz_przycisk)
        except Exception as e:
            okno_pob.after(0, lambda: messagebox.showerror("Błąd", f"Nie udało się pobrać: {e}", parent=okno_pob))
            okno_pob.after(0, okno_pob.destroy)

    threading.Thread(target=download_thread, daemon=True).start()
    return okno_pob

def wyslij_zgloszenie_email(email, opis, pliki_zgloszenia, pliki_dodatkowe, okno, btn_wyslij):
    btn_wyslij.config(state="disabled", text="Wysyłanie zgłoszenia. Proszę czekać...")
    
    def thread_send():
        try:
            wszystkie_pliki = [pliki_zgloszenia.get('zrodlo'), pliki_zgloszenia.get('poprawiony'), pliki_zgloszenia.get('raport')] + pliki_dodatkowe
            rozmiar = sum(os.path.getsize(p) for p in wszystkie_pliki if p and os.path.exists(p))
            if rozmiar > ZALACZNIKI_MAX_MB * 1024 * 1024:
                raise Exception(f"Załączniki mają razem {rozmiar / 1024 / 1024:.1f} MB - limit to {ZALACZNIKI_MAX_MB} MB. Usuń część plików dodatkowych.")
            zalaczniki = []
            for sciezka in wszystkie_pliki:
                if sciezka and os.path.exists(sciezka):
                    with open(sciezka, 'rb') as f:
                        zalaczniki.append({"nazwa": os.path.basename(sciezka), "dane": base64.b64encode(f.read()).decode('ascii')})

            zgloszenie = {
                "program": NAZWA_PROGRAMU, "wersja": VERSION, "email": email,
                "kategoria": "Błąd programu", "nazwa": f"Zgłoszenie błędu Korektora v{VERSION}",
                "opis": f"Data zgłoszenia: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n--- OPIS PROBLEMU I PRACOWNICY ---\n{opis}",
                "zalaczniki": zalaczniki,
            }
            req = urllib.request.Request(URL_ZGLOSZEN, data=json.dumps(zgloszenie).encode('utf-8'),
                                         headers={**NAGLOWKI, 'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(req, timeout=60.0) as response:
                    wynik = json.loads(response.read().decode('utf-8'))
            except urllib.error.HTTPError as http_err:
                # Serwer odrzucił zgłoszenie - powód jest w treści odpowiedzi
                try: wynik = json.loads(http_err.read().decode('utf-8'))
                except Exception: raise http_err
            if not wynik.get("ok"):
                raise Exception(wynik.get("blad", "Nieznany błąd serwera."))

            okno.after(0, lambda: messagebox.showinfo("Sukces", "Zgłoszenie zostało wysłane. Odpowiemy na podany adres e-mail.", parent=okno))
            okno.after(0, okno.destroy)
        except Exception as e:
            blad_msg = f"Nie udało się wysłać zgłoszenia.\nUpewnij się, że masz połączenie z internetem.\n\nSzczegóły: {str(e)}"
            okno.after(0, lambda: messagebox.showerror("Błąd wysyłania", blad_msg, parent=okno))
            okno.after(0, lambda: btn_wyslij.config(state="normal", text="WYŚLIJ ZGŁOSZENIE"))

    threading.Thread(target=thread_send, daemon=True).start()