import os
import json
import ctypes
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
from datetime import datetime, timedelta
import webbrowser
import re

try:
    import pandas as pd
except ImportError:
    pd = None

# Importy z naszych własnych modułów
from konfiguracja_app import *
from obliczenia import zaokraglij_czas, oblicz_roznice_minut, parse_czas_do_minut, formatuj_minuty_do_czasu
from narzedzia import sprawdz_aktualizacje, wyslij_zgloszenie_email
from kalendarz import czy_dzien_roboczy
from serwer_hr import pobierz_dane_pracownikow, wyloguj

CONFIG_FILE = f"settings_v{VERSION.replace('.', '')}.json"

def format_czas_gui(czas_str):
    """ Formatuje wewnętrzny czas na przyjazny dla HR: np. 25:30 -> 01:30 (+1d) """
    if not czas_str or czas_str == "---": return czas_str
    try:
        g, m = map(int, czas_str.split(':'))
        if g >= 24:
            return f"{g % 24:02d}:{m:02d} (+1d)"
        return f"{g:02d}:{m:02d}"
    except:
        return czas_str

def parse_czas_gui(czas_str_gui):
    """ Rozbija czas z GUI na czysty HH:MM oraz flagę następnego dnia """
    if "(+1d)" in czas_str_gui:
        return czas_str_gui.replace(" (+1d)", "").strip(), True
    return czas_str_gui.strip(), False

class AppHR:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Specjalny Korektor Logów Specjalnego HRa v{VERSION}")
        wysokosc_ekranu = self.root.winfo_screenheight()
        szerokosc_ekranu = self.root.winfo_screenwidth()
        wysokosc_okna = 850
        
        if wysokosc_okna > wysokosc_ekranu - 80:
            wysokosc_okna = wysokosc_ekranu - 80
        pozycja_y = 0
        pozycja_x = (szerokosc_ekranu - 620) // 2 
            
        self.root.geometry(f"1200x{wysokosc_okna}+{pozycja_x}+{pozycja_y}")
        self.plik_sciezka = ""
        self.dane_zaladowane = []
        
        self.dane_do_zapisu = {}
        self.kontekst_pracownikow = {}
        self.filtry_dzialow_vars = {}
        self.baza_urlopow = {} 

        # Pracownicy, działy i listy zmian z serwera (panel HR na diamel.pl) - nie są wbudowane w program
        self.root.withdraw()
        self.dane_serwera = pobierz_dane_pracownikow(self.root) or {}
        self.root.deiconify()
        self.baza_pracownikow = self.dane_serwera.get("pracownicy", {})
        self.baza_dzialow = self.dane_serwera.get("dzialy", {})
        if not self.dane_serwera:
            messagebox.showwarning("Brak listy pracowników",
                                   "Program działa bez listy pracowników (nazwiska, działy i zmiany nie będą dostępne).\n\n"
                                   "Aby ją pobrać, uruchom program ponownie i zaloguj się.")

        self.main_canvas = tk.Canvas(self.root, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.main_canvas.yview)
        self.scrollable_frame = tk.Frame(self.main_canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        )

        self.canvas_window = self.main_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.main_canvas.bind("<Configure>", self._on_canvas_configure)
        self.main_canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.main_canvas.pack(side="left", expand=True, fill="both")
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)

        self.chk_wej_var = tk.BooleanVar()
        self.wej_kierunek = tk.StringVar()
        self.chk_zmiana1_var = tk.BooleanVar()
        self.chk_zmiana2_var = tk.BooleanVar()
        self.chk_wyj_var = tk.BooleanVar()
        self.wyj_kierunek = tk.StringVar()
        self.chk_duplikaty_var = tk.BooleanVar()
        self.chk_pomylki_var = tk.BooleanVar()
        self.chk_midnight_var = tk.BooleanVar()
        self.chk_ostrzegaj_polnoc_var = tk.BooleanVar(value=True)
        self.chk_usun_18_var = tk.BooleanVar()
        self.chk_przepustka_var = tk.BooleanVar()
        self.chk_raport_var = tk.BooleanVar()
        self.chk_flex_var = tk.BooleanVar()
        self.chk_ochrona_var = tk.BooleanVar()
        
        self.chk_nadgodziny_var = tk.BooleanVar()
        self.combo_nadgodziny_val = tk.StringVar(value="15")
        self.chk_nadgodziny_skok_var = tk.BooleanVar()
        self.combo_nadgodziny_skok_val = tk.StringVar(value="30")
        
        self.chk_nadgodziny_wyjatek_var = tk.BooleanVar()
        self.dzialy_wyjatek_var = tk.StringVar()
        self.combo_nadgodziny_wyjatek_val = tk.StringVar(value="10")
        self.combo_nadgodziny_wyjatek_skok_val = tk.StringVar(value="0") 
        
        self.pracownicy_7h_var = tk.StringVar()
        self.pracownicy_6_14_var = tk.StringVar()
        self.pracownicy_13_21_var = tk.StringVar()
        self.pracownicy_8_16_var = tk.StringVar()
        self.pracownicy_16_24_var = tk.StringVar()
        self.pracownicy_ignorowani_var = tk.StringVar()

        self.setup_ui()
        self.load_settings()
        self.toggle_wej_widgets()
        self.toggle_wyj_widgets()
        self.toggle_duplikaty_widgets()
        self.toggle_pomylki_widgets()
        
        sprawdz_aktualizacje(self.root, tryb="w_tle")

    def wyloguj_z_bazy(self):
        if messagebox.askyesno("Wyloguj z bazy pracowników",
                               "Usunąć zapamiętane logowanie z tego komputera?\n\nPrzy następnym uruchomieniu program poprosi o login i hasło.",
                               parent=self.root):
            wyloguj()
            messagebox.showinfo("Wylogowano", "Zapamiętane logowanie zostało usunięte.", parent=self.root)

    def _on_canvas_configure(self, event):
        self.main_canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self.main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def pobierz_dzial_pracownika(self, nr_pracownika):
        nr_czysty = nr_pracownika.strip().replace('\ufeff', '')
        dzial = self.baza_dzialow.get(nr_czysty)
        if not dzial:
            dzial = self.baza_dzialow.get(nr_pracownika)
        if not dzial and nr_czysty.isdigit():
            dzial = self.baza_dzialow.get(str(int(nr_czysty)))
        return dzial.strip() if dzial else "Nieprzypisani"

    def pobierz_liste_id_pracownikow(self):
        ids = set()
        if self.baza_pracownikow:
            ids.update(self.baza_pracownikow.keys())
        if self.baza_dzialow:
            ids.update(self.baza_dzialow.keys())
        if self.dane_zaladowane:
            prac_z_pliku = {p.strip().split(';')[1] for p in self.dane_zaladowane if len(p.split(';')) >= 3}
            ids.update(prac_z_pliku)
        return sorted(list(ids))

    def pobierz_liste_dzialow(self):
        if not self.baza_dzialow:
            return []
        return sorted(list(set(self.baza_dzialow.values())))

    def laduj_urlopy(self):
        if pd is None:
            messagebox.showerror("Brak biblioteki", "Aby odczytywać pliki Excel, zainstaluj dodatkowe biblioteki do Pythona (przed kompilacją).\n\nOtwórz terminal (CMD) i wpisz:\npip install pandas xlrd openpyxl")
            return
            
        sciezka = filedialog.askopenfilename(filetypes=[("Pliki Excel", "*.xls *.xlsx")])
        if not sciezka: return
        
        try:
            self.lbl_status_urlopy.config(text="Wczytywanie pliku Excel, proszę czekać...", fg="orange")
            self.root.update_idletasks()
            
            df = pd.read_excel(sciezka, header=None)
            baza_urlopow = {}
            last_emp_id = None
            
            col_od = None
            col_do = None
            for col in df.columns:
                for val in df[col].head(30):
                    val_str = str(val).strip().upper()
                    if val_str == 'OD DNIA':
                        col_od = col
                    elif val_str == 'DO DNIA':
                        col_do = col
            
            if col_od is None or col_do is None:
                col_od, col_do = 6, 9 
            
            for idx, row in df.iterrows():
                col0 = str(row[0]) if pd.notna(row[0]) else ''
                match = re.search(r'\[(\d+)\]', col0)
                if match:
                    last_emp_id = match.group(1).zfill(4)
                
                v_od = row.get(col_od)
                v_do = row.get(col_do)
                
                if pd.notna(v_od) and pd.notna(v_do) and last_emp_id:
                    try:
                        od_dnia = pd.to_datetime(v_od)
                        do_dnia = pd.to_datetime(v_do)
                        if od_dnia.year >= 2000:
                            date_range = pd.date_range(od_dnia, do_dnia)
                            if last_emp_id not in baza_urlopow:
                                baza_urlopow[last_emp_id] = set()
                            for d in date_range:
                                baza_urlopow[last_emp_id].add(d.strftime("%Y.%m.%d"))
                    except:
                        pass
                        
            self.baza_urlopow = baza_urlopow
            suma_dni = sum(len(v) for v in baza_urlopow.values())
            self.lbl_status_urlopy.config(text=f"Plan urlopów: Wczytano ({len(baza_urlopow)} prac., {suma_dni} dni)", fg="green")
            messagebox.showinfo("Sukces", f"Pomyślnie wczytano plan urlopowy.\n\nRozpoznano nieobecności dla {len(baza_urlopow)} pracowników (łącznie {suma_dni} dni).")
            
        except Exception as e:
            self.lbl_status_urlopy.config(text="Błąd odczytu planu urlopowego", fg="red")
            messagebox.showerror("Błąd", f"Wystąpił błąd podczas odczytu pliku Excel:\n{str(e)}")

    def generuj_nazwy_plikow(self, sciezka):
        dir_name = os.path.dirname(sciezka)
        base_name = os.path.basename(sciezka)
        name, ext = os.path.splitext(base_name)
        rdzen = re.sub(r'_poprawione(?:_\d+)?$', '', name)
        idx = 1
        while True:
            p_wynik = os.path.join(dir_name, f"{rdzen}_poprawione_{idx}{ext}")
            p_raport = os.path.join(dir_name, f"{rdzen}_RAPORT_BRAKOW_{idx}.txt")
            if not os.path.exists(p_wynik) and not os.path.exists(p_raport):
                return p_wynik, p_raport
            idx += 1

    def znajdz_najnowsze_pliki(self, sciezka):
        dir_name = os.path.dirname(sciezka)
        base_name = os.path.basename(sciezka)
        name, ext = os.path.splitext(base_name)
        rdzen = re.sub(r'_poprawione(?:_\d+)?$', '', name)
        najnowszy_wynik = ""
        najnowszy_raport = ""
        idx = 1
        while True:
            p_wynik = os.path.join(dir_name, f"{rdzen}_poprawione_{idx}{ext}")
            p_raport = os.path.join(dir_name, f"{rdzen}_RAPORT_BRAKOW_{idx}.txt")
            if not os.path.exists(p_wynik) and not os.path.exists(p_raport): break
            if os.path.exists(p_wynik): najnowszy_wynik = p_wynik
            if os.path.exists(p_raport): najnowszy_raport = p_raport
            idx += 1
        
        if not najnowszy_wynik:
            p_wynik = os.path.join(dir_name, f"{rdzen}_poprawione{ext}")
            if os.path.exists(p_wynik): najnowszy_wynik = p_wynik
        if not najnowszy_raport:
            p_raport = os.path.join(dir_name, f"{rdzen}_RAPORT_BRAKOW.txt")
            if os.path.exists(p_raport): najnowszy_raport = p_raport
        return najnowszy_wynik, najnowszy_raport

    def pokaz_okno_zgloszenia(self):
        okno = tk.Toplevel(self.root)
        okno.title("Zgłoś błąd programu")
        okno.geometry("620x620")
        
        pliki_zgloszenia = {
            'zrodlo': self.plik_sciezka if self.plik_sciezka else "",
            'poprawiony': "",
            'raport': ""
        }
        pliki_dodatkowe = []
        
        if self.plik_sciezka:
            p_popr, p_rap = self.znajdz_najnowsze_pliki(self.plik_sciezka)
            if p_popr: pliki_zgloszenia['poprawiony'] = p_popr
            if p_rap: pliki_zgloszenia['raport'] = p_rap

        tk.Label(okno, text="Twój adres e-mail (do kontaktu):", font=("Arial", 9, "bold")).pack(pady=(15, 5), anchor="w", padx=20)
        entry_email = tk.Entry(okno, width=50, font=("Arial", 10))
        entry_email.pack(padx=20, anchor="w")

        tk.Label(okno, text="Lista numerów pracowników z problemem i opis błędu:", font=("Arial", 9, "bold")).pack(pady=(15, 5), anchor="w", padx=20)
        text_opis = scrolledtext.ScrolledText(okno, width=70, height=8, font=("Arial", 10))
        text_opis.pack(padx=20, anchor="w")

        f_pliki = tk.LabelFrame(okno, text=" Załączniki do zgłoszenia ", padx=10, pady=10, font=("Arial", 9, "bold"))
        f_pliki.pack(padx=20, pady=15, fill="x")

        def ucieknij_nazwe(sciezka): return os.path.basename(sciezka) if sciezka else "Brak pliku"

        lbl_zrodlo = tk.Label(f_pliki, text=f"Plik źródłowy:\n{ucieknij_nazwe(pliki_zgloszenia['zrodlo'])}", fg="blue", justify="left")
        lbl_popr = tk.Label(f_pliki, text=f"Plik poprawiony:\n{ucieknij_nazwe(pliki_zgloszenia['poprawiony'])}", fg="blue", justify="left")
        lbl_rap = tk.Label(f_pliki, text=f"Raport nieprawidłowości:\n{ucieknij_nazwe(pliki_zgloszenia['raport'])}", fg="blue", justify="left")
        lbl_dod = tk.Label(f_pliki, text="Dodatkowe pliki (np. zrzuty ekranu):\nBrak", fg="blue", justify="left")

        def zmien_plik(klucz, label_element, tytul):
            p = filedialog.askopenfilename()
            if p:
                pliki_zgloszenia[klucz] = p
                label_element.config(text=f"{tytul}:\n{os.path.basename(p)}")

        def dodaj_dodatkowe():
            sciezki = filedialog.askopenfilenames(title="Wybierz dodatkowe pliki (można zaznaczyć wiele)")
            if sciezki:
                for s in sciezki:
                    if s not in pliki_dodatkowe: pliki_dodatkowe.append(s)
                lbl_dod.config(text=f"Dodatkowe pliki (zrzuty ekranu):\nWybrano: {len(pliki_dodatkowe)} plik(ów)")

        def wyczysc_dodatkowe():
            pliki_dodatkowe.clear()
            lbl_dod.config(text="Dodatkowe pliki (zrzuty ekranu):\nBrak")

        lbl_zrodlo.grid(row=0, column=0, sticky="w", pady=5)
        tk.Button(f_pliki, text="Wybierz/Zmień", command=lambda: zmien_plik('zrodlo', lbl_zrodlo, "Plik źródłowy")).grid(row=0, column=1, padx=20, sticky="e")
        ttk.Separator(f_pliki, orient='horizontal').grid(row=1, column=0, columnspan=2, sticky='ew', pady=5)
        lbl_popr.grid(row=2, column=0, sticky="w", pady=5)
        tk.Button(f_pliki, text="Wybierz/Zmień", command=lambda: zmien_plik('poprawiony', lbl_popr, "Plik poprawiony")).grid(row=2, column=1, padx=20, sticky="e")
        ttk.Separator(f_pliki, orient='horizontal').grid(row=3, column=0, columnspan=2, sticky='ew', pady=5)
        lbl_rap.grid(row=4, column=0, sticky="w", pady=5)
        tk.Button(f_pliki, text="Wybierz/Zmień", command=lambda: zmien_plik('raport', lbl_rap, "Raport nieprawidłowości")).grid(row=4, column=1, padx=20, sticky="e")
        ttk.Separator(f_pliki, orient='horizontal').grid(row=5, column=0, columnspan=2, sticky='ew', pady=5)
        lbl_dod.grid(row=6, column=0, sticky="w", pady=5)
        
        f_dod_btn = tk.Frame(f_pliki)
        f_dod_btn.grid(row=6, column=1, padx=20, sticky="e")
        tk.Button(f_dod_btn, text="Dodaj pliki", command=dodaj_dodatkowe).pack(side="left", padx=2)
        tk.Button(f_dod_btn, text="Wyczyść", command=wyczysc_dodatkowe).pack(side="left", padx=2)

        def wywolaj_wysylke():
            email = entry_email.get().strip()
            opis = text_opis.get("1.0", tk.END).strip()

            if not email or "@" not in email:
                messagebox.showerror("Błąd", "Podaj poprawny adres e-mail!", parent=okno)
                return
            if not opis:
                messagebox.showerror("Błąd", "Opisz krótko problem i podaj numery pracowników!", parent=okno)
                return
            
            if not pliki_zgloszenia.get('zrodlo') or not os.path.exists(pliki_zgloszenia['zrodlo']):
                messagebox.showerror("Brak pliku", "Musisz załączyć 'Plik źródłowy', aby wysłać zgłoszenie błędu.", parent=okno)
                return
            if not pliki_zgloszenia.get('poprawiony') or not os.path.exists(pliki_zgloszenia['poprawiony']):
                messagebox.showerror("Brak pliku", "Musisz załączyć 'Plik poprawiony', aby wysłać zgłoszenie błędu.", parent=okno)
                return
            if not pliki_zgloszenia.get('raport') or not os.path.exists(pliki_zgloszenia['raport']):
                messagebox.showerror("Brak pliku", "Musisz załączyć 'Raport nieprawidłowości', aby wysłać zgłoszenie błędu.", parent=okno)
                return

            wyslij_zgloszenie_email(email, opis, pliki_zgloszenia, pliki_dodatkowe, okno, btn_wyslij)

        btn_wyslij = tk.Button(okno, text="WYŚLIJ ZGŁOSZENIE", command=wywolaj_wysylke, bg="#2196F3", fg="white", font=("Arial", 11, "bold"), height=2)
        btn_wyslij.pack(pady=20, fill="x", padx=20)

    def otworz_okno_wyboru(self, tytul, dostepne_elementy, zmienna_docelowa):
        pop = tk.Toplevel(self.root)
        pop.title(tytul)
        pop.geometry("380x500")
        pop.grab_set()

        aktualne_wartosci = [v.strip() for v in zmienna_docelowa.get().split(',') if v.strip()]
        
        stan_zaznaczenia = {}
        for el in dostepne_elementy:
            stan_zaznaczenia[el] = (el in aktualne_wartosci)

        f_szukaj = tk.Frame(pop)
        f_szukaj.pack(fill="x", padx=10, pady=10)
        tk.Label(f_szukaj, text="Szukaj:").pack(side="left")
        var_szukaj = tk.StringVar()
        ent_szukaj = tk.Entry(f_szukaj, textvariable=var_szukaj)
        ent_szukaj.pack(side="left", fill="x", expand=True, padx=5)

        f_lista = tk.Frame(pop)
        f_lista.pack(fill="both", expand=True, padx=10, pady=5)
        scroll = ttk.Scrollbar(f_lista)
        scroll.pack(side="right", fill="y")
        
        lista = tk.Listbox(f_lista, selectmode=tk.MULTIPLE, yscrollcommand=scroll.set, exportselection=False)
        lista.pack(side="left", fill="both", expand=True)
        scroll.config(command=lista.yview)

        widoczne_elementy = []

        def odswiez_liste(*args):
            for idx, el in enumerate(widoczne_elementy):
                stan_zaznaczenia[el] = lista.selection_includes(idx)

            lista.delete(0, tk.END)
            widoczne_elementy.clear()

            fraza = var_szukaj.get().lower()
            for el in sorted(dostepne_elementy):
                if fraza in str(el).lower():
                    lista.insert(tk.END, el)
                    widoczne_elementy.append(el)
                    if stan_zaznaczenia[el]:
                        lista.selection_set(tk.END)

        var_szukaj.trace_add("write", odswiez_liste)
        odswiez_liste()

        def zapisz():
            for idx, el in enumerate(widoczne_elementy):
                stan_zaznaczenia[el] = lista.selection_includes(idx)

            wybrane = [str(el) for el, zazn in stan_zaznaczenia.items() if zazn]
            zmienna_docelowa.set(", ".join(wybrane))
            pop.destroy()

        tk.Button(pop, text="Zapisz wybór", command=zapisz, bg="#4CAF50", fg="white", font=("Arial", 10, "bold")).pack(fill="x", padx=10, pady=10)

    def setup_ui(self):
        container = self.scrollable_frame

        frame_header = tk.Frame(container)
        frame_header.pack(side="top", fill="x", padx=15, pady=(10, 5))
        
        tk.Label(frame_header, text="©Mateusz Kujawa @diamel.pl", font=("Arial", 9, "bold"), fg="blue").pack(side="left")
        btn_info = tk.Button(frame_header, text="ℹ Historia", command=self.pokaz_changelog, font=("Arial", 9, "underline"), fg="#555555", relief="flat", cursor="hand2")
        btn_info.pack(side="left", padx=5)
        
        btn_update = tk.Button(frame_header, text="🔄 Sprawdź aktualizacje", command=lambda: sprawdz_aktualizacje(self.root, tryb="recznie"), font=("Arial", 9, "underline"), fg="#555555", relief="flat", cursor="hand2")
        btn_update.pack(side="left", padx=5)
        
        btn_web = tk.Button(frame_header, text="🌐 Strona WWW", command=lambda: webbrowser.open("https://diamel.pl/hr/aktualizacje-hr.php"), font=("Arial", 9, "underline"), fg="#555555", relief="flat", cursor="hand2")
        btn_web.pack(side="left", padx=5)

        btn_wyloguj = tk.Button(frame_header, text="🔑 Wyloguj z bazy", command=self.wyloguj_z_bazy, font=("Arial", 9, "underline"), fg="#555555", relief="flat", cursor="hand2")
        btn_wyloguj.pack(side="left", padx=5)

        tk.Label(frame_header, text=f"Wersja: {VERSION} | {BUILD_DATE}", font=("Arial", 9), fg="blue").pack(side="right")
        ttk.Separator(container, orient='horizontal').pack(fill='x', pady=(0, 10))

        cols_frame = tk.Frame(container)
        cols_frame.pack(fill="x", padx=10)
        col_left = tk.Frame(cols_frame)
        col_left.pack(side="left", fill="both", expand=True, padx=5)
        col_right = tk.Frame(cols_frame)
        col_right.pack(side="left", fill="both", expand=True, padx=5)

        top_frame = tk.Frame(container)
        top_frame.pack(pady=5, fill="x", padx=20)
        
        f_left_top = tk.Frame(top_frame)
        f_left_top.pack(side="left", expand=True, fill="x")
        
        self.btn_load = tk.Button(f_left_top, text="Załaduj plik tekstowy (RCP)", command=self.laduj_plik, bg="#e1e1e1", font=("Arial", 10, "bold"), height=2)
        self.btn_load.pack(side="left", expand=True, fill="x", padx=(0, 5))
        
        self.btn_load_urlopy = tk.Button(f_left_top, text="Załaduj plan nieobecności (Excel)", command=self.laduj_urlopy, bg="#e1e1e1", font=("Arial", 10, "bold"), height=2)
        self.btn_load_urlopy.pack(side="left", expand=True, fill="x", padx=(5, 10))

        self.btn_zglos = tk.Button(top_frame, text="⚠ Zgłoś błąd", command=self.pokaz_okno_zgloszenia, bg="#ff9999", font=("Arial", 9, "bold"), height=2, width=15)
        self.btn_zglos.pack(side="right")

        f_statusy = tk.Frame(container)
        f_statusy.pack(pady=(0, 10))
        self.lbl_status = tk.Label(f_statusy, text="Dane RCP: Brak pliku", fg="gray", font=("Arial", 9, "italic"))
        self.lbl_status.pack(side="top")
        self.lbl_status_urlopy = tk.Label(f_statusy, text="Plan urlopów: Brak", fg="gray", font=("Arial", 9, "italic"))
        self.lbl_status_urlopy.pack(side="top")

        # Detekcja Zmian
        self.frame_ai = tk.LabelFrame(col_left, text=" Detekcja Zmian i Ochrony wypracowania (8h / 7h) ", padx=10, pady=5, font=("Arial", 9, "bold"))
        self.frame_ai.pack(padx=20, pady=5, fill="x")
        tk.Label(self.frame_ai, text="Wykrywaj Zmianę 1 (Wejścia od-do):", font=("Arial", 8)).grid(row=0, column=0, sticky="w")
        self.combo_z1_od = ttk.Combobox(self.frame_ai, values=[f"04:{i:02d}" for i in range(0, 60, 15)]+[f"05:{i:02d}" for i in range(0, 60, 15)], width=5, state="readonly")
        self.combo_z1_od.grid(row=0, column=1)
        self.combo_z1_do = ttk.Combobox(self.frame_ai, values=[f"06:{i:02d}" for i in range(0, 60, 15)], width=5, state="readonly")
        self.combo_z1_do.grid(row=0, column=2)

        tk.Label(self.frame_ai, text="Wykrywaj Zmianę 2 (Wejścia od-do):", font=("Arial", 8)).grid(row=1, column=0, sticky="w")
        self.combo_z2_od = ttk.Combobox(self.frame_ai, values=[f"12:{i:02d}" for i in range(0, 60, 15)]+[f"13:{i:02d}" for i in range(0, 60, 15)], width=5, state="readonly")
        self.combo_z2_od.grid(row=1, column=1)
        self.combo_z2_do = ttk.Combobox(self.frame_ai, values=[f"14:{i:02d}" for i in range(0, 60, 15)], width=5, state="readonly")
        self.combo_z2_do.grid(row=1, column=2)
        
        tk.Label(self.frame_ai, text="*Wejścia poza tymi oknami to automatycznie GODZINY RUCHOME.", fg="gray", font=("Arial", 8, "italic")).grid(row=2, column=0, columnspan=3, sticky="w", pady=2)
        ttk.Separator(self.frame_ai, orient='horizontal').grid(row=3, column=0, columnspan=3, sticky='ew', pady=5)
        
        tk.Checkbutton(self.frame_ai, text="Dla godzin ruchomych: Zaokrąglaj sumę pracy i przesuwaj wej/wyj", variable=self.chk_flex_var, font=("Arial", 8)).grid(row=4, column=0, columnspan=3, sticky="w")
        tk.Checkbutton(self.frame_ai, text="Dla stałych: Ochrona wypracowanego etatu", variable=self.chk_ochrona_var, font=("Arial", 8)).grid(row=5, column=0, columnspan=3, sticky="w")
        
        f_7h = tk.Frame(self.frame_ai)
        f_7h.grid(row=6, column=0, columnspan=3, sticky="w", pady=2)
        tk.Label(f_7h, text="Numery pracowników (7h pracy):", font=("Arial", 8)).pack(side="left")
        tk.Entry(f_7h, textvariable=self.pracownicy_7h_var, width=32).pack(side="left", padx=5)
        tk.Button(f_7h, text="Wybierz", command=lambda: self.otworz_okno_wyboru("Pracownicy 7h", self.pobierz_liste_id_pracownikow(), self.pracownicy_7h_var), bg="#e1e1e1").pack(side="left")
        
        f_ign = tk.Frame(self.frame_ai)
        f_ign.grid(row=7, column=0, columnspan=3, sticky="w", pady=2)
        tk.Label(f_ign, text="Ignorowani prac. (brak błędów):", font=("Arial", 8)).pack(side="left")
        tk.Entry(f_ign, textvariable=self.pracownicy_ignorowani_var, width=32).pack(side="left", padx=5)
        tk.Button(f_ign, text="Wybierz", command=lambda: self.otworz_okno_wyboru("Ignorowani pracownicy", self.pobierz_liste_id_pracownikow(), self.pracownicy_ignorowani_var), bg="#e1e1e1").pack(side="left")
        
        tk.Checkbutton(self.frame_ai, text="Zawsze otwieraj Menedżer Danych przed zapisem", variable=self.chk_raport_var, font=("Arial", 8)).grid(row=8, column=0, columnspan=3, sticky="w")

        # Sztywne Zmiany
        self.frame_sztywne = tk.LabelFrame(col_left, text=" Sztywne zmiany dla wybranych pracowników ", padx=10, pady=5, font=("Arial", 9, "bold"))
        self.frame_sztywne.pack(padx=20, pady=5, fill="x")
        
        tk.Label(self.frame_sztywne, text="Sztywna 06:00 - 14:00:", font=("Arial", 8)).grid(row=0, column=0, sticky="w", pady=2)
        tk.Entry(self.frame_sztywne, textvariable=self.pracownicy_6_14_var, width=35).grid(row=0, column=1, sticky="w", padx=5)
        tk.Button(self.frame_sztywne, text="Wybierz", command=lambda: self.otworz_okno_wyboru("Sztywna 06:00 - 14:00", self.pobierz_liste_id_pracownikow(), self.pracownicy_6_14_var), bg="#e1e1e1").grid(row=0, column=2, sticky="w")
        
        tk.Label(self.frame_sztywne, text="Sztywna 13:00 - 21:00:", font=("Arial", 8)).grid(row=1, column=0, sticky="w", pady=2)
        tk.Entry(self.frame_sztywne, textvariable=self.pracownicy_13_21_var, width=35).grid(row=1, column=1, sticky="w", padx=5)
        tk.Button(self.frame_sztywne, text="Wybierz", command=lambda: self.otworz_okno_wyboru("Sztywna 13:00 - 21:00", self.pobierz_liste_id_pracownikow(), self.pracownicy_13_21_var), bg="#e1e1e1").grid(row=1, column=2, sticky="w")
        
        tk.Label(self.frame_sztywne, text="Sztywna 08:00 - 16:00:", font=("Arial", 8)).grid(row=2, column=0, sticky="w", pady=2)
        tk.Entry(self.frame_sztywne, textvariable=self.pracownicy_8_16_var, width=35).grid(row=2, column=1, sticky="w", padx=5)
        tk.Button(self.frame_sztywne, text="Wybierz", command=lambda: self.otworz_okno_wyboru("Sztywna 08:00 - 16:00", self.pobierz_liste_id_pracownikow(), self.pracownicy_8_16_var), bg="#e1e1e1").grid(row=2, column=2, sticky="w")
        
        tk.Label(self.frame_sztywne, text="Sztywna 16:00 - 00:00:", font=("Arial", 8)).grid(row=3, column=0, sticky="w", pady=2)
        tk.Entry(self.frame_sztywne, textvariable=self.pracownicy_16_24_var, width=35).grid(row=3, column=1, sticky="w", padx=5)
        tk.Button(self.frame_sztywne, text="Wybierz", command=lambda: self.otworz_okno_wyboru("Sztywna 16:00 - 00:00", self.pobierz_liste_id_pracownikow(), self.pracownicy_16_24_var), bg="#e1e1e1").grid(row=3, column=2, sticky="w")

        # Wejścia
        self.frame_wejscie = tk.LabelFrame(col_left, text=" Korekta godzin WEJŚCIA (Kod 00) ", padx=10, pady=5, font=("Arial", 9, "bold"))
        self.frame_wejscie.pack(padx=20, pady=5, fill="x")
        tk.Checkbutton(self.frame_wejscie, text="Aktywuj zaokrąglanie wejść", variable=self.chk_wej_var, command=self.toggle_wej_widgets).grid(row=0, column=0, columnspan=2, sticky="w")
        self.rb_wej_up = tk.Radiobutton(self.frame_wejscie, text="W górę", variable=self.wej_kierunek, value="góra")
        self.rb_wej_down = tk.Radiobutton(self.frame_wejscie, text="W dół", variable=self.wej_kierunek, value="dół")
        self.rb_wej_up.grid(row=1, column=0, sticky="w")
        self.rb_wej_down.grid(row=1, column=1, sticky="w")
        self.lbl_wej_min = tk.Label(self.frame_wejscie, text="Zaokrąglaj do (min):")
        self.lbl_wej_min.grid(row=2, column=0, sticky="w")
        self.combo_wej = ttk.Combobox(self.frame_wejscie, values=[5, 10, 15, 30], width=5, state="readonly")
        self.combo_wej.grid(row=2, column=1, sticky="w", pady=2)
        self.lbl_wej_tol = tk.Label(self.frame_wejscie, text="Tolerancja błędu (min):")
        self.lbl_wej_tol.grid(row=3, column=0, sticky="w")
        self.combo_wej_tol = ttk.Combobox(self.frame_wejscie, values=[0, 1, 2, 3, 4, 5], width=5, state="readonly")
        self.combo_wej_tol.grid(row=3, column=1, sticky="w", pady=2)
        ttk.Separator(self.frame_wejscie, orient='horizontal').grid(row=4, column=0, columnspan=2, sticky='ew', pady=5)
        
        frame_z1 = tk.Frame(self.frame_wejscie)
        frame_z1.grid(row=5, column=0, columnspan=2, sticky="w")
        tk.Checkbutton(frame_z1, text="Dla stałych: Podbij wejście do 06:00 od min:", variable=self.chk_zmiana1_var, command=self.toggle_wej_widgets).pack(side="left")
        self.combo_zmiana1 = ttk.Combobox(frame_z1, values=[f"05:{i:02d}" for i in range(60)], width=6, state="readonly")
        self.combo_zmiana1.pack(side="left", padx=5)

        frame_z2 = tk.Frame(self.frame_wejscie)
        frame_z2.grid(row=6, column=0, columnspan=2, sticky="w")
        tk.Checkbutton(frame_z2, text="Dla stałych: Podbij wejście do 14:00 od min:", variable=self.chk_zmiana2_var, command=self.toggle_wej_widgets).pack(side="left")
        self.combo_zmiana2 = ttk.Combobox(frame_z2, values=[f"13:{i:02d}" for i in range(60)], width=6, state="readonly")
        self.combo_zmiana2.pack(side="left", padx=5)

        # Duplikaty i Pomyłki
        self.frame_duplikaty = tk.LabelFrame(col_right, text=" Filtrowanie duplikatów i pomyłek ", padx=10, pady=5, font=("Arial", 9, "bold"))
        self.frame_duplikaty.pack(padx=20, pady=5, fill="x")
        tk.Checkbutton(self.frame_duplikaty, text="Usuwaj podwójne odbicia (ignoruj jeśli odstęp < X min)", variable=self.chk_duplikaty_var, command=self.toggle_duplikaty_widgets).grid(row=0, column=0, columnspan=2, sticky="w")
        self.combo_dup_wej = ttk.Combobox(self.frame_duplikaty, values=[str(i) for i in range(1, 31)], width=4, state="readonly")
        self.combo_dup_wej.grid(row=1, column=0, sticky="w", pady=2)
        self.lbl_dup_wej = tk.Label(self.frame_duplikaty, text="minut na wejściu (Kod 00)")
        self.lbl_dup_wej.grid(row=1, column=1, sticky="w")
        self.combo_dup_wyj = ttk.Combobox(self.frame_duplikaty, values=[str(i) for i in range(1, 31)], width=4, state="readonly")
        self.combo_dup_wyj.grid(row=2, column=0, sticky="w")
        self.lbl_dup_wyj = tk.Label(self.frame_duplikaty, text="minut na wyjściu (Kod 16)")
        self.lbl_dup_wyj.grid(row=2, column=1, sticky="w")

        ttk.Separator(self.frame_duplikaty, orient='horizontal').grid(row=3, column=0, columnspan=2, sticky='ew', pady=5)
        
        f_pom = tk.Frame(self.frame_duplikaty)
        f_pom.grid(row=4, column=0, columnspan=2, sticky="w")
        tk.Checkbutton(f_pom, text="Koryguj odwrotne odbicia (pomyłka klawisza) do:", variable=self.chk_pomylki_var, command=self.toggle_pomylki_widgets).pack(side="left")
        self.combo_pomylki_val = ttk.Combobox(f_pom, values=[str(i) for i in range(1, 16)], width=3, state="readonly")
        self.combo_pomylki_val.pack(side="left", padx=2)
        self.lbl_pom_min = tk.Label(f_pom, text="min")
        self.lbl_pom_min.pack(side="left")

        # Wyjścia
        self.frame_wyjscie = tk.LabelFrame(col_right, text=" Korekta godzin WYJŚCIA (Kod 16) ", padx=10, pady=5, font=("Arial", 9, "bold"))
        self.frame_wyjscie.pack(padx=20, pady=5, fill="x")
        tk.Checkbutton(self.frame_wyjscie, text="Aktywuj zaokrąglanie wyjść", variable=self.chk_wyj_var, command=self.toggle_wyj_widgets).grid(row=0, column=0, columnspan=2, sticky="w")
        self.rb_wyj_up = tk.Radiobutton(self.frame_wyjscie, text="W górę", variable=self.wyj_kierunek, value="góra")
        self.rb_wyj_down = tk.Radiobutton(self.frame_wyjscie, text="W dół", variable=self.wyj_kierunek, value="dół")
        self.rb_wyj_up.grid(row=1, column=0, sticky="w")
        self.rb_wyj_down.grid(row=1, column=1, sticky="w")
        self.lbl_wyj_min = tk.Label(self.frame_wyjscie, text="Zaokrąglaj do (min):")
        self.lbl_wyj_min.grid(row=2, column=0, sticky="w")
        self.combo_wyj = ttk.Combobox(self.frame_wyjscie, values=[5, 10, 15, 30], width=5, state="readonly")
        self.combo_wyj.grid(row=2, column=1, sticky="w", pady=2)
        self.lbl_wyj_tol = tk.Label(self.frame_wyjscie, text="Tolerancja błędu (min):")
        self.lbl_wyj_tol.grid(row=3, column=0, sticky="w")
        self.combo_wyj_tol = ttk.Combobox(self.frame_wyjscie, values=[0, 1, 2, 3, 4, 5], width=5, state="readonly")
        self.combo_wyj_tol.grid(row=3, column=1, sticky="w", pady=2)

        # Nadgodziny
        self.frame_nad = tk.LabelFrame(col_right, text=" Ograniczenie i naliczanie nadgodzin ", padx=10, pady=5, font=("Arial", 9, "bold"))
        self.frame_nad.pack(padx=20, pady=5, fill="x")
        
        f_nad1 = tk.Frame(self.frame_nad)
        f_nad1.pack(anchor="w", pady=2)
        tk.Checkbutton(f_nad1, text="Ogranicz rozpoczęcie naliczania nadgodzin", variable=self.chk_nadgodziny_var).pack(side="left")
        tk.Label(f_nad1, text="Ignoruj mniejsze niż (min):").pack(side="left", padx=(10, 2))
        self.combo_nadgodziny_val = ttk.Combobox(f_nad1, values=[0, 5, 10, 15, 30, 45, 60], width=4, state="readonly")
        self.combo_nadgodziny_val.pack(side="left")
        
        f_nad2 = tk.Frame(self.frame_nad)
        f_nad2.pack(anchor="w", pady=2)
        tk.Checkbutton(f_nad2, text="Zaliczaj nadgodziny skokowo (co X minut)", variable=self.chk_nadgodziny_skok_var).pack(side="left")
        tk.Label(f_nad2, text="Krok naliczania (min):").pack(side="left", padx=(10, 2))
        self.combo_nadgodziny_skok_val = ttk.Combobox(f_nad2, values=[15, 30, 45, 60], width=4, state="readonly")
        self.combo_nadgodziny_skok_val.pack(side="left")

        f_nad3 = tk.Frame(self.frame_nad)
        f_nad3.pack(anchor="w", pady=(5, 2))
        tk.Checkbutton(f_nad3, text="Wyjątek dla działów:", variable=self.chk_nadgodziny_wyjatek_var).pack(side="left")
        tk.Entry(f_nad3, textvariable=self.dzialy_wyjatek_var, width=15).pack(side="left", padx=5)
        tk.Button(f_nad3, text="Wybierz", command=lambda: self.otworz_okno_wyboru("Wybierz działy wyjątków", self.pobierz_liste_dzialow(), self.dzialy_wyjatek_var), bg="#e1e1e1").pack(side="left")
        tk.Label(f_nad3, text="Ignoruj (min):").pack(side="left", padx=(5, 2))
        self.combo_nadgodziny_wyjatek_val = ttk.Combobox(f_nad3, values=[0, 5, 10, 15, 30, 45, 60], width=4, state="readonly")
        self.combo_nadgodziny_wyjatek_val.pack(side="left")
        tk.Label(f_nad3, text="Skok (min):").pack(side="left", padx=(5, 2))
        self.combo_nadgodziny_wyjatek_skok_val = ttk.Combobox(f_nad3, values=[0, 1, 5, 10, 15, 30, 45, 60], width=4, state="readonly")
        self.combo_nadgodziny_wyjatek_skok_val.pack(side="left")

        # Inne opcje
        self.frame_opcje = tk.LabelFrame(col_right, text=" Przestoje i przerwy ", padx=10, pady=5, font=("Arial", 9, "bold"))
        self.frame_opcje.pack(padx=20, pady=5, fill="x")
        
        f_noc = tk.Frame(self.frame_opcje)
        f_noc.pack(anchor="w", pady=2)
        tk.Checkbutton(f_noc, text="Korekta nocnej zmiany (przesuń do wczoraj) dla wyjść do:", variable=self.chk_midnight_var).pack(side="left")
        self.combo_midnight_val = ttk.Combobox(f_noc, values=[f"0{i}:00" for i in range(1, 10)], width=5, state="readonly")
        self.combo_midnight_val.pack(side="left", padx=5)
        
        tk.Checkbutton(self.frame_opcje, text="Usuń przerwę (Kod 18) i powiązane z nią wejście", variable=self.chk_usun_18_var).pack(anchor="w")
        tk.Checkbutton(self.frame_opcje, text="Zamień ostatnią w dniu przepustkę (Kod 25) na wyjście (Kod 16)", variable=self.chk_przepustka_var).pack(anchor="w")
        tk.Checkbutton(self.frame_opcje, text="Ostrzegaj o zakończeniu doby pracowniczej o północy (00:00)", variable=self.chk_ostrzegaj_polnoc_var).pack(anchor="w")

        self.btn_fix = tk.Button(container, text="PRZETWÓRZ DANE (PODGLĄD I KOREKTA)", command=self.procesuj, bg="#4CAF50", fg="black", font=("Arial", 11, "bold"), height=2)
        self.btn_fix.pack(pady=10, fill="x", padx=20)

    def pokaz_changelog(self):
        okno = tk.Toplevel(self.root)
        okno.title("Historia zmian")
        okno.geometry("800x400")
        lbl = tk.Label(okno, text="Historia aktualizacji programu", font=("Arial", 11, "bold"), pady=10)
        lbl.pack()
        pole_tekstu = scrolledtext.ScrolledText(okno, wrap=tk.WORD, font=("Consolas", 9))
        pole_tekstu.pack(expand=True, fill="both", padx=15, pady=5)
        pole_tekstu.insert(tk.END, CHANGELOG.strip())
        pole_tekstu.config(state=tk.DISABLED)
        btn = tk.Button(okno, text="Zamknij", command=okno.destroy, width=15)
        btn.pack(pady=10)

    def toggle_wej_widgets(self):
        state = "readonly" if self.chk_wej_var.get() else "disabled"
        self.rb_wej_up.config(state="normal" if self.chk_wej_var.get() else "disabled")
        self.rb_wej_down.config(state="normal" if self.chk_wej_var.get() else "disabled")
        self.combo_wej.config(state=state)
        self.combo_wej_tol.config(state=state)
        self.lbl_wej_min.config(fg="black" if self.chk_wej_var.get() else "gray")
        self.lbl_wej_tol.config(fg="black" if self.chk_wej_var.get() else "gray")
        self.combo_zmiana1.config(state="readonly" if self.chk_zmiana1_var.get() else "disabled")
        self.combo_zmiana2.config(state="readonly" if self.chk_zmiana2_var.get() else "disabled")

    def toggle_wyj_widgets(self):
        state = "readonly" if self.chk_wyj_var.get() else "disabled"
        self.rb_wyj_up.config(state="normal" if self.chk_wyj_var.get() else "disabled")
        self.rb_wyj_down.config(state="normal" if self.chk_wyj_var.get() else "disabled")
        self.combo_wyj.config(state=state)
        self.combo_wyj_tol.config(state=state)
        self.lbl_wyj_min.config(fg="black" if self.chk_wyj_var.get() else "gray")
        self.lbl_wyj_tol.config(fg="black" if self.chk_wyj_var.get() else "gray")

    def toggle_duplikaty_widgets(self):
        state = "readonly" if self.chk_duplikaty_var.get() else "disabled"
        self.combo_dup_wej.config(state=state)
        self.combo_dup_wyj.config(state=state)
        self.lbl_dup_wej.config(fg="black" if self.chk_duplikaty_var.get() else "gray")
        self.lbl_dup_wyj.config(fg="black" if self.chk_duplikaty_var.get() else "gray")

    def toggle_pomylki_widgets(self):
        state = "readonly" if self.chk_pomylki_var.get() else "disabled"
        self.combo_pomylki_val.config(state=state)
        self.lbl_pom_min.config(fg="black" if self.chk_pomylki_var.get() else "gray")

    def load_settings(self):
        s = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f: s = json.load(f)
            except: pass
            
        self.combo_z1_od.set(s.get("z1_od", "05:00"))
        self.combo_z1_do.set(s.get("z1_do", "06:30"))
        self.combo_z2_od.set(s.get("z2_od", "13:00"))
        self.combo_z2_do.set(s.get("z2_do", "14:30"))
        self.chk_flex_var.set(s.get("chk_flex", True))
        self.chk_ochrona_var.set(s.get("chk_ochrona", True))
        self.chk_raport_var.set(s.get("chk_raport", True))
        self.chk_wej_var.set(s.get("chk_wej", True))
        self.wej_kierunek.set(s.get("wej_kierunek", "dół"))
        self.combo_wej.set(s.get("wej_minuty", "5"))
        self.combo_wej_tol.set(s.get("wej_tol", "2"))
        self.chk_zmiana1_var.set(s.get("chk_zmiana1", True))
        self.combo_zmiana1.set(s.get("zmiana1_czas", "05:00"))
        self.chk_zmiana2_var.set(s.get("chk_zmiana2", True))
        self.combo_zmiana2.set(s.get("zmiana2_czas", "13:00"))
        self.chk_wyj_var.set(s.get("chk_wyj", True))
        self.wyj_kierunek.set(s.get("wyj_kierunek", "dół"))
        self.combo_wyj.set(s.get("wyj_minuty", "5"))
        self.combo_wyj_tol.set(s.get("wyj_tol", "2"))
        
        self.chk_duplikaty_var.set(s.get("chk_duplikaty", True))
        self.combo_dup_wej.set(s.get("dup_wej_min", "10"))
        self.combo_dup_wyj.set(s.get("dup_wyj_min", "10"))
        
        self.chk_pomylki_var.set(s.get("chk_pomylki", True))
        self.combo_pomylki_val.set(s.get("pomylki_min", "10"))
        
        self.chk_midnight_var.set(s.get("chk_midnight", True))
        self.chk_ostrzegaj_polnoc_var.set(s.get("chk_ostrzegaj_polnoc", True))
        self.combo_midnight_val.set(s.get("midnight_limit", "05:00"))
        self.chk_usun_18_var.set(s.get("chk_usun_18", True))
        self.chk_przepustka_var.set(s.get("chk_przepustka", True))
        self.chk_nadgodziny_var.set(s.get("chk_nadgodziny", True))
        self.combo_nadgodziny_val.set(s.get("nadgodziny_min", "30"))
        self.chk_nadgodziny_skok_var.set(s.get("chk_nadgodziny_skok", True))
        self.combo_nadgodziny_skok_val.set(s.get("nadgodziny_skok_min", "30"))
        
        self.chk_nadgodziny_wyjatek_var.set(s.get("chk_nadgodziny_wyjatek", True))
        
        domyslne_dzialy = "Dział Administracji, Dział Kadr i Płac, Dział Konstrukcyjny, Dział Kontroli Jakości, Dział Księgowości, Dział Serwisu, Dział Zaopatrzenia"
        self.dzialy_wyjatek_var.set(s.get("dzialy_wyjatek", domyslne_dzialy))
        
        self.combo_nadgodziny_wyjatek_val.set(s.get("nadgodziny_wyjatek_min", "10"))
        self.combo_nadgodziny_wyjatek_skok_val.set(s.get("nadgodziny_wyjatek_skok_min", "0"))
        
        domyslne_ignorowani = "0019, 0018, 0022, 0033, 0076, 0044, 0005, 0069, 0029, 0093, 0021"
        wczytani_ignorowani = s.get("pracownicy_ignorowani", domyslne_ignorowani)
        
        # Niepracujący (status w panelu HR) trafiają automatycznie do ignorowanych
        auto_ignorowani = self.dane_serwera.get("ignorowani", "")

        if auto_ignorowani:
            aktualna_lista = [x.strip() for x in wczytani_ignorowani.split(',') if x.strip()]
            nowi_ignorowani = [x.strip() for x in auto_ignorowani.split(',') if x.strip() and x.strip() not in aktualna_lista]
            if nowi_ignorowani:
                if aktualna_lista:
                    wczytani_ignorowani += ", "
                wczytani_ignorowani += ", ".join(nowi_ignorowani)
                
        self.pracownicy_ignorowani_var.set(wczytani_ignorowani)
        # --------------------------------------------------------------
                
        self.pracownicy_ignorowani_var.set(wczytani_ignorowani)

        def_7h, def_6_14, def_13_21, def_8_16, def_16_24 = "0232,0212", "0100,0205", "0100,0205", "0235", ""

        # Listy zmian z serwera (panel HR) mają pierwszeństwo przed zapisanymi ustawieniami
        dane_zewn = self.dane_serwera.get("listy")

        if dane_zewn:
            self.pracownicy_7h_var.set(dane_zewn.get("pracownicy_7h", def_7h))
            self.pracownicy_6_14_var.set(dane_zewn.get("pracownicy_6_14", def_6_14))
            self.pracownicy_13_21_var.set(dane_zewn.get("pracownicy_13_21", def_13_21))
            self.pracownicy_8_16_var.set(dane_zewn.get("pracownicy_8_16", def_8_16))
            self.pracownicy_16_24_var.set(dane_zewn.get("pracownicy_16_24", def_16_24))
        else:
            self.pracownicy_7h_var.set(s.get("pracownicy_7h", def_7h))
            self.pracownicy_6_14_var.set(s.get("pracownicy_6_14", def_6_14))
            self.pracownicy_13_21_var.set(s.get("pracownicy_13_21", def_13_21))
            self.pracownicy_8_16_var.set(s.get("pracownicy_8_16", def_8_16))
            self.pracownicy_16_24_var.set(s.get("pracownicy_16_24", def_16_24))

        self.toggle_pomylki_widgets()

    def save_settings(self):
        s = {
            "z1_od": self.combo_z1_od.get(), "z1_do": self.combo_z1_do.get(), "z2_od": self.combo_z2_od.get(), "z2_do": self.combo_z2_do.get(),
            "chk_flex": self.chk_flex_var.get(), "chk_ochrona": self.chk_ochrona_var.get(), "chk_raport": self.chk_raport_var.get(),
            "chk_wej": self.chk_wej_var.get(), "wej_kierunek": self.wej_kierunek.get(), "wej_minuty": self.combo_wej.get(), "wej_tol": self.combo_wej_tol.get(),
            "chk_zmiana1": self.chk_zmiana1_var.get(), "zmiana1_czas": self.combo_zmiana1.get(),
            "chk_zmiana2": self.chk_zmiana2_var.get(), "zmiana2_czas": self.combo_zmiana2.get(),
            "chk_wyj": self.chk_wyj_var.get(), "wyj_kierunek": self.wyj_kierunek.get(), "wyj_minuty": self.combo_wyj.get(), "wyj_tol": self.combo_wyj_tol.get(),
            "chk_duplikaty": self.chk_duplikaty_var.get(), "dup_wej_min": self.combo_dup_wej.get(), "dup_wyj_min": self.combo_dup_wyj.get(),
            "chk_pomylki": self.chk_pomylki_var.get(), "pomylki_min": self.combo_pomylki_val.get(),
            "chk_midnight": self.chk_midnight_var.get(), "midnight_limit": self.combo_midnight_val.get(),
            "chk_ostrzegaj_polnoc": self.chk_ostrzegaj_polnoc_var.get(),
            "chk_usun_18": self.chk_usun_18_var.get(),
            "chk_przepustka": self.chk_przepustka_var.get(), "pracownicy_7h": self.pracownicy_7h_var.get(),
            "pracownicy_6_14": self.pracownicy_6_14_var.get(), "pracownicy_13_21": self.pracownicy_13_21_var.get(), 
            "pracownicy_8_16": self.pracownicy_8_16_var.get(), "pracownicy_16_24": self.pracownicy_16_24_var.get(),
            "chk_nadgodziny": self.chk_nadgodziny_var.get(), "nadgodziny_min": self.combo_nadgodziny_val.get(),
            "chk_nadgodziny_skok": self.chk_nadgodziny_skok_var.get(), "nadgodziny_skok_min": self.combo_nadgodziny_skok_val.get(),
            "chk_nadgodziny_wyjatek": self.chk_nadgodziny_wyjatek_var.get(),
            "dzialy_wyjatek": self.dzialy_wyjatek_var.get(),
            "nadgodziny_wyjatek_min": self.combo_nadgodziny_wyjatek_val.get(),
            "nadgodziny_wyjatek_skok_min": self.combo_nadgodziny_wyjatek_skok_val.get(),
            "pracownicy_ignorowani": self.pracownicy_ignorowani_var.get()
        }
        if os.name == 'nt' and os.path.exists(CONFIG_FILE):
            try: ctypes.windll.kernel32.SetFileAttributesW(CONFIG_FILE, 0x80)
            except: pass
        with open(CONFIG_FILE, 'w') as f: json.dump(s, f)
        if os.name == 'nt':
            try: ctypes.windll.kernel32.SetFileAttributesW(CONFIG_FILE, 0x02)
            except: pass

    def laduj_plik(self):
        self.plik_sciezka = filedialog.askopenfilename(filetypes=[("Pliki tekstowe", "*.txt")])
        if not self.plik_sciezka: return
        try:
            with open(self.plik_sciezka, 'r', encoding='utf-8') as f:
                self.dane_zaladowane = f.readlines()
            pracownicy = {p.strip().split(';')[1] for p in self.dane_zaladowane if len(p.split(';')) >= 3}
            self.lbl_status.config(text=f"Dane RCP: {os.path.basename(self.plik_sciezka)}\nWczytano {len(pracownicy)} Pracowników | Łącznie wpisów: {len(self.dane_zaladowane)}", fg="green")
        except Exception as e: messagebox.showerror("Błąd", str(e))

    def przetworz_slownik_zdarzen(self, dane_zgrupowane):
        self.dane_do_zapisu.clear()
        self.kontekst_pracownikow.clear()

        int_wej, int_wyj = int(self.combo_wej.get()), int(self.combo_wyj.get())
        tol_wej, tol_wyj = int(self.combo_wej_tol.get()), int(self.combo_wyj_tol.get())
        limit_wej, limit_wyj = int(self.combo_dup_wej.get()), int(self.combo_dup_wyj.get())
        
        lista_pracownikow_7h = [x.strip() for x in self.pracownicy_7h_var.get().replace(';', ',').split(',') if x.strip()]
        lista_s6_14 = [x.strip() for x in self.pracownicy_6_14_var.get().replace(';', ',').split(',') if x.strip()]
        lista_s13_21 = [x.strip() for x in self.pracownicy_13_21_var.get().replace(';', ',').split(',') if x.strip()]
        lista_s8_16 = [x.strip() for x in self.pracownicy_8_16_var.get().replace(';', ',').split(',') if x.strip()]
        lista_s16_24 = [x.strip() for x in self.pracownicy_16_24_var.get().replace(';', ',').split(',') if x.strip()]

        for (data, pracownik), zdarzenia in dane_zgrupowane.items():
            zdarzenia.sort(key=lambda x: parse_czas_do_minut(x['czas']))
            
            jest_na_7h = pracownik in lista_pracownikow_7h
            wymiar_pracy_minuty = 420 if jest_na_7h else 480
            wymiar_pracy_prog = 415 if jest_na_7h else 475
            
            # FILTROWANIE DUPLIKATÓW TEGO SAMEGO KODU
            if self.chk_duplikaty_var.get():
                bez_duplikatow, ost_czas = [], {}
                for z in zdarzenia:
                    k, c = z['kod'], z['czas']
                    if k == '00' and '00' in ost_czas and oblicz_roznice_minut(ost_czas['00'], c) <= limit_wej: continue
                    if k == '16' and '16' in ost_czas and oblicz_roznice_minut(ost_czas['16'], c) <= limit_wyj: continue
                    ost_czas[k] = c
                    bez_duplikatow.append(z)
                zdarzenia = bez_duplikatow

            # FILTROWANIE POMYŁKOWYCH ODBIĆ
            if self.chk_pomylki_var.get():
                try: limit_pom = int(self.combo_pomylki_val.get())
                except: limit_pom = 2
                
                i = 0
                while i < len(zdarzenia) - 1:
                    z1 = zdarzenia[i]
                    z2 = zdarzenia[i+1]
                    diff = oblicz_roznice_minut(z1['czas'], z2['czas'])
                    
                    if diff <= limit_pom:
                        if z1['kod'] != z2['kod']:
                            if z1['kod'] in ['18', '25'] and z2['kod'] == '00' and diff > 2:
                                i += 1
                                continue
                            zdarzenia.pop(i)
                            continue
                    i += 1

            if self.chk_przepustka_var.get() and zdarzenia:
                if zdarzenia[-1]['kod'] == '25': zdarzenia[-1]['kod'] = '16'

            # Usuwanie KOD 18
            czyste_zdarzenia = []
            skip_next_00 = False
            for z in zdarzenia:
                if z['kod'] == '18' and self.chk_usun_18_var.get():
                    skip_next_00 = True
                    continue
                if z['kod'] == '00' and skip_next_00:
                    skip_next_00 = False
                    continue
                czyste_zdarzenia.append(z)
                skip_next_00 = False
            zdarzenia = czyste_zdarzenia

            wejscia_surowe = [z for z in zdarzenia if z['kod'] == '00']
            typ_zmiany = "godziny ruchome"
            if wejscia_surowe:
                pierwsze_wej_surowe = format_czas_gui(wejscia_surowe[0]['czas'])[:5]
                z1_od, z1_do = self.combo_z1_od.get(), self.combo_z1_do.get()
                z2_od, z2_do = self.combo_z2_od.get(), self.combo_z2_do.get()
                
                in_6_14, in_13_21 = pracownik in lista_s6_14, pracownik in lista_s13_21
                in_8_16, in_16_24 = pracownik in lista_s8_16, pracownik in lista_s16_24

                if in_6_14 and in_13_21: typ_zmiany = "Sztywna 06:00-14:00" if pierwsze_wej_surowe < "10:00" else "Sztywna 13:00-21:00"
                elif in_6_14 and in_8_16: typ_zmiany = "Sztywna 06:00-14:00" if pierwsze_wej_surowe < "07:00" else "Sztywna 08:00-16:00"
                elif in_13_21 and in_8_16: typ_zmiany = "Sztywna 08:00-16:00" if pierwsze_wej_surowe < "10:30" else "Sztywna 13:00-21:00"
                elif in_6_14 and in_16_24: typ_zmiany = "Sztywna 06:00-14:00" if pierwsze_wej_surowe < "11:00" else "Sztywna 16:00-00:00"
                elif in_13_21 and in_16_24: typ_zmiany = "Sztywna 13:00-21:00" if pierwsze_wej_surowe < "14:30" else "Sztywna 16:00-00:00"
                elif in_8_16 and in_16_24: typ_zmiany = "Sztywna 08:00-16:00" if pierwsze_wej_surowe < "12:00" else "Sztywna 16:00-00:00"
                elif in_6_14: typ_zmiany = "Sztywna 06:00-14:00"
                elif in_13_21: typ_zmiany = "Sztywna 13:00-21:00"
                elif in_8_16: typ_zmiany = "Sztywna 08:00-16:00"
                elif in_16_24: typ_zmiany = "Sztywna 16:00-00:00"
                else:
                    if z1_od <= pierwsze_wej_surowe <= z1_do: typ_zmiany = "Zmiana 1"
                    elif z2_od <= pierwsze_wej_surowe <= z2_do: typ_zmiany = "Zmiana 2"

            surowy_czas = 0
            w_pracy_surowy = False
            ost_wej_surowy = None
            pierwsze_odbicie_zaliczone = False

            for z in zdarzenia:
                if z['kod'] == '00':
                    if not w_pracy_surowy:
                        w_pracy_surowy = True
                        c_start = format_czas_gui(z['czas'])[:5]
                        
                        g_int = int(c_start.split(':')[0])
                        if g_int < 24:
                            if not pierwsze_odbicie_zaliczone:
                                if typ_zmiany == "Zmiana 1" and self.chk_zmiana1_var.get() and self.combo_zmiana1.get() <= format_czas_gui(c_start)[:5] < '06:00': c_start = '06:00'
                                elif typ_zmiany == "Zmiana 2" and self.chk_zmiana2_var.get() and self.combo_zmiana2.get() <= format_czas_gui(c_start)[:5] < '14:00': c_start = '14:00'
                                elif typ_zmiany == "Sztywna 06:00-14:00" and "04:00" <= format_czas_gui(c_start)[:5] < '06:00': c_start = '06:00'
                                elif typ_zmiany == "Sztywna 13:00-21:00" and "11:00" <= format_czas_gui(c_start)[:5] < '13:00': c_start = '13:00'
                                elif typ_zmiany == "Sztywna 08:00-16:00" and "06:00" <= format_czas_gui(c_start)[:5] < '08:00': c_start = '08:00'
                                elif typ_zmiany == "Sztywna 16:00-00:00" and "14:00" <= format_czas_gui(c_start)[:5] < '16:00': c_start = '16:00'
                                pierwsze_odbicie_zaliczone = True
                                
                        ost_wej_surowy = z['czas']
                elif z['kod'] in ['16', '25']:
                    if w_pracy_surowy:
                        w_pracy_surowy = False
                        surowy_czas += oblicz_roznice_minut(ost_wej_surowy, z['czas'])
                        ost_wej_surowy = None

            wejscia = [z for z in zdarzenia if z['kod'] == '00']
            wyjscia = [z for z in zdarzenia if z['kod'] in ['16', '25']]

            for z in zdarzenia:
                if 'czas_skorygowany' not in z: z['czas_skorygowany'] = z['czas']
                if z['kod'] == '00':
                    c_roboczy = z['czas']
                    g_int = int(c_roboczy.split(':')[0])
                    
                    if g_int < 24:
                        if typ_zmiany == "godziny ruchome":
                            if self.chk_wej_var.get(): c_roboczy = zaokraglij_czas(c_roboczy, self.wej_kierunek.get(), int_wej, tol_wej)
                        elif typ_zmiany == "Zmiana 1":
                            if self.chk_zmiana1_var.get() and self.combo_zmiana1.get() <= format_czas_gui(c_roboczy)[:5] < '06:00': c_roboczy = '06:00'
                            if self.chk_wej_var.get(): c_roboczy = zaokraglij_czas(c_roboczy, self.wej_kierunek.get(), int_wej, tol_wej)
                        elif typ_zmiany == "Zmiana 2":
                            if self.chk_zmiana2_var.get() and self.combo_zmiana2.get() <= format_czas_gui(c_roboczy)[:5] < '14:00': c_roboczy = '14:00'
                            if self.chk_wej_var.get(): c_roboczy = zaokraglij_czas(c_roboczy, self.wej_kierunek.get(), int_wej, tol_wej)
                        elif typ_zmiany == "Sztywna 06:00-14:00":
                            if "04:00" <= format_czas_gui(c_roboczy)[:5] < '06:00': c_roboczy = '06:00'
                            if self.chk_wej_var.get(): c_roboczy = zaokraglij_czas(c_roboczy, self.wej_kierunek.get(), int_wej, tol_wej)
                        elif typ_zmiany == "Sztywna 13:00-21:00":
                            if "11:00" <= format_czas_gui(c_roboczy)[:5] < '13:00': c_roboczy = '13:00'
                            if self.chk_wej_var.get(): c_roboczy = zaokraglij_czas(c_roboczy, self.wej_kierunek.get(), int_wej, tol_wej)
                        elif typ_zmiany == "Sztywna 08:00-16:00":
                            if "06:00" <= format_czas_gui(c_roboczy)[:5] < '08:00': c_roboczy = '08:00'
                            if self.chk_wej_var.get(): c_roboczy = zaokraglij_czas(c_roboczy, self.wej_kierunek.get(), int_wej, tol_wej)
                        elif typ_zmiany == "Sztywna 16:00-00:00":
                            if "14:00" <= format_czas_gui(c_roboczy)[:5] < '16:00': c_roboczy = '16:00'
                            if self.chk_wej_var.get(): c_roboczy = zaokraglij_czas(c_roboczy, self.wej_kierunek.get(), int_wej, tol_wej)
                    else:
                        if self.chk_wej_var.get(): c_roboczy = zaokraglij_czas(c_roboczy, self.wej_kierunek.get(), int_wej, tol_wej)
                    z['czas_skorygowany'] = c_roboczy

            for z in zdarzenia:
                if z['kod'] == '16':
                    c_roboczy = z['czas']
                    is_last_wyjscie = (z == wyjscia[-1]) if wyjscia else False
                    
                    if typ_zmiany == "godziny ruchome" and self.chk_flex_var.get() and wejscia and is_last_wyjscie:
                        pierw_wej_skoryg = wejscia[0]['czas_skorygowany']
                        min_in = parse_czas_do_minut(pierw_wej_skoryg)
                        surowy_span = int(oblicz_roznice_minut(wejscia[0]['czas'], wyjscia[-1]['czas']))
                        zaokraglony_span = surowy_span
                        reszta = surowy_span % int_wyj
                        
                        if reszta != 0:
                            if self.wyj_kierunek.get() == "dół":
                                if reszta <= tol_wyj: zaokraglony_span -= reszta
                                elif (int_wyj - reszta) <= tol_wyj: zaokraglony_span += (int_wyj - reszta)
                                else: zaokraglony_span -= reszta
                            else:
                                if (int_wyj - reszta) <= tol_wyj: zaokraglony_span += (int_wyj - reszta)
                                elif reszta <= tol_wyj: zaokraglony_span -= reszta
                                else: zaokraglony_span += (int_wyj - reszta)
                        suma_minut = min_in + zaokraglony_span
                        c_roboczy = formatuj_minuty_do_czasu(suma_minut)
                        
                    else:
                        if self.chk_wyj_var.get(): c_roboczy = zaokraglij_czas(c_roboczy, self.wyj_kierunek.get(), int_wyj, tol_wyj)
                        if self.chk_ochrona_var.get() and typ_zmiany in ["Zmiana 1", "Zmiana 2", "Sztywna 06:00-14:00", "Sztywna 13:00-21:00", "Sztywna 08:00-16:00", "Sztywna 16:00-00:00"] and is_last_wyjscie:
                            if surowy_czas >= wymiar_pracy_prog and wejscia: 
                                pierw_wej_skoryg = wejscia[0]['czas_skorygowany']
                                nowa_roznica = oblicz_roznice_minut(pierw_wej_skoryg, c_roboczy)
                                if nowa_roznica < wymiar_pracy_minuty: 
                                    min_in = parse_czas_do_minut(pierw_wej_skoryg)
                                    suma_minut = min_in + wymiar_pracy_minuty
                                    c_roboczy = formatuj_minuty_do_czasu(suma_minut) 
                    
                    if is_last_wyjscie and wejscia:
                        pierw_wej_skoryg = wejscia[0]['czas_skorygowany']
                        nowa_roznica = oblicz_roznice_minut(pierw_wej_skoryg, c_roboczy)
                        nadgodziny = nowa_roznica - wymiar_pracy_minuty
                        
                        if nadgodziny > 0:
                            nadgodziny_ostateczne = nadgodziny
                            
                            dzial_pracownika = self.pobierz_dzial_pracownika(pracownik)
                            lista_wyjatkow = [d.strip().lower() for d in self.dzialy_wyjatek_var.get().split(',') if d.strip()]
                            
                            limit_minut = int(self.combo_nadgodziny_val.get()) if self.chk_nadgodziny_var.get() else 0
                            skok = int(self.combo_nadgodziny_skok_val.get()) if self.chk_nadgodziny_skok_var.get() else 0
                            
                            czy_wyjatek = self.chk_nadgodziny_wyjatek_var.get() and dzial_pracownika.lower() in lista_wyjatkow
                            if czy_wyjatek:
                                limit_minut = int(self.combo_nadgodziny_wyjatek_val.get())
                                skok = int(self.combo_nadgodziny_wyjatek_skok_val.get())

                            if limit_minut > 0 and nadgodziny < limit_minut: 
                                nadgodziny_ostateczne = 0
                                
                            if nadgodziny_ostateczne > 0 and skok > 0:
                                nadgodziny_ostateczne = (nadgodziny_ostateczne // skok) * skok
                                
                            if nadgodziny_ostateczne != nadgodziny:
                                min_in = parse_czas_do_minut(pierw_wej_skoryg)
                                suma_minut = min_in + wymiar_pracy_minuty + int(nadgodziny_ostateczne)
                                c_roboczy = formatuj_minuty_do_czasu(suma_minut)
                    
                    z['czas_skorygowany'] = c_roboczy

            lista_zdarzen_ostatecznych = []
            for z in zdarzenia:
                c_roboczy = z['czas_skorygowany']
                c_oryg = z.get('czas_oryg', '---')
                
                lista_zdarzen_ostatecznych.append({
                    'czas_oryg': c_oryg, 
                    'czas': c_roboczy, 
                    'kod': z['kod']
                })
            
            dzial = self.pobierz_dzial_pracownika(pracownik)
            
            self.dane_do_zapisu[(data, pracownik)] = lista_zdarzen_ostatecznych
            self.kontekst_pracownikow[(data, pracownik)] = {
                'wymiar': wymiar_pracy_minuty,
                'typ_zmiany': typ_zmiany,
                'surowy_czas': surowy_czas,
                'nazwisko': self.baza_pracownikow.get(pracownik, "---"),
                'dzial': dzial
            }

    def generuj_raporty(self):
        wpisy_anomalii = []
        wszyscy_info = []
        linie_raportu = []
        
        lista_ignorowanych = [x.strip() for x in self.pracownicy_ignorowani_var.get().replace(';', ',').split(',') if x.strip()]
        
        wszystkie_daty = set(d for d, p in self.dane_do_zapisu.keys())
        dni_robocze = set()
        for d in wszystkie_daty:
            try:
                if czy_dzien_roboczy(d):
                    dni_robocze.add(d)
            except: pass
            
        pracownicy_z_pliku = set(p for d, p in self.dane_do_zapisu.keys())
        wszyscy_pracownicy = set(self.baza_pracownikow.keys()).union(pracownicy_z_pliku)

        for pracownik in wszyscy_pracownicy:
            nazwisko = self.baza_pracownikow.get(pracownik, "---")
            dzial = self.pobierz_dzial_pracownika(pracownik)
            jest_ignorowany = pracownik in lista_ignorowanych
            
            for data in sorted(list(dni_robocze)):
                klucz = (data, pracownik)
                
                jest_na_urlopie = False
                if hasattr(self, 'baza_urlopow') and pracownik in self.baza_urlopow:
                    if data in self.baza_urlopow[pracownik]:
                        jest_na_urlopie = True
                        
                zdarzenia = self.dane_do_zapisu.get(klucz, [])
                
                if not zdarzenia:
                    if not jest_na_urlopie and not jest_ignorowany:
                        uwaga = "Nieobecność"
                        wpisy_anomalii.append({
                            'data': data, 'pracownik': pracownik, 'nazwisko': nazwisko,
                            'dzial': dzial, 'typ_zmiany': "---", 'uwaga': uwaga
                        })
                        wszyscy_info.append({
                            'data': data, 'pracownik': pracownik, 'nazwisko': nazwisko,
                            'dzial': dzial, 'typ_zmiany': "---", 'status': "Nieobecność", 'uwagi': uwaga
                        })
                        linie_raportu.append(f"{data} | Pracownik {pracownik} ({nazwisko}) | Dział: {dzial} | {uwaga}")
                    continue

                ctx = self.kontekst_pracownikow.get(klucz, {})
                wymiar = ctx.get('wymiar', 480)
                typ_zmiany = ctx.get('typ_zmiany', '---')
                surowy_czas = ctx.get('surowy_czas', 0)

                uwagi = []
                braki_odbic, ost_dla_braku = False, None
                for z in zdarzenia:
                    if z['kod'] == '00': ost_dla_braku = z['czas']
                    elif z['kod'] in ['16', '25'] and ost_dla_braku: ost_dla_braku = None
                if ost_dla_braku is not None: braki_odbic = True

                wejscia = [z for z in zdarzenia if z['kod'] == '00']
                wyjscia = [z for z in zdarzenia if z['kod'] in ['16', '25']]
                kody = [z['kod'] for z in zdarzenia]

                if len(wejscia) == 0 and len(wyjscia) > 0: 
                    uwagi.append("Brak wejścia do pracy (00)")
                if braki_odbic: 
                    uwagi.append("Brak wyjścia z pracy (16)")
                if kody and kody[0] != '00': 
                    uwagi.append("Pierwsze odbicie to nie Wejście (00)")
                
                num_16 = kody.count('16')
                if num_16 > 1:
                    uwagi.append(f"Zbyt wiele zakończeń pracy ({num_16}x kod 16)")

                for idx in range(len(zdarzenia)-1):
                    if zdarzenia[idx]['kod'] == '00' and zdarzenia[idx+1]['kod'] == '00':
                        uwagi.append("Powielone wejście (00) z rzędu")
                        break
                        
                for idx in range(len(zdarzenia)-1):
                    if zdarzenia[idx]['kod'] in ['16', '25'] and zdarzenia[idx+1]['kod'] in ['16', '25']:
                        uwagi.append("Powielone wyjście z rzędu")
                        break
                        
                # --- OSTRZEŻENIE O PÓŁNOCY ---
                if self.chk_ostrzegaj_polnoc_var.get():
                    for z in zdarzenia:
                        if z['kod'] in ['16', '25'] and z['czas'] == '24:00':
                            uwagi.append("Ostrzeżenie: Zakończenie pracy o północy (00:00)")
                            break
                
                czas_skor = 0
                w_p_skor, ost_wej_skor = False, None
                for z in zdarzenia:
                    if z['kod'] == '00':
                        if not w_p_skor: w_p_skor = True; ost_wej_skor = z['czas']
                    elif z['kod'] in ['16', '25']:
                        if w_p_skor:
                            w_p_skor = False
                            czas_skor += oblicz_roznice_minut(ost_wej_skor, z['czas'])
                            ost_wej_skor = None

                if wejscia and wyjscia and 0 < czas_skor < wymiar:
                    if not jest_na_urlopie:
                        hh, mm = int(surowy_czas // 60), int(surowy_czas % 60)
                        wymiar_etykieta = "7h" if wymiar == 420 else "8h"
                        uwagi.append(f"Niepełne {wymiar_etykieta} (rzeczywisty czas: {hh:02d}h {mm:02d}m)")
                
                if uwagi:
                    tylko_ostrzezenia = all(u.startswith("Ostrzeżenie") for u in uwagi)
                    status = "Ostrzeżenie : 00:00" if tylko_ostrzezenia else f"Błąd: {', '.join(uwagi)}"
                else:
                    status = "OK"
                    
                if jest_ignorowany and not uwagi:
                    status = "OK (Ignorowany)"
                    
                wszyscy_info.append({
                    'data': data, 'pracownik': pracownik, 'nazwisko': nazwisko,
                    'dzial': dzial, 'typ_zmiany': typ_zmiany, 'status': status, 'uwagi': ", ".join(uwagi)
                })

                if uwagi: 
                    wpisy_anomalii.append({
                        'data': data, 'pracownik': pracownik, 'nazwisko': nazwisko,
                        'dzial': dzial, 'typ_zmiany': typ_zmiany, 'uwaga': ", ".join(uwagi)
                    })
                    linie_raportu.append(f"{data} | Pracownik {pracownik} ({nazwisko}) | Dział: {dzial} | Typ zmiany: {typ_zmiany} | {', '.join(uwagi)}")
                
        return wpisy_anomalii, wszyscy_info, linie_raportu

    def procesuj(self):
        if not self.dane_zaladowane:
            messagebox.showwarning("Uwaga", "Najpierw załaduj plik!")
            return

        self.save_settings()
        
        try:
            wszystkie_zdarzenia = []
            for linia in self.dane_zaladowane:
                linia = linia.strip()
                if not linia: continue
                f = linia.split(';')
                if len(f) == 3:
                    wszystkie_zdarzenia.append({'data': f[0][:10], 'czas': f[0][11:], 'pracownik': f[1], 'kod': f[2]})

            pracownicy = set(z['pracownik'] for z in wszystkie_zdarzenia)
            naprawione_zdarzenia = []
            
            limit_nocny = self.combo_midnight_val.get() if self.chk_midnight_var.get() else "00:00"
            limit_nocny_minuty = parse_czas_do_minut(limit_nocny)
            
            for p in pracownicy:
                zdarzenia_pracownika = [z for z in wszystkie_zdarzenia if z['pracownik'] == p]
                zdarzenia_pracownika.sort(key=lambda x: (x['data'], x['czas']))
                
                # Usuwamy wczesne, "sieroce" wyjścia na samym początku pliku
                while zdarzenia_pracownika and zdarzenia_pracownika[0]['kod'] in ['16', '25', '18']:
                    if self.chk_midnight_var.get() and parse_czas_do_minut(zdarzenia_pracownika[0]['czas']) <= limit_nocny_minuty: 
                        zdarzenia_pracownika.pop(0)
                    else: break
                
                naprawione_zdarzenia_pracownika = []
                for curr in zdarzenia_pracownika:
                    # Przesuwamy zdarzenia po północy do poprzedniego dnia, by zachować chronologię
                    if self.chk_midnight_var.get():
                        if parse_czas_do_minut(curr['czas']) <= limit_nocny_minuty:
                            if naprawione_zdarzenia_pracownika:
                                prev = naprawione_zdarzenia_pracownika[-1]
                                try:
                                    dt_curr = datetime.strptime(curr['data'], "%Y.%m.%d")
                                    dt_prev = datetime.strptime(prev['data'][:10], "%Y.%m.%d")
                                    g_prev, _ = map(int, prev['czas'].split(':'))
                                    
                                    # Przesuwamy tylko, gdy wczorajsza zmiana nie jest jeszcze zamknięta wyjściem!
                                    if prev['kod'] not in ['16', '25']:
                                        if (dt_curr - dt_prev).days == 1 or (dt_curr == dt_prev and g_prev >= 24):
                                            curr['data'] = prev['data'][:10]
                                            godz, minuty = map(int, curr['czas'].split(':'))
                                            curr['czas'] = f"{24 + godz:02d}:{minuty:02d}"
                                except: pass
                    naprawione_zdarzenia_pracownika.append(curr)
                naprawione_zdarzenia.extend(naprawione_zdarzenia_pracownika)
                
            wszystkie_zdarzenia = naprawione_zdarzenia

            dane_zgrupowane = {}
            for z in wszystkie_zdarzenia:
                klucz = (z['data'], z['pracownik'])
                if klucz not in dane_zgrupowane: dane_zgrupowane[klucz] = []
                dane_zgrupowane[klucz].append({'czas': z['czas'], 'kod': z['kod'], 'czas_oryg': z['czas']})

            self.przetworz_slownik_zdarzen(dane_zgrupowane)
            wpisy_anomalii, wszyscy_info, linie_raportu = self.generuj_raporty()
            
            path_wynik, path_raport = self.generuj_nazwy_plikow(self.plik_sciezka)

            if self.chk_raport_var.get() or wpisy_anomalii:
                self.otworz_menedzer_korekt(path_wynik, path_raport)
            else:
                self.finalizuj_zapis(self.dane_do_zapisu, path_wynik, path_raport, linie_raportu, False)

        except Exception as e: 
            messagebox.showerror("Błąd Krytyczny w procesuj", traceback.format_exc())

    def buduj_raport_tekst(self, lista_zaznaczonych):
        out = []
        out.append("="*65)
        out.append(" SZCZEGÓŁOWY RAPORT ODBIĆ - KOREKTOR HR ")
        out.append(f" Wygenerowano: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        out.append("="*65)
        
        for item in lista_zaznaczonych:
            d, pr, nazw, dzial = item['data'], item['pracownik'], item['nazwisko'], item.get('dzial', '---')
            status = item.get('status', '---')
            out.append(f"\n▶ DATA: {d} | PRACOWNIK: {pr} ({nazw}) | DZIAŁ: {dzial}")
            out.append(f"  STATUS: {status}")
            out.append("  SZCZEGÓŁY ODBIĆ:")
            
            zdarzenia = self.dane_do_zapisu.get((d, pr), [])
            if not zdarzenia:
                out.append("    [Brak zapisanych zdarzeń]")
            else:
                for z in zdarzenia:
                    oryg = format_czas_gui(z.get('czas_oryg', '---'))
                    kor = format_czas_gui(z['czas'])
                    opis = KODY_MAPA.get(z['kod'], z['kod'])
                    out.append(f"    - [Oryginał: {oryg}]  -->  [Korekta: {kor}]  |  {opis}")
        
        out.append("\n" + "="*65)
        return "\n".join(out)

    def otworz_menedzer_korekt(self, path_wynik, path_raport):
        obecnie_wybrany_klucz = None
        txt_uwagi = None # Bezpieczna deklaracja dla closure
        
        okno = tk.Toplevel(self.root)
        okno.title("Menedżer Danych i Korekt - Podgląd i Edycja")
        okno.geometry("1300x700")
        okno.grab_set() 

        lbl_top = tk.Label(okno, text="Weryfikacja danych przed zapisem pliku wyjściowego.", fg="black", font=("Arial", 10, "bold"), pady=5)
        lbl_top.pack()

        paned = ttk.PanedWindow(okno, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # LEWA STRONA (Filtry)
        f_filtry = tk.Frame(paned, width=200)
        paned.add(f_filtry, weight=0)
        tk.Label(f_filtry, text="Filtruj działy", font=("Arial", 9, "bold")).pack(anchor="w", pady=(0, 5))
        f_filtry_btn = tk.Frame(f_filtry)
        f_filtry_btn.pack(fill=tk.X, pady=(0, 5))

        def toggle_filtry(stan):
            for var in self.filtry_dzialow_vars.values(): var.set(stan)
            odswiez_GUI(pokaz_komunikat=False)

        tk.Button(f_filtry_btn, text="Zaznacz", command=lambda: toggle_filtry(True), bg="#e1e1e1").pack(side="left", expand=True, fill="x", padx=1)
        tk.Button(f_filtry_btn, text="Odznacz", command=lambda: toggle_filtry(False), bg="#e1e1e1").pack(side="left", expand=True, fill="x", padx=1)

        canvas_f = tk.Canvas(f_filtry, highlightthickness=0, width=190)
        scroll_f = ttk.Scrollbar(f_filtry, orient="vertical", command=canvas_f.yview)
        frame_in_canvas = tk.Frame(canvas_f)
        frame_in_canvas.bind("<Configure>", lambda e: canvas_f.configure(scrollregion=canvas_f.bbox("all")))
        canvas_f.create_window((0, 0), window=frame_in_canvas, anchor="nw")
        canvas_f.configure(yscrollcommand=scroll_f.set)
        scroll_f.pack(side="right", fill="y")
        canvas_f.pack(side="left", fill="both", expand=True)

        unikalne_dzialy = sorted(list(set(self.baza_dzialow.values())))
        if "Nieprzypisani" not in unikalne_dzialy: unikalne_dzialy.append("Nieprzypisani")
        
        self.filtry_dzialow_vars = {}
        for d in unikalne_dzialy:
            var = tk.BooleanVar(value=True)
            self.filtry_dzialow_vars[d] = var
            cb = tk.Checkbutton(frame_in_canvas, text=d, variable=var, wraplength=180, justify="left", command=lambda: odswiez_GUI(pokaz_komunikat=False))
            cb.pack(anchor="w")

        # ŚRODEK (Tabele)
        f_lewa = tk.Frame(paned, width=1250)
        paned.add(f_lewa, weight=6)
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TNotebook.Tab', padding=[15, 5], font=('Arial', 9))
        style.map('TNotebook.Tab', background=[('selected', '#4CAF50')], foreground=[('selected', 'white')], expand=[('selected', [1, 1, 1, 0])])
        style.configure('Treeview', font=('Arial', 10), rowheight=24)
        style.configure('Treeview.Heading', font=('Arial', 10, 'bold'))
        
        notebook = ttk.Notebook(f_lewa)
        notebook.pack(fill=tk.BOTH, expand=True)

        tab_anomalie = tk.Frame(notebook)
        tab_wszyscy = tk.Frame(notebook)
        notebook.add(tab_anomalie, text="Nieprawidłowości")
        notebook.add(tab_wszyscy, text="Wszystkie wpisy")

        scroll_anom = ttk.Scrollbar(tab_anomalie, orient="vertical")
        kolumny_anom = ("Wyb.", "Data", "Pracownik", "Nazwisko", "Dział", "Problem")
        drzewo_anom = ttk.Treeview(tab_anomalie, columns=kolumny_anom, show='headings', selectmode="browse", yscrollcommand=scroll_anom.set)
        scroll_anom.config(command=drzewo_anom.yview)
        scroll_anom.pack(side="right", fill="y")
        drzewo_anom.pack(side="left", fill="both", expand=True)

        scroll_wszyscy = ttk.Scrollbar(tab_wszyscy, orient="vertical")
        kolumny_wszyscy = ("Wyb.", "Data", "Pracownik", "Nazwisko", "Dział", "Status")
        drzewo_wszyscy = ttk.Treeview(tab_wszyscy, columns=kolumny_wszyscy, show='headings', selectmode="browse", yscrollcommand=scroll_wszyscy.set)
        scroll_wszyscy.config(command=drzewo_wszyscy.yview)
        scroll_wszyscy.pack(side="right", fill="y")
        drzewo_wszyscy.pack(side="left", fill="both", expand=True)

        def sortuj_drzewo(drzewo, col, reverse):
            l = [(drzewo.set(k, col), k) for k in drzewo.get_children('')]
            l.sort(reverse=reverse)
            for index, (val, k) in enumerate(l): drzewo.move(k, '', index)
            drzewo.heading(col, command=lambda _col=col: sortuj_drzewo(drzewo, _col, not reverse))

        drzewo_anom.heading("Wyb.", text="☑")
        drzewo_anom.heading("Data", text="Data", command=lambda: sortuj_drzewo(drzewo_anom, "Data", False))
        drzewo_anom.heading("Pracownik", text="Nr", command=lambda: sortuj_drzewo(drzewo_anom, "Pracownik", False))
        drzewo_anom.heading("Nazwisko", text="Nazwisko", command=lambda: sortuj_drzewo(drzewo_anom, "Nazwisko", False))
        drzewo_anom.heading("Dział", text="Dział", command=lambda: sortuj_drzewo(drzewo_anom, "Dział", False))
        drzewo_anom.heading("Problem", text="Problem", command=lambda: sortuj_drzewo(drzewo_anom, "Problem", False))
        drzewo_anom.column("Wyb.", width=30, anchor="center")
        drzewo_anom.column("Data", width=90, anchor="center")
        drzewo_anom.column("Pracownik", width=50, anchor="center")
        drzewo_anom.column("Nazwisko", width=150)
        drzewo_anom.column("Dział", width=200)
        drzewo_anom.column("Problem", width=300)

        drzewo_wszyscy.heading("Wyb.", text="☑")
        drzewo_wszyscy.heading("Data", text="Data", command=lambda: sortuj_drzewo(drzewo_wszyscy, "Data", False))
        drzewo_wszyscy.heading("Pracownik", text="Nr", command=lambda: sortuj_drzewo(drzewo_wszyscy, "Pracownik", False))
        drzewo_wszyscy.heading("Nazwisko", text="Nazwisko", command=lambda: sortuj_drzewo(drzewo_wszyscy, "Nazwisko", False))
        drzewo_wszyscy.heading("Dział", text="Dział", command=lambda: sortuj_drzewo(drzewo_wszyscy, "Dział", False))
        drzewo_wszyscy.heading("Status", text="Status", command=lambda: sortuj_drzewo(drzewo_wszyscy, "Status", False))
        drzewo_wszyscy.column("Wyb.", width=30, anchor="center")
        drzewo_wszyscy.column("Data", width=90, anchor="center")
        drzewo_wszyscy.column("Pracownik", width=50, anchor="center")
        drzewo_wszyscy.column("Nazwisko", width=150)
        drzewo_wszyscy.column("Dział", width=200)
        drzewo_wszyscy.column("Status", width=300)

        f_akcje_lewe = tk.Frame(f_lewa)
        f_akcje_lewe.pack(fill=tk.X, pady=5)
        f_checks = tk.Frame(f_akcje_lewe)
        f_checks.pack(fill=tk.X, pady=(0, 5))
        
        def set_all_checks(val):
            aktywna = notebook.index(notebook.select())
            drzewo = drzewo_anom if aktywna == 0 else drzewo_wszyscy
            for item in drzewo.get_children():
                vals = list(drzewo.item(item, "values"))
                vals[0] = val
                drzewo.item(item, values=vals)

        tk.Button(f_checks, text="Zaznacz wszystkie", command=lambda: set_all_checks("☑"), bg="#e1e1e1").pack(side="left", padx=2)
        tk.Button(f_checks, text="Odznacz wszystkie", command=lambda: set_all_checks("☐"), bg="#e1e1e1").pack(side="left", padx=2)

        def odswiez_GUI(pokaz_komunikat=True):
            nonlocal obecnie_wybrany_klucz
            if pokaz_komunikat:
                dane_zgrupowane_nowe = {}
                for (data, pracownik), zdarzenia_stare in self.dane_do_zapisu.items():
                    surowe = []
                    for z in zdarzenia_stare:
                        czas_baza = z['czas_oryg'] if z.get('czas_oryg') and z['czas_oryg'] != '---' else z['czas']
                        surowe.append({'czas': czas_baza, 'czas_oryg': czas_baza, 'kod': z['kod']})
                    dane_zgrupowane_nowe[(data, pracownik)] = surowe
                self.przetworz_slownik_zdarzen(dane_zgrupowane_nowe)
                
            wpisy_anomalii, wszyscy_info, _ = self.generuj_raporty()
            
            aktywne_dzialy = [d for d, var in self.filtry_dzialow_vars.items() if var.get()]
            wpisy_anomalii = [w for w in wpisy_anomalii if w.get('dzial', 'Nieprzypisani') in aktywne_dzialy]
            wszyscy_info = [w for w in wszyscy_info if w.get('dzial', 'Nieprzypisani') in aktywne_dzialy]

            for i in drzewo_anom.get_children(): drzewo_anom.delete(i)
            for i in drzewo_wszyscy.get_children(): drzewo_wszyscy.delete(i)
            
            wpisy_anomalii.sort(key=lambda x: x['nazwisko'])
            wszyscy_info.sort(key=lambda x: x['nazwisko'])

            for w in wpisy_anomalii:
                drzewo_anom.insert('', 'end', values=("☐", w['data'], w['pracownik'], w['nazwisko'], w['dzial'], w['uwaga']))
            for w in wszyscy_info:
                drzewo_wszyscy.insert('', 'end', values=("☐", w['data'], w['pracownik'], w['nazwisko'], w['dzial'], w['status']))
                
            notebook.tab(0, text=f"Nieprawidłowości ({len(wpisy_anomalii)})")
            notebook.tab(1, text=f"Wszystkie wpisy ({len(wszyscy_info)})")
            
            obecnie_wybrany_klucz = None
            if 'odswiez_logi' in locals(): odswiez_logi(None)
            
            if txt_uwagi:
                txt_uwagi.config(state=tk.NORMAL)
                txt_uwagi.delete(1.0, tk.END)
                txt_uwagi.insert(tk.END, "Wybierz wpis z listy po lewej stronie.")
                txt_uwagi.config(bg="#f5f5f5", fg="#000000", state=tk.DISABLED)
            
            if pokaz_komunikat:
                messagebox.showinfo("Odświeżono pomyślnie", "Dane przeliczone.\n\nPracownicy naprawieni zniknęli z listy błędów.", parent=okno)

        tk.Button(f_checks, text="🔄 Odśwież Wpisy (Przelicz wszystko)", bg="#2196F3", fg="white", font=("Arial", 9, "bold"), command=odswiez_GUI).pack(side="right", padx=2)

        f_raporty = tk.Frame(f_akcje_lewe)
        f_raporty.pack(fill=tk.X)

        def zapisz_i_otworz_plik(tekst, domyslna_nazwa):
            path = filedialog.asksaveasfilename(defaultextension=".txt", initialfile=domyslna_nazwa, title="Zapisz raport jako...")
            if path:
                with open(path, 'w', encoding='utf-8') as f: f.write(tekst)
                os.startfile(path)

        def wygeneruj_zaznaczone():
            aktywna = notebook.index(notebook.select())
            drzewo = drzewo_anom if aktywna == 0 else drzewo_wszyscy
            zaznaczone = []
            for k in drzewo.get_children():
                vals = drzewo.item(k, "values")
                if vals[0] == "☑":
                    zaznaczone.append({'data': vals[1], 'pracownik': vals[2], 'nazwisko': vals[3], 'dzial': vals[4], 'status': vals[5]})
            if not zaznaczone:
                messagebox.showinfo("Brak wpisów", "Zaznacz wpisy klikając checkbox.", parent=okno)
                return
            zapisz_i_otworz_plik(self.buduj_raport_tekst(zaznaczone), "Raport_Wlasny_Wybrane.txt")

        def wygeneruj_wszystkie_bledy():
            anomalie, _, _ = self.generuj_raporty()
            if not anomalie: return messagebox.showinfo("Info", "Brak błędów do wygenerowania!", parent=okno)
            for a in anomalie: a['status'] = a.pop('uwaga')
            zapisz_i_otworz_plik(self.buduj_raport_tekst(anomalie), "Raport_Wszystkich_Bledow.txt")

        tk.Button(f_raporty, text="📝 Wygeneruj listę (z zaznaczonych)", command=wygeneruj_zaznaczone, bg="#ffeb3b").pack(side="left", padx=2)
        tk.Button(f_raporty, text="⚠ Wygeneruj pełną listę nieprawidłowości", command=wygeneruj_wszystkie_bledy, bg="#ff9800").pack(side="left", padx=2)

        def dodaj_brakujacego():
            pop = tk.Toplevel(okno)
            pop.title("Dopisz pracownika")
            pop.geometry("300x200")
            pop.grab_set()

            tk.Label(pop, text="Data (YYYY.MM.DD):").pack(pady=(10, 0))
            ent_data = tk.Entry(pop, justify="center")
            ent_data.insert(0, list(self.dane_do_zapisu.keys())[0][0] if self.dane_do_zapisu else datetime.now().strftime("%Y.%m.%d"))
            ent_data.pack()

            tk.Label(pop, text="Pracownik (Nr lub Nazwisko):").pack(pady=(5, 0))
            lista_prac = [f"{nr} - {nazwa}" for nr, nazwa in self.baza_pracownikow.items()]
            cb_prac = ttk.Combobox(pop, values=lista_prac)
            cb_prac.pack(fill="x", padx=20)

            def zapisz_nowego():
                d, p_val = ent_data.get().strip(), cb_prac.get().strip()
                nr = p_val.split(" - ")[0] if " - " in p_val else p_val
                
                if not re.match(r"^\d{4}\.\d{2}\.\d{2}$", d): return messagebox.showerror("Błąd", "Nieprawidłowy format daty!", parent=pop)
                if not nr: return

                if (d, nr) not in self.dane_do_zapisu:
                    self.dane_do_zapisu[(d, nr)] = []
                    self.kontekst_pracownikow[(d, nr)] = {
                        'wymiar': 480, 'typ_zmiany': 'Ręcznie dodany', 'surowy_czas': 0,
                        'nazwisko': self.baza_pracownikow.get(nr, "---"), 'dzial': self.pobierz_dzial_pracownika(nr)
                    }
                pop.destroy()
                odswiez_GUI(pokaz_komunikat=True)

            tk.Button(pop, text="Dodaj do listy dnia", command=zapisz_nowego, bg="#4CAF50", fg="white").pack(pady=15, fill="x", padx=20)

        tk.Button(f_akcje_lewe, text="➕ Brak pracownika w logach? Dopisz go", command=dodaj_brakujacego, bg="#2196F3", fg="white").pack(fill="x", pady=(5, 0))

        # PRAWA STRONA (Szczegóły)
        f_prawa = tk.Frame(paned, width=150)
        paned.add(f_prawa, weight=1)
        tk.Label(f_prawa, text="Szczegóły odbić", font=("Arial", 9, "bold")).pack(anchor="w")
        
        # --- NOWE POLE TEKSTOWE NA UWAGI ---
        f_uwagi_info = tk.LabelFrame(f_prawa, text=" Komunikat systemu ", fg="#d32f2f", font=("Arial", 9, "bold"))
        f_uwagi_info.pack(fill=tk.X, pady=(0, 5), padx=2)
        txt_uwagi = tk.Text(f_uwagi_info, height=3, width=40, wrap=tk.WORD, font=("Arial", 9), bg="#f5f5f5", fg="#000000")
        txt_uwagi.pack(fill=tk.X, padx=2, pady=2)
        txt_uwagi.insert(tk.END, "Wybierz wpis z listy po lewej stronie.")
        txt_uwagi.config(state=tk.DISABLED)

        frame_drzewo_log = tk.Frame(f_prawa)
        frame_drzewo_log.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        scroll_log = ttk.Scrollbar(frame_drzewo_log, orient="vertical")
        kolumny_log = ("Czas oryg.", "Czas korekty", "Kod")
        drzewo_log = ttk.Treeview(frame_drzewo_log, columns=kolumny_log, show='headings', selectmode="browse", yscrollcommand=scroll_log.set)
        scroll_log.config(command=drzewo_log.yview)
        scroll_log.pack(side="right", fill="y")
        drzewo_log.pack(side="left", fill="both", expand=True)

        drzewo_log.heading("Czas oryg.", text="Czas oryg.")
        drzewo_log.heading("Czas korekty", text="Czas korekty")
        drzewo_log.heading("Kod", text="Zdarzenie")
        drzewo_log.column("Czas oryg.", width=50, anchor="center")
        drzewo_log.column("Czas korekty", width=50, anchor="center")
        drzewo_log.column("Kod", width=50)

        f_przyciski = tk.Frame(f_prawa)
        f_przyciski.pack(fill=tk.X)
        btn_dodaj = tk.Button(f_przyciski, text="Dodaj", bg="#e1e1e1")
        btn_dodaj.pack(side="left", expand=True, fill="x", padx=2)
        btn_edytuj = tk.Button(f_przyciski, text="Edytuj", bg="#e1e1e1")
        btn_edytuj.pack(side="left", expand=True, fill="x", padx=2)
        btn_usun = tk.Button(f_przyciski, text="Usuń", bg="#ffcccc")
        btn_usun.pack(side="left", expand=True, fill="x", padx=2)

        btn_zapisz = tk.Button(okno, text="ZATWIERDŹ WSZYSTKIE POPRAWKI I WYGENERUJ PLIK", bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), height=2)
        btn_zapisz.pack(fill="x", padx=20, pady=10)

        def odswiez_logi(klucz):
            for i in drzewo_log.get_children(): drzewo_log.delete(i)
            if klucz and klucz in self.dane_do_zapisu:
                for z in self.dane_do_zapisu[klucz]:
                    oryg = format_czas_gui(z.get('czas_oryg', '---'))
                    kor = format_czas_gui(z['czas'])
                    drzewo_log.insert('', 'end', values=(oryg, kor, KODY_MAPA.get(z['kod'], z['kod'])))

        def on_tree_click(event, tree):
            region = tree.identify("region", event.x, event.y)
            if region == "cell" and tree.identify_column(event.x) == '#1':
                item = tree.identify_row(event.y)
                if item:
                    vals = list(tree.item(item, "values"))
                    vals[0] = "☑" if vals[0] == "☐" else "☐"
                    tree.item(item, values=vals)

        def on_employee_select(event):
            nonlocal obecnie_wybrany_klucz
            sel = event.widget.selection()
            if not sel: return
            item = event.widget.item(sel[0])['values']
            obecnie_wybrany_klucz = (str(item[1]), str(item[2]).zfill(4))
            
            uwagi_text = str(item[5])
            txt_uwagi.config(state=tk.NORMAL)
            txt_uwagi.delete(1.0, tk.END)
            if uwagi_text.strip() == "OK" or uwagi_text.startswith("OK"):
                txt_uwagi.config(bg="#e8f5e9", fg="#2e7d32")
            elif uwagi_text.startswith("Ostrzeżenie") and "Brak" not in uwagi_text and "Niepełne" not in uwagi_text:
                txt_uwagi.config(bg="#fff3e0", fg="#e65100") 
            else:
                txt_uwagi.config(bg="#ffebee", fg="#b71c1c")
            txt_uwagi.insert(tk.END, uwagi_text)
            txt_uwagi.config(state=tk.DISABLED)
            
            odswiez_logi(obecnie_wybrany_klucz)

        drzewo_anom.bind("<ButtonRelease-1>", lambda e: on_tree_click(e, drzewo_anom))
        drzewo_wszyscy.bind("<ButtonRelease-1>", lambda e: on_tree_click(e, drzewo_wszyscy))
        drzewo_anom.bind('<<TreeviewSelect>>', on_employee_select)
        drzewo_wszyscy.bind('<<TreeviewSelect>>', on_employee_select)

        odswiez_GUI(pokaz_komunikat=False)

        def otworz_mini_edytor(tryb="dodaj", stary_czas_gui="", stary_kod=""):
            if not obecnie_wybrany_klucz: return
            pop = tk.Toplevel(okno)
            pop.title("Edycja zdarzenia")
            pop.geometry("250x180")
            pop.grab_set()

            czysty_czas, czy_nast_dzien = parse_czas_gui(stary_czas_gui)

            tk.Label(pop, text="Godzina (HH:MM):").pack(pady=(10, 0))
            ent_czas = tk.Entry(pop, justify="center")
            ent_czas.insert(0, czysty_czas)
            ent_czas.pack()

            var_nast_dzien = tk.BooleanVar(value=czy_nast_dzien)
            tk.Checkbutton(pop, text="+1 dzień (po północy)", variable=var_nast_dzien).pack(pady=2)

            tk.Label(pop, text="Rodzaj zdarzenia:").pack(pady=(5, 0))
            cb_kod = ttk.Combobox(pop, values=list(KODY_MAPA.values()), state="readonly")
            if stary_kod:
                for v in KODY_MAPA.values():
                    if v.startswith(stary_kod): cb_kod.set(v)
            else: cb_kod.set(list(KODY_MAPA.values())[0])
            cb_kod.pack()

            def zapisz_zmiane():
                n_czas = ent_czas.get().strip()
                if not re.match(r"^([0-1][0-9]|2[0-3]):[0-5][0-9]$", n_czas): 
                    return messagebox.showerror("Błąd", "Zły format czasu! Wpisz HH:MM (00:00 - 23:59)", parent=pop)
                
                g, m = map(int, n_czas.split(':'))
                if var_nast_dzien.get():
                    g += 24
                czas_do_zapisu = f"{g:02d}:{m:02d}"
                
                lista = self.dane_do_zapisu[obecnie_wybrany_klucz]
                if tryb == "dodaj": lista.append({'czas_oryg': czas_do_zapisu, 'czas': czas_do_zapisu, 'kod': cb_kod.get()[:2]})
                elif tryb == "edytuj":
                    idx = drzewo_log.index(drzewo_log.selection()[0])
                    lista[idx].update({'czas_oryg': czas_do_zapisu, 'czas': czas_do_zapisu, 'kod': cb_kod.get()[:2]})
                
                lista.sort(key=lambda x: parse_czas_do_minut(x['czas']))
                odswiez_logi(obecnie_wybrany_klucz)
                pop.destroy()

            tk.Button(pop, text="Zapisz", command=zapisz_zmiane, bg="#4CAF50", fg="white").pack(fill="x", pady=10, padx=20)

        def usun_zdarzenie():
            sel = drzewo_log.selection()
            if not sel or not obecnie_wybrany_klucz: return
            self.dane_do_zapisu[obecnie_wybrany_klucz].pop(drzewo_log.index(sel[0]))
            odswiez_logi(obecnie_wybrany_klucz)

        btn_dodaj.config(command=lambda: otworz_mini_edytor(tryb="dodaj"))
        btn_edytuj.config(command=lambda: otworz_mini_edytor(tryb="edytuj", 
            stary_czas_gui=drzewo_log.item(drzewo_log.selection()[0])['values'][1] if drzewo_log.selection() else "",
            stary_kod=str(drzewo_log.item(drzewo_log.selection()[0])['values'][2])[:2] if drzewo_log.selection() else ""))
        btn_usun.config(command=usun_zdarzenie)

        def finalizuj():
            _, _, linie_rap = self.generuj_raporty()
            okno.destroy()
            self.finalizuj_zapis(self.dane_do_zapisu, path_wynik, path_raport, linie_rap, pokazywac_raport=bool(linie_rap))

        btn_zapisz.config(command=finalizuj)

    def finalizuj_zapis(self, dane_do_zapisu, path_wynik, path_raport, linie_raportu, pokazywac_raport):
        wynikowe_rekordy = []
        for (data, pracownik), zdarzenia in dane_do_zapisu.items():
            for z in zdarzenia:
                godz, minuty = map(int, z['czas'].split(':'))
                if godz >= 24:
                    prawdziwa_godz = godz % 24
                    czas_do_pliku = f"{prawdziwa_godz:02d}:{minuty:02d}"
                    
                    if godz == 24 and minuty == 0:
                        # Zatrzymujemy datę w tym samym dniu dla równej północy!
                        data_do_pliku = data
                    else:
                        dt_prawdziwa = datetime.strptime(data, "%Y.%m.%d") + timedelta(days=godz // 24)
                        data_do_pliku = dt_prawdziwa.strftime("%Y.%m.%d")
                else:
                    czas_do_pliku = z['czas']
                    data_do_pliku = data
                
                wynikowe_rekordy.append({
                    'linia': f"{data_do_pliku}.{czas_do_pliku};{pracownik};{z['kod']}",
                    'data': data_do_pliku, 
                    'pracownik': pracownik, 
                    'czas_sort': z['czas'] 
                })
        
        wynikowe_rekordy.sort(key=lambda x: (x['data'], x['pracownik'], parse_czas_do_minut(x['czas_sort'])))
        output = "\n".join([r['linia'] for r in wynikowe_rekordy]) + "\n"

        with open(path_wynik, 'w', encoding='utf-8') as f: f.write(output)
        msg = f"Utworzono plik z poprawnymi logami:\n{os.path.basename(path_wynik)}"
        
        if pokazywac_raport and linie_raportu:
            with open(path_raport, 'w', encoding='utf-8') as f:
                f.write("--- RAPORT NIEPRAWIDŁOWOŚCI RCP ---\n")
                f.write(f"Zarejestrowano nieprawidłowości u {len(linie_raportu)} osób.\nWykryte braki mogły zostać zignorowane lub ręcznie poprawione.\n\n")
                f.write("\n".join(linie_raportu))
            msg += f"\n\nWygenerowano również log systemowy (raport braków):\n{os.path.basename(path_raport)}"
        messagebox.showinfo("Sukces - Zakończono!", msg)