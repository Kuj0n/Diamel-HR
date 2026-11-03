"""
Test zgodności obliczeń: przetwarza pliki RCP z testy/dane_prywatne/ tak jak program (bez okien)
i porównuje wynik z plikami zapisanymi przez wersję wzorcową (*_poprawione_1.txt, *_RAPORT_BRAKOW_1.txt).

W folderze testy/dane_prywatne/ (poza repozytorium - dane osobowe):
  - pliki RCP:        <nazwa>.txt  + wzorce <nazwa>_poprawione_1.txt i <nazwa>_RAPORT_BRAKOW_1.txt
  - ustawienia:       settings_v*.json (z folderu programu, zapisane przy generowaniu wzorców)
  - lista pracowników: pracownicy_*.txt (panel HR -> Kopie -> Pobierz kopię)

Użycie: python testy/porownaj_wyniki.py      (kod wyjścia 0 = wyniki identyczne)
Wypisuje tylko liczby i numery linii - bez nazwisk pracowników.
"""
import glob
import os
import re
import shutil
import sys
import tempfile
import tkinter as tk

KATALOG_HR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DANE = os.path.join(KATALOG_HR, "testy", "dane_prywatne")
sys.path.insert(0, KATALOG_HR)

ZMIANY = {"7h": "pracownicy_7h", "6-14": "pracownicy_6_14", "13-21": "pracownicy_13_21", "8-16": "pracownicy_8_16", "16-24": "pracownicy_16_24"}


def dane_z_kopii_panelu(sciezka):
    """Kopia z panelu HR (format zakładki Import) -> dane w formacie API /api/hr.php (akcja 'dane')."""
    pracownicy, dzialy, ignorowani = {}, {}, []
    listy = {k: [] for k in ZMIANY.values()}
    for linia in open(sciezka, encoding="utf-8-sig").read().splitlines():
        pola = linia.split(";")
        if len(pola) < 5:
            continue
        nr, nazwisko, dzial, zmiany, status = pola[:5]
        pracownicy[nr] = nazwisko
        if dzial:
            dzialy[nr] = dzial
        for z in filter(None, zmiany.split("+")):
            listy[ZMIANY[z]].append(nr)
        if status == "nie pracuje":
            ignorowani.append(nr)
    return {"pracownicy": pracownicy, "dzialy": dzialy, "listy": {k: ", ".join(v) for k, v in listy.items()}, "ignorowani": ", ".join(ignorowani)}


def porownaj(nazwa, wzorzec, wynik, dowolna_kolejnosc=False):
    a = open(wzorzec, encoding="utf-8").read().splitlines()
    b = open(wynik, encoding="utf-8").read().splitlines()
    if a == b:
        print(f"  OK    {nazwa}: identyczne ({len(a)} linii)")
        return True
    if dowolna_kolejnosc and sorted(a) == sorted(b):
        # Wersja 3.1.2 układa raport w przypadkowej kolejności (zbiór pracowników) - liczy się treść
        print(f"  OK    {nazwa}: ta sama treść ({len(a)} linii), inna kolejność linii")
        return True
    rozne = [i for i in range(max(len(a), len(b))) if (a[i] if i < len(a) else None) != (b[i] if i < len(b) else None)]
    print(f"  RÓŻNE {nazwa}: wzorzec {len(a)} linii, wynik {len(b)} linii, różnych pozycji {len(rozne)} (pierwsze linie: {[i + 1 for i in rozne[:10]]})")
    return False


def main():
    import gui
    ustawienia = sorted(glob.glob(os.path.join(DANE, "settings_v*.json")))
    kopie = sorted(glob.glob(os.path.join(DANE, "pracownicy_*.txt")))
    zrodla = [p for p in sorted(glob.glob(os.path.join(DANE, "*.txt"))) if not re.search(r"_(poprawione|RAPORT_BRAKOW)_\d+\.txt$|pracownicy_", p)]
    if not (ustawienia and kopie and zrodla):
        sys.exit(f"Brak danych w {DANE}: potrzebne settings_v*.json, pracownicy_*.txt i pliki RCP")

    dane = dane_z_kopii_panelu(kopie[-1])
    gui.sprawdz_aktualizacje_przed_startem = lambda root: None
    gui.pobierz_dane_pracownikow = lambda root: dane
    gui.messagebox.showinfo = gui.messagebox.showwarning = lambda *a, **k: None
    gui.messagebox.showerror = lambda tytul, tresc, **k: print("  BŁĄD PROGRAMU:", tytul, "\n", tresc)

    def zapis_bez_menedzera(self, path_wynik, path_raport):
        # Jak przycisk "ZATWIERDŹ WSZYSTKIE POPRAWKI" w Menedżerze danych, bez ręcznych zmian
        _, _, linie = self.generuj_raporty()
        self.finalizuj_zapis(self.dane_do_zapisu, path_wynik, path_raport, linie, pokazywac_raport=bool(linie))
    gui.AppHR.otworz_menedzer_korekt = zapis_bez_menedzera

    wszystko_ok = True
    roboczy = tempfile.mkdtemp(prefix="hr_test_")
    try:
        shutil.copy(ustawienia[-1], os.path.join(roboczy, gui.CONFIG_FILE))
        os.chdir(roboczy)  # program czyta i zapisuje ustawienia w bieżącym folderze
        print(f"Wersja programu {gui.VERSION} | ustawienia {os.path.basename(ustawienia[-1])} | pracownicy z {os.path.basename(kopie[-1])}")
        for zrodlo in zrodla:
            nazwa = os.path.splitext(os.path.basename(zrodlo))[0]
            print(f"\n{nazwa}")
            kopia = os.path.join(roboczy, os.path.basename(zrodlo))
            shutil.copy(zrodlo, kopia)
            root = tk.Tk()
            root.withdraw()
            app = gui.AppHR(root)
            root.withdraw()
            app.plik_sciezka = kopia
            with open(kopia, encoding="utf-8") as f:
                app.dane_zaladowane = f.readlines()
            app.procesuj()
            root.destroy()
            for rodzaj in ("poprawione", "RAPORT_BRAKOW"):
                wzorzec = os.path.join(DANE, f"{nazwa}_{rodzaj}_1.txt")
                wynik = os.path.join(roboczy, f"{nazwa}_{rodzaj}_1.txt")
                if not os.path.exists(wynik):
                    print(f"  BRAK  {rodzaj}: program nie zapisał pliku")
                    wszystko_ok = False
                elif os.path.exists(wzorzec):
                    wszystko_ok &= porownaj(rodzaj, wzorzec, wynik, dowolna_kolejnosc=(rodzaj == "RAPORT_BRAKOW"))
    finally:
        os.chdir(KATALOG_HR)
        shutil.rmtree(roboczy, ignore_errors=True)
    print("\nWYNIK:", "wszystkie pliki identyczne ze wzorcem" if wszystko_ok else "są różnice")
    return 0 if wszystko_ok else 1


if __name__ == "__main__":
    sys.exit(main())
