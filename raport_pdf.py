"""
raport_pdf.py

Raport braków odbić w PDF - pod drukarkę czarno-białą: bez kolorów, rodzaj problemu oznaczony
symbolem (X błąd, ! ostrzeżenie) i krojem pisma (pogrubienie / kursywa), pozycje pogrupowane po działach.
Kolumny Poprawka i OK to pola formularza - raport można wypełnić na komputerze (Edge, Acrobat) albo wydrukować.
Czcionki z Windows (Segoe UI, Consolas) - są na każdym komputerze z Windows 10/11.
"""
import io
import logging
import os
from collections import OrderedDict
from datetime import datetime

from fpdf import FPDF
from pypdf import PdfWriter
from pypdf.generic import ArrayObject, BooleanObject, DecodedStreamObject, DictionaryObject, FloatObject, NameObject, NumberObject, TextStringObject

logging.getLogger("fontTools").setLevel(logging.ERROR)  # Segoe UI: niegroźne komunikaty przy wycinaniu czcionki

CZCIONKI = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
# Problem + odbicia z dnia, Poprawka = miejsce na ręczny wpis (co wprowadzić w ERP), OK = kratka po wprowadzeniu
# A4 poziomo: szerokość treści SZER, prawa krawędź PRAWA, dół treści DOL (nad stopką) - więcej miejsca na opis i poprawkę
SZER, PRAWA, DOL = 269, 283, 192
KOLUMNY = [("", 7), ("Data", 17), ("Nr", 13), ("Pracownik", 38), ("Zmiana", 21), ("Problem", 85), ("Poprawka", 80), ("OK", 8)]


def _data(d):
    """'2026.10.06' -> '06.10'"""
    return f"{d[8:10]}.{d[5:7]}" if len(d) >= 10 else d


def _zmiana(typ):
    return {"Zmiana 1": "I zmiana", "Zmiana 2": "II zmiana", "godziny ruchome": "ruchome", "---": "-"}.get(typ, typ.replace("Sztywna ", ""))


class _Pdf(FPDF):
    def __init__(self, stopka_lewa):
        super().__init__(orientation="L", format="A4")
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
        self.line(14, self.get_y(), PRAWA, self.get_y())
        self.set_font("txt", "", 7.5)
        self.set_text_color(60)
        self.set_y(-12)
        self.cell(SZER - 40, 4, self.stopka_lewa[:220])
        self.cell(40, 4, f"Strona {self.page_no()} z {{nb}}", align="R")


def zapisz(sciezka, anomalie, statystyki, plik, uzytkownik, wersja, podpisy=False, kratki=True,
           pominiete=(), nazwiska=None, nieobecnosci=(), zakres=""):
    """
    anomalie: lista z interfejs.Api.anomalie (bez nieobecności) - pola data, pracownik, nazwisko, dzial, typ_zmiany, uwaga, rodzaj, status
    pominiete: lista (data, nr) dni wyłączonych z pliku ERP
    """
    pola_formularza = []  # pola formularza dodawane po zapisie (dodaj_pola)
    pdf = _Pdf(f"Raport braków odbić · {plik}")  # stopka bez reguł - raport trafia też do osób spoza kadr
    pdf.add_page()

    # Nagłówek
    pdf.set_text_color(0)
    pdf.set_font("txt", "B", 19)
    pdf.cell(SZER - 70, 9, "Raport braków odbić")
    pdf.set_font("txt", "B", 11)
    pdf.cell(70, 5, "DIAMEL", align="R", new_x="LMARGIN", new_y="NEXT")
    y = pdf.get_y()
    pdf.set_font("txt", "", 8.5)
    pdf.set_text_color(50)
    pdf.set_xy(PRAWA - 70, y - 0.5)
    pdf.multi_cell(70, 3.9, f"Korektor Logów HR v{wersja}\nwygenerowano {datetime.now():%d.%m.%Y %H:%M}" + (f" · {uzytkownik}" if uzytkownik else ""), align="R")
    pdf.set_xy(14, y + 4)
    pdf.set_font("txt", "", 10)
    okres = f"Okres {statystyki['od'].replace('.', '-')} – {statystyki['do'].replace('.', '-')}" if statystyki.get("od") else ""
    pdf.cell(SZER - 75, 5, f"{okres} · plik {plik}")
    pdf.set_y(y + 10)
    pdf.set_line_width(0.7)
    pdf.line(14, pdf.get_y(), PRAWA, pdf.get_y())

    # Liczby
    pdf.ln(3.5)
    y = pdf.get_y()
    pola = [("PRACOWNIKÓW", statystyki["pracownikow"]), ("ZDARZEŃ W PLIKU", statystyki["zdarzen"]),
            ("KOREKT AUTOMATYCZNYCH", statystyki["skorygowane"]), ("DO SPRAWDZENIA", len(anomalie))]
    szer = SZER / len(pola)
    pdf.set_line_width(0.3)
    pdf.rect(14, y, SZER, 13)
    for i, (etykieta, wartosc) in enumerate(pola):
        x = 14 + i * szer
        if i:
            pdf.line(x, y, x, y + 13)
        pdf.set_xy(x + 3, y + 1.8)
        pdf.set_font("txt", "", 7)
        pdf.set_text_color(70)
        pdf.cell(szer - 6, 3, etykieta)
        pdf.set_xy(x + 3, y + 5.5)
        pdf.set_font("txt", "B", 13)
        pdf.set_text_color(0)
        pdf.cell(szer - 6, 6, f"{wartosc:,}".replace(",", " "))
    pdf.set_y(y + 16)

    # Legenda
    pdf.set_font("txt", "B", 9)
    pdf.cell(4, 4.5, "X")
    pdf.set_font("txt", "", 9)
    pdf.cell(64, 4.5, "błąd - wymaga korekty przed importem")
    pdf.set_font("txt", "B", 9)
    pdf.cell(3, 4.5, "!")
    pdf.set_font("txt", "", 9)
    pdf.cell(48, 4.5, "ostrzeżenie - do sprawdzenia")
    if kratki:
        pdf.rect(pdf.get_x() + 1, pdf.get_y() + 0.8, 2.6, 2.6)
        pdf.set_x(pdf.get_x() + 5)
        pdf.cell(40, 4, "po wprowadzeniu poprawki w ERP")
    pdf.ln(5)
    pdf.set_text_color(70)
    pdf.cell(0, 4, "Poprawkę i OK można wpisać na komputerze (np. w Edge: kliknij w pole, potem zapisz plik) albo ręcznie po wydruku.",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0)
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
        pdf.set_font("txt", "B", 7.5)
        pdf.set_text_color(0)
        for nazwa, w in KOLUMNY:
            pdf.cell(w, 5.5, nazwa.upper(), border="B")
        pdf.ln()

    for dzial, pozycje in grupy.items():
        if pdf.get_y() > DOL - 26:
            pdf.add_page()
        pdf.ln(3)
        pdf.set_fill_color(228)
        pdf.set_font("txt", "B", 11)
        y = pdf.get_y()
        pdf.cell(SZER, 7, "  " + dzial, fill=True)
        pdf.set_font("txt", "", 9)
        pdf.set_x(14)
        pdf.cell(SZER - 2, 7, f"{len(pozycje)} {'pozycja' if len(pozycje) == 1 else 'pozycje' if 2 <= len(pozycje) % 10 <= 4 and not 12 <= len(pozycje) % 100 <= 14 else 'pozycji'}", align="R")
        pdf.set_fill_color(0)
        pdf.rect(14, y, 1, 7, style="F")
        pdf.ln(8)
        naglowek_tabeli()
        for i, a in enumerate(pozycje):
            blad = a["rodzaj"] == "blad"
            problem = a["uwaga"].replace("Ostrzeżenie: ", "")
            odbicia = a.get("odbicia") or "brak odbić"
            pdf.set_font("txt", "B" if blad else "I", 9)
            linie = max(1, len(pdf.multi_cell(KOLUMNY[5][1] - 1, 4.5, problem, align="L", dry_run=True, output="LINES")))
            pdf.set_font("txt", "", 8)
            linie_odb = len(pdf.multi_cell(KOLUMNY[5][1] - 1, 3.8, odbicia, align="L", dry_run=True, output="LINES"))
            h = max(15, 4.5 * linie + 3.8 * linie_odb + 2)  # min. wysokość: trzy linijki na ręczny wpis
            if pdf.get_y() + h > DOL:
                pdf.add_page()
                naglowek_tabeli()
            y = pdf.get_y()
            if i % 2:
                pdf.set_fill_color(244)
                pdf.rect(14, y, SZER, h, style="F")
            pdf.set_draw_color(185)
            pdf.set_line_width(0.15)
            pdf.line(14, y + h, PRAWA, y + h)
            pdf.set_draw_color(0)
            x = 14
            komorki = [("txt", "B", 9.5, "X" if blad else "!", "C"), ("mono", "", 8.8, _data(a["data"]), ""),
                       ("mono", "", 8.8, a["pracownik"], ""), ("txt", "", 9, a["nazwisko"], ""),
                       ("txt", "", 9, _zmiana(a["typ_zmiany"]), "")]
            for nr_kol, ((font, styl, rozmiar, tekst, wyr), (_, w)) in enumerate(zip(komorki, KOLUMNY)):
                pdf.set_font(font, styl, rozmiar)
                pdf.set_xy(x, y + 0.8)
                if nr_kol == 3:
                    # Nazwisko w pierwszej linijce, imię (reszta) w drugiej - węższa kolumna, więcej miejsca na problem
                    nazwisko, _, imie = str(tekst).partition(" ")
                    pdf.cell(w, 4.5, pdf_skroc(pdf, nazwisko, w - 1))
                    pdf.set_xy(x, y + 5.1)
                    pdf.cell(w, 4.5, pdf_skroc(pdf, imie, w - 1))
                else:
                    pdf.cell(w, 4.5, pdf_skroc(pdf, tekst, w - 1), align=wyr or "L")
                x += w
            pdf.set_font("txt", "B" if blad else "I", 9)
            pdf.set_xy(x, y + 0.8)
            pdf.multi_cell(KOLUMNY[5][1] - 1, 4.5, problem, align="L")
            pdf.set_font("txt", "", 8)
            pdf.set_text_color(40)
            pdf.set_x(x)
            pdf.multi_cell(KOLUMNY[5][1] - 1, 3.8, odbicia, align="L")
            pdf.set_text_color(0)
            x += KOLUMNY[5][1]
            # Ramka na poprawkę: do wpisania na komputerze (pole formularza) albo ręcznie po wydruku
            pdf.set_draw_color(170)
            pdf.set_line_width(0.2)
            pdf.rect(x + 0.6, y + 0.6, KOLUMNY[6][1] - 1.6, h - 1.2)
            pdf.set_draw_color(0)
            pola_formularza.append({"typ": "tekst", "strona": pdf.page_no(), "x": x + 0.6, "y": y + 0.6, "w": KOLUMNY[6][1] - 1.6, "h": h - 1.2,
                         "nazwa": f"poprawka_{len(pola_formularza)}", "opis": f"Poprawka: {a['pracownik']} {_data(a['data'])}"})
            x += KOLUMNY[6][1]
            if kratki:
                pdf.set_line_width(0.25)
                pdf.rect(x + 1.6, y + 1.4, 3.6, 3.6)
                pola_formularza.append({"typ": "kratka", "strona": pdf.page_no(), "x": x + 1.6, "y": y + 1.4, "w": 3.6, "h": 3.6,
                             "nazwa": f"ok_{len(pola_formularza)}", "zaznaczone": bool(a.get("status")), "opis": f"OK: {a['pracownik']} {_data(a['data'])}"})
            pdf.set_xy(14, y + h)

    if not anomalie:
        pdf.ln(6)
        pdf.set_font("txt", "B", 11)
        pdf.cell(0, 8, "Brak pozycji do sprawdzenia.", new_x="LMARGIN", new_y="NEXT")

    if pominiete:
        nazwiska = nazwiska or {}
        pdf.ln(5)
        pdf.set_font("txt", "B", 11)
        pdf.cell(0, 6, "Pominięte w pliku ERP (niepoprawione błędy)", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("txt", "", 9)
        for d, nr in pominiete:
            pdf.cell(0, 4.8, f"{_data(d)}.{d[:4]}   {nr}   {nazwiska.get(nr, '---')}", new_x="LMARGIN", new_y="NEXT")

    if nieobecnosci:
        # Pracownik (numer, nazwisko, dział), pod nim jego dni bez odbić - każdy dzień z polem na wpis (np. powód, kod
        # nieobecności) na całą szerokość i kratką do odhaczenia po wprowadzeniu w ERP; każdy dzień w osobnym wierszu
        osoby = OrderedDict()
        for a in sorted(nieobecnosci, key=lambda a: (a["dzial"], a["pracownik"], a["data"])):
            osoby.setdefault((a["pracownik"], a["nazwisko"], a["dzial"]), []).append(a)
        if pdf.get_y() > DOL - 34:
            pdf.add_page()
        pdf.ln(5)
        pdf.set_font("txt", "B", 11)
        pdf.cell(0, 6, f"Nieobecności bez wpisu w planie urlopów ({len(nieobecnosci)} dni)", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("txt", "", 8.5)
        pdf.set_text_color(60)
        pdf.cell(0, 4.5, "Dni robocze bez żadnego odbicia. Przy każdym dniu: pole na wpis (np. powód, kod nieobecności) i kratka"
                       + (" do odhaczenia." if kratki else "."), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0)
        pdf.ln(1)
        kol, szer_kol, h_dnia = 1, SZER, 7.5
        for (nr, nazwisko, dzial), dni in osoby.items():
            wiersze = -(-len(dni) // kol)
            if pdf.get_y() + 6 + min(wiersze, 2) * h_dnia > DOL:
                pdf.add_page()
            y = pdf.get_y()
            pdf.set_fill_color(236)
            pdf.rect(14, y, SZER, 5.8, style="F")
            pdf.set_xy(15, y + 0.6)
            pdf.set_font("mono", "", 8.8)
            pdf.cell(13, 4.6, nr)
            pdf.set_font("txt", "B", 9)
            pdf.cell(80, 4.6, pdf_skroc(pdf, nazwisko, 79))
            pdf.set_font("txt", "", 8.5)
            pdf.set_text_color(60)
            pdf.cell(120, 4.6, pdf_skroc(pdf, dzial, 119))
            pdf.cell(SZER - 215, 4.6, f"{len(dni)} {'dzień' if len(dni) == 1 else 'dni'}", align="R")
            pdf.set_text_color(0)
            pdf.set_y(y + 6.4)
            for w in range(wiersze):
                if pdf.get_y() + h_dnia > DOL:
                    pdf.add_page()
                y = pdf.get_y()
                for k, a in enumerate(dni[w * kol:(w + 1) * kol]):
                    x = 14 + k * szer_kol
                    pdf.set_font("mono", "", 8.6)
                    pdf.set_xy(x + 1, y + 1.3)
                    dt = datetime.strptime(a["data"], "%Y.%m.%d")
                    pdf.cell(20, 4.5, f"{_data(a['data'])} {['pn', 'wt', 'śr', 'cz', 'pt', 'so', 'nd'][dt.weekday()]}")
                    xp, wp = x + 22, szer_kol - (31 if kratki else 23)
                    pdf.set_draw_color(170)
                    pdf.set_line_width(0.2)
                    pdf.rect(xp, y + 0.6, wp, h_dnia - 1.2)
                    pdf.set_draw_color(0)
                    pola_formularza.append({"typ": "tekst", "strona": pdf.page_no(), "x": xp, "y": y + 0.6, "w": wp, "h": h_dnia - 1.2,
                                            "nazwa": f"nieob_{len(pola_formularza)}", "opis": f"Nieobecność: {nr} {_data(a['data'])}"})
                    if kratki:
                        xk = xp + wp + 3.5
                        pdf.set_line_width(0.25)
                        pdf.rect(xk, y + 1.9, 3.6, 3.6)
                        pola_formularza.append({"typ": "kratka", "strona": pdf.page_no(), "x": xk, "y": y + 1.9, "w": 3.6, "h": 3.6,
                                                "nazwa": f"nieob_ok_{len(pola_formularza)}", "zaznaczone": bool(a.get("status")),
                                                "opis": f"OK nieobecność: {nr} {_data(a['data'])}"})
                pdf.set_y(y + h_dnia)
            pdf.set_draw_color(205)
            pdf.set_line_width(0.15)
            pdf.line(14, pdf.get_y() + 0.6, PRAWA, pdf.get_y() + 0.6)
            pdf.set_draw_color(0)
            pdf.ln(2)

    if podpisy:
        if pdf.get_y() > DOL - 28:
            pdf.add_page()
        pdf.ln(18)
        y = pdf.get_y()
        pdf.set_line_width(0.3)
        pdf.line(14, y, 120, y)
        pdf.line(PRAWA - 106, y, PRAWA, y)
        pdf.set_font("txt", "", 8)
        pdf.set_text_color(50)
        pdf.set_xy(14, y + 1)
        pdf.cell(106, 4, "Sprawdził(a) - data i podpis")
        pdf.set_xy(PRAWA - 106, y + 1)
        pdf.cell(106, 4, "Zatwierdził(a) - data i podpis")

    pdf.output(sciezka)
    dodaj_pola(sciezka, pola_formularza)
    return sciezka


def dodaj_pola(sciezka, pola):
    """
    Pola formularza w gotowym PDF (fpdf2 ich nie tworzy): tekst wielowierszowy w kolumnie Poprawka, pole wyboru w kolumnie OK.
    Współrzędne pól w mm od lewego górnego rogu strony A4 (jak w fpdf2) - PDF liczy w punktach od dołu.
    """
    if not pola:
        return
    pt = 72 / 25.4
    with open(sciezka, "rb") as f:
        w = PdfWriter(clone_from=io.BytesIO(f.read()))  # z pamięci - ten sam plik jest potem nadpisywany
    helv = w._add_object(DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                                           NameObject("/BaseFont"): NameObject("/Helvetica"), NameObject("/Encoding"): NameObject("/WinAnsiEncoding")}))
    zadb = w._add_object(DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                                           NameObject("/BaseFont"): NameObject("/ZapfDingbats")}))

    def wyglad(szer, wys, tresc):
        s = DecodedStreamObject()
        s.set_data(tresc)
        s.update({NameObject("/Type"): NameObject("/XObject"), NameObject("/Subtype"): NameObject("/Form"),
                  NameObject("/BBox"): ArrayObject([FloatObject(0), FloatObject(0), FloatObject(szer), FloatObject(wys)]),
                  NameObject("/Resources"): DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/ZaDb"): zadb})})})
        return w._add_object(s)

    pola_pdf = ArrayObject()
    for p in pola:
        strona = w.pages[p["strona"] - 1]
        wys_strony = float(strona.mediabox.height)
        x0, y1 = p["x"] * pt, wys_strony - p["y"] * pt
        x1, y0 = x0 + p["w"] * pt, y1 - p["h"] * pt
        pole = DictionaryObject({NameObject("/Type"): NameObject("/Annot"), NameObject("/Subtype"): NameObject("/Widget"),
                                 NameObject("/T"): TextStringObject(p["nazwa"]), NameObject("/TU"): TextStringObject(p["opis"]),
                                 NameObject("/Rect"): ArrayObject([FloatObject(round(v, 2)) for v in (x0, y0, x1, y1)]),
                                 NameObject("/F"): NumberObject(4), NameObject("/P"): strona.indirect_reference})
        if p["typ"] == "tekst":
            pole.update({NameObject("/FT"): NameObject("/Tx"), NameObject("/Ff"): NumberObject(4096),  # wielowierszowe
                         NameObject("/DA"): TextStringObject("/Helv 10 Tf 0 g"), NameObject("/V"): TextStringObject(""),
                         NameObject("/MK"): DictionaryObject()})
        else:
            szer, wys = x1 - x0, y1 - y0
            stan = NameObject("/Tak" if p["zaznaczone"] else "/Off")
            pole.update({NameObject("/FT"): NameObject("/Btn"), NameObject("/V"): stan, NameObject("/AS"): stan,
                         NameObject("/DA"): TextStringObject("/ZaDb 0 Tf 0 g"),
                         NameObject("/MK"): DictionaryObject({NameObject("/CA"): TextStringObject("4")}),
                         NameObject("/AP"): DictionaryObject({NameObject("/N"): DictionaryObject({
                             NameObject("/Tak"): wyglad(szer, wys, f"q 0 g BT /ZaDb {wys * 0.9:.2f} Tf {szer * 0.1:.2f} {wys * 0.18:.2f} Td (4) Tj ET Q".encode()),
                             NameObject("/Off"): wyglad(szer, wys, b"")})})})
        ref = w._add_object(pole)
        if "/Annots" not in strona:
            strona[NameObject("/Annots")] = ArrayObject()
        strona["/Annots"].append(ref)
        pola_pdf.append(ref)
    w._root_object[NameObject("/AcroForm")] = DictionaryObject({
        NameObject("/Fields"): pola_pdf, NameObject("/NeedAppearances"): BooleanObject(True),
        NameObject("/DA"): TextStringObject("/Helv 10 Tf 0 g"),
        NameObject("/DR"): DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/Helv"): helv, NameObject("/ZaDb"): zadb})})})
    w.write(sciezka)


def pdf_skroc(pdf, tekst, szerokosc):
    """Przycina tekst do szerokości komórki (długie nazwiska)."""
    tekst = str(tekst or "")
    if pdf.get_string_width(tekst) <= szerokosc:
        return tekst
    while tekst and pdf.get_string_width(tekst + "…") > szerokosc:
        tekst = tekst[:-1]
    return tekst + "…"
