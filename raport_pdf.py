"""
raport_pdf.py

Raport braków odbić w PDF - pod drukarkę czarno-białą: bez kolorów, rodzaj problemu oznaczony
symbolem (X błąd, ! ostrzeżenie) i krojem pisma (pogrubienie / kursywa), pozycje pogrupowane po działach.
Czcionki z Windows (Segoe UI, Consolas) - są na każdym komputerze z Windows 10/11.
"""
import logging
import os
from collections import OrderedDict
from datetime import datetime

from fpdf import FPDF

logging.getLogger("fontTools").setLevel(logging.ERROR)  # Segoe UI: niegroźne komunikaty przy wycinaniu czcionki

CZCIONKI = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
# Problem + odbicia z dnia, Poprawka = miejsce na ręczny wpis (co wprowadzić w ERP), OK = kratka po wprowadzeniu
KOLUMNY = [("", 6), ("Data", 14), ("Nr", 11), ("Pracownik", 25), ("Zmiana", 16), ("Problem", 66), ("Poprawka", 38), ("OK", 6)]


def _data(d):
    """'2026.10.06' -> '06.10'"""
    return f"{d[8:10]}.{d[5:7]}" if len(d) >= 10 else d


def _zmiana(typ):
    return {"Zmiana 1": "I zmiana", "Zmiana 2": "II zmiana", "godziny ruchome": "ruchome", "---": "-"}.get(typ, typ.replace("Sztywna ", ""))


class _Pdf(FPDF):
    def __init__(self, stopka_lewa):
        super().__init__(format="A4")
        self.stopka_lewa = stopka_lewa
        self.add_font("txt", "", os.path.join(CZCIONKI, "segoeui.ttf"))
        self.add_font("txt", "B", os.path.join(CZCIONKI, "segoeuib.ttf"))
        self.add_font("txt", "I", os.path.join(CZCIONKI, "segoeuii.ttf"))
        self.add_font("mono", "", os.path.join(CZCIONKI, "consola.ttf"))
        self.set_margins(14, 14, 14)
        self.set_auto_page_break(True, 18)
        self.alias_nb_pages()

    def footer(self):
        self.set_y(-13)
        self.set_draw_color(0)
        self.set_line_width(0.2)
        self.line(14, self.get_y(), 196, self.get_y())
        self.set_font("txt", "", 7)
        self.set_text_color(60)
        self.set_y(-12)
        self.cell(150, 4, self.stopka_lewa[:180])
        self.cell(32, 4, f"Strona {self.page_no()} z {{nb}}", align="R")


def zapisz(sciezka, anomalie, statystyki, plik, uzytkownik, wersja, podpisy=False, kratki=True,
           pominiete=(), nazwiska=None, nieobecnosci=(), zakres=""):
    """
    anomalie: lista z interfejs.Api.anomalie (bez nieobecności) - pola data, pracownik, nazwisko, dzial, typ_zmiany, uwaga, rodzaj, status
    pominiete: lista (data, nr) dni wyłączonych z pliku ERP
    """
    pdf = _Pdf(f"Raport braków odbić · {plik}")  # stopka bez reguł - raport trafia też do osób spoza kadr
    pdf.add_page()

    # Nagłówek
    pdf.set_text_color(0)
    pdf.set_font("txt", "B", 17)
    pdf.cell(120, 9, "Raport braków odbić")
    pdf.set_font("txt", "B", 10)
    pdf.cell(62, 5, "DIAMEL", align="R", new_x="LMARGIN", new_y="NEXT")
    y = pdf.get_y()
    pdf.set_font("txt", "", 8)
    pdf.set_text_color(50)
    pdf.set_xy(134, y - 0.5)
    pdf.multi_cell(62, 3.6, f"Korektor Logów HR v{wersja}\nwygenerowano {datetime.now():%d.%m.%Y %H:%M}" + (f" · {uzytkownik}" if uzytkownik else ""), align="R")
    pdf.set_xy(14, y + 4)
    pdf.set_font("txt", "", 9)
    okres = f"Okres {statystyki['od'].replace('.', '-')} – {statystyki['do'].replace('.', '-')}" if statystyki.get("od") else ""
    pdf.cell(120, 5, f"{okres} · plik {plik}")
    pdf.set_y(y + 10)
    pdf.set_line_width(0.7)
    pdf.line(14, pdf.get_y(), 196, pdf.get_y())

    # Liczby
    pdf.ln(3.5)
    y = pdf.get_y()
    pola = [("PRACOWNIKÓW", statystyki["pracownikow"]), ("ZDARZEŃ W PLIKU", statystyki["zdarzen"]),
            ("KOREKT AUTOMATYCZNYCH", statystyki["skorygowane"]), ("DO SPRAWDZENIA", len(anomalie))]
    szer = 182 / len(pola)
    pdf.set_line_width(0.3)
    pdf.rect(14, y, 182, 13)
    for i, (etykieta, wartosc) in enumerate(pola):
        x = 14 + i * szer
        if i:
            pdf.line(x, y, x, y + 13)
        pdf.set_xy(x + 3, y + 1.8)
        pdf.set_font("txt", "", 6.5)
        pdf.set_text_color(70)
        pdf.cell(szer - 6, 3, etykieta)
        pdf.set_xy(x + 3, y + 5.5)
        pdf.set_font("txt", "B", 12)
        pdf.set_text_color(0)
        pdf.cell(szer - 6, 6, f"{wartosc:,}".replace(",", " "))
    pdf.set_y(y + 16)

    # Legenda
    pdf.set_font("txt", "B", 8)
    pdf.cell(4, 4, "X")
    pdf.set_font("txt", "", 8)
    pdf.cell(55, 4, "błąd - wymaga korekty przed importem")
    pdf.set_font("txt", "B", 8)
    pdf.cell(3, 4, "!")
    pdf.set_font("txt", "", 8)
    pdf.cell(40, 4, "ostrzeżenie - do sprawdzenia")
    if kratki:
        pdf.rect(pdf.get_x() + 1, pdf.get_y() + 0.8, 2.6, 2.6)
        pdf.set_x(pdf.get_x() + 5)
        pdf.cell(40, 4, "po wprowadzeniu poprawki w ERP")
    pdf.ln(5)
    if zakres:
        pdf.set_font("txt", "B", 8)
        pdf.cell(0, 4, f"Zakres raportu: {zakres}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("txt", "", 8)
    if nieobecnosci:
        pdf.set_text_color(70)
        pdf.cell(0, 4, f"Nieobecności bez wpisu w planie urlopów: {len(nieobecnosci)} dni - lista na końcu raportu.",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0)

    # Pozycje po działach
    grupy = OrderedDict()
    for a in sorted(anomalie, key=lambda a: (a["dzial"] in ("", "---", "Brak działu"), a["dzial"], a["pracownik"], a["data"])):
        grupy.setdefault(a["dzial"] if a["dzial"] not in ("", "---") else "Bez działu", []).append(a)

    def naglowek_tabeli():
        pdf.set_font("txt", "B", 6.8)
        pdf.set_text_color(0)
        for nazwa, w in KOLUMNY:
            pdf.cell(w, 5, nazwa.upper(), border="B")
        pdf.ln()

    for dzial, pozycje in grupy.items():
        if pdf.get_y() > 255:
            pdf.add_page()
        pdf.ln(3)
        pdf.set_fill_color(228)
        pdf.set_font("txt", "B", 10)
        y = pdf.get_y()
        pdf.cell(182, 6.5, "  " + dzial, fill=True)
        pdf.set_font("txt", "", 8)
        pdf.set_x(14)
        pdf.cell(180, 6.5, f"{len(pozycje)} {'pozycja' if len(pozycje) == 1 else 'pozycje' if 2 <= len(pozycje) % 10 <= 4 and not 12 <= len(pozycje) % 100 <= 14 else 'pozycji'}", align="R")
        pdf.set_fill_color(0)
        pdf.rect(14, y, 1, 6.5, style="F")
        pdf.ln(7.5)
        naglowek_tabeli()
        for i, a in enumerate(pozycje):
            blad = a["rodzaj"] == "blad"
            problem = a["uwaga"].replace("Ostrzeżenie: ", "")
            odbicia = a.get("odbicia") or "brak odbić"
            pdf.set_font("txt", "B" if blad else "I", 8)
            linie = max(1, len(pdf.multi_cell(KOLUMNY[5][1] - 1, 4, problem, align="L", dry_run=True, output="LINES")))
            pdf.set_font("txt", "", 7)
            linie_odb = len(pdf.multi_cell(KOLUMNY[5][1] - 1, 3.3, odbicia, align="L", dry_run=True, output="LINES"))
            h = max(13, 4 * linie + 3.3 * linie_odb + 2)  # min. wysokość: dwie linijki na ręczny wpis
            if pdf.get_y() + h > 279:
                pdf.add_page()
                naglowek_tabeli()
            y = pdf.get_y()
            if i % 2:
                pdf.set_fill_color(244)
                pdf.rect(14, y, 182, h, style="F")
            pdf.set_draw_color(185)
            pdf.set_line_width(0.15)
            pdf.line(14, y + h, 196, y + h)
            pdf.set_draw_color(0)
            x = 14
            komorki = [("txt", "B", 8.5, "X" if blad else "!", "C"), ("mono", "", 7.8, _data(a["data"]), ""),
                       ("mono", "", 7.8, a["pracownik"], ""), ("txt", "", 8, a["nazwisko"], ""),
                       ("txt", "", 8, _zmiana(a["typ_zmiany"]), "")]
            for nr_kol, ((font, styl, rozmiar, tekst, wyr), (_, w)) in enumerate(zip(komorki, KOLUMNY)):
                pdf.set_font(font, styl, rozmiar)
                pdf.set_xy(x, y + 0.8)
                if nr_kol == 3:
                    # Nazwisko w pierwszej linijce, imię (reszta) w drugiej - węższa kolumna, więcej miejsca na problem
                    nazwisko, _, imie = str(tekst).partition(" ")
                    pdf.cell(w, 4, pdf_skroc(pdf, nazwisko, w - 1))
                    pdf.set_xy(x, y + 4.6)
                    pdf.cell(w, 4, pdf_skroc(pdf, imie, w - 1))
                else:
                    pdf.cell(w, 4, pdf_skroc(pdf, tekst, w - 1), align=wyr or "L")
                x += w
            pdf.set_font("txt", "B" if blad else "I", 8)
            pdf.set_xy(x, y + 0.8)
            pdf.multi_cell(KOLUMNY[5][1] - 1, 4, problem, align="L")
            pdf.set_font("txt", "", 7)
            pdf.set_text_color(40)
            pdf.set_x(x)
            pdf.multi_cell(KOLUMNY[5][1] - 1, 3.3, odbicia, align="L")
            pdf.set_text_color(0)
            x += KOLUMNY[5][1]
            pdf.set_draw_color(150)
            pdf.set_line_width(0.2)
            pdf.set_dash_pattern(dash=0.8, gap=0.8)
            for linia in (y + h - 7, y + h - 2):
                pdf.line(x + 1, linia, x + KOLUMNY[6][1] - 2, linia)
            pdf.set_dash_pattern()
            pdf.set_draw_color(0)
            x += KOLUMNY[6][1]
            if kratki:
                pdf.set_line_width(0.25)
                pdf.rect(x + 1.2, y + 1.4, 2.8, 2.8)
                if a.get("status"):
                    pdf.set_font("txt", "B", 7)
                    pdf.set_xy(x + 1.2, y + 1.1)
                    pdf.cell(2.8, 3.4, "v", align="C")
            pdf.set_xy(14, y + h)

    if not anomalie:
        pdf.ln(6)
        pdf.set_font("txt", "B", 11)
        pdf.cell(0, 8, "Brak pozycji do sprawdzenia.", new_x="LMARGIN", new_y="NEXT")

    if pominiete:
        nazwiska = nazwiska or {}
        pdf.ln(5)
        pdf.set_font("txt", "B", 10)
        pdf.cell(0, 6, "Pominięte w pliku ERP (niepoprawione błędy)", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("txt", "", 8)
        for d, nr in pominiete:
            pdf.cell(0, 4.4, f"{_data(d)}.{d[:4]}   {nr}   {nazwiska.get(nr, '---')}", new_x="LMARGIN", new_y="NEXT")

    if nieobecnosci:
        # Jeden wiersz na pracownika: numer, nazwisko, dział i dni bez odbić
        osoby = OrderedDict()
        for a in sorted(nieobecnosci, key=lambda a: (a["dzial"], a["pracownik"], a["data"])):
            osoby.setdefault((a["pracownik"], a["nazwisko"], a["dzial"]), []).append(_data(a["data"]))
        if pdf.get_y() > 250:
            pdf.add_page()
        pdf.ln(5)
        pdf.set_font("txt", "B", 10)
        pdf.cell(0, 6, f"Nieobecności bez wpisu w planie urlopów ({len(nieobecnosci)} dni)", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("txt", "", 7.5)
        pdf.set_text_color(60)
        pdf.cell(0, 4, "Dni robocze bez żadnego odbicia. Wczytanie planu nieobecności (Excel) usuwa z listy dni urlopów.", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0)
        pdf.ln(1)
        for (nr, nazwisko, dzial), dni in osoby.items():
            if pdf.get_y() > 272:
                pdf.add_page()
            y = pdf.get_y()
            pdf.set_font("mono", "", 7.8)
            pdf.cell(11, 4.2, nr)
            pdf.set_font("txt", "B", 8)
            pdf.cell(46, 4.2, pdf_skroc(pdf, nazwisko, 45))
            pdf.set_font("txt", "", 7.5)
            pdf.set_text_color(60)
            pdf.cell(38, 4.2, pdf_skroc(pdf, dzial, 37))
            pdf.set_text_color(0)
            pdf.set_font("txt", "", 8)
            pdf.multi_cell(87, 4.2, ", ".join(dni), align="L", new_x="LMARGIN", new_y="NEXT")
            pdf.set_draw_color(205)
            pdf.set_line_width(0.15)
            pdf.line(14, pdf.get_y() + 0.4, 196, pdf.get_y() + 0.4)
            pdf.set_draw_color(0)
            pdf.ln(1)

    if podpisy:
        if pdf.get_y() > 250:
            pdf.add_page()
        pdf.ln(18)
        y = pdf.get_y()
        pdf.set_line_width(0.3)
        pdf.line(14, y, 92, y)
        pdf.line(118, y, 196, y)
        pdf.set_font("txt", "", 8)
        pdf.set_text_color(50)
        pdf.set_xy(14, y + 1)
        pdf.cell(78, 4, "Sprawdził(a) - data i podpis")
        pdf.set_xy(118, y + 1)
        pdf.cell(78, 4, "Zatwierdził(a) - data i podpis")

    pdf.output(sciezka)
    return sciezka


def pdf_skroc(pdf, tekst, szerokosc):
    """Przycina tekst do szerokości komórki (długie nazwiska)."""
    tekst = str(tekst or "")
    if pdf.get_string_width(tekst) <= szerokosc:
        return tekst
    while tekst and pdf.get_string_width(tekst + "…") > szerokosc:
        tekst = tekst[:-1]
    return tekst + "…"
