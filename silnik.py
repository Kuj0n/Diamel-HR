"""
silnik.py

Obliczenia Korektora Logów HR bez interfejsu: wczytanie zdarzeń RCP, korekty, raport braków, plik dla ERP.
Kod metod przeniesiony 1:1 z gui.py wersji 3.1.2 (zamiast pól okna czyta ustawienia ze słownika self.u).
Zgodność z wersją 3.1.2 sprawdza testy/porownaj_wyniki.py.
"""
from datetime import datetime, timedelta
import os
import re

from obliczenia import parse_czas_do_minut, formatuj_minuty_do_czasu, zaokraglij_czas, oblicz_roznice_minut
from kalendarz import czy_dzien_roboczy

# Wartości domyślne - jak w load_settings() wersji 3.1.2
DOMYSLNE = {
    "z1_od": "05:00", "z1_do": "06:30", "z2_od": "13:00", "z2_do": "14:30",
    "chk_flex": True, "chk_ochrona": True, "chk_raport": True,
    "chk_wej": True, "wej_kierunek": "dół", "wej_minuty": "5", "wej_tol": "2",
    "chk_zmiana1": True, "zmiana1_czas": "05:00", "chk_zmiana2": True, "zmiana2_czas": "13:00",
    "chk_wyj": True, "wyj_kierunek": "dół", "wyj_minuty": "5", "wyj_tol": "2",
    "chk_duplikaty": True, "dup_wej_min": "10", "dup_wyj_min": "10",
    "chk_pomylki": True, "pomylki_min": "10",
    "chk_midnight": True, "chk_ostrzegaj_polnoc": True, "midnight_limit": "05:00",
    "chk_usun_18": True, "chk_przepustka": True,
    "chk_nadgodziny": True, "nadgodziny_min": "30", "chk_nadgodziny_skok": True, "nadgodziny_skok_min": "30",
    "chk_nadgodziny_wyjatek": True,
    "dzialy_wyjatek": "Dział Administracji, Dział Kadr i Płac, Dział Konstrukcyjny, Dział Kontroli Jakości, Dział Księgowości, Dział Serwisu, Dział Zaopatrzenia",
    "nadgodziny_wyjatek_min": "10", "nadgodziny_wyjatek_skok_min": "0",
    "pracownicy_ignorowani": "0019, 0018, 0022, 0033, 0076, 0044, 0005, 0069, 0029, 0093, 0021",
    "pracownicy_7h": "0232,0212", "pracownicy_6_14": "0100,0205", "pracownicy_13_21": "0100,0205",
    "pracownicy_8_16": "0235", "pracownicy_16_24": "",
}
LISTY_ZMIAN = ("pracownicy_7h", "pracownicy_6_14", "pracownicy_13_21", "pracownicy_8_16", "pracownicy_16_24")


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


class Silnik:
    def __init__(self, ustawienia=None, dane_serwera=None, baza_urlopow=None):
        """
        ustawienia: słownik jak plik settings_v*.json (brakujące klucze = DOMYSLNE)
        dane_serwera: odpowiedź API HR (pracownicy, dzialy, listy, ignorowani) albo None
        baza_urlopow: {nr: zbiór dat 'RRRR.MM.DD'} z planu nieobecności
        """
        dane_serwera = dane_serwera or {}
        self.u = {**DOMYSLNE, **(ustawienia or {})}
        self.baza_pracownikow = dane_serwera.get("pracownicy", {})
        self.baza_dzialow = dane_serwera.get("dzialy", {})
        # Okres sprawdzania z panelu: {nr: {od, do}} (RRRR.MM.DD) - nowy pracownik sprawdzany od "od", odchodzący do dnia przed "do"
        self.okresy = dane_serwera.get("okresy") or {}
        self.baza_urlopow = baza_urlopow or {}
        self.dane_do_zapisu = {}
        self.kontekst_pracownikow = {}

        # Jak load_settings(): niepracujący z panelu HR dopisani do ignorowanych, listy zmian z serwera mają pierwszeństwo
        wczytani_ignorowani = self.u["pracownicy_ignorowani"]
        auto_ignorowani = dane_serwera.get("ignorowani", "")
        if auto_ignorowani:
            aktualna_lista = [x.strip() for x in wczytani_ignorowani.split(',') if x.strip()]
            nowi_ignorowani = [x.strip() for x in auto_ignorowani.split(',') if x.strip() and x.strip() not in aktualna_lista]
            if nowi_ignorowani:
                if aktualna_lista:
                    wczytani_ignorowani += ", "
                wczytani_ignorowani += ", ".join(nowi_ignorowani)
        self.u["pracownicy_ignorowani"] = wczytani_ignorowani
        listy = dane_serwera.get("listy")
        if listy:
            for klucz in LISTY_ZMIAN:
                self.u[klucz] = listy.get(klucz, DOMYSLNE[klucz])

    def przetworz(self, linie, dzien_domkniecia=None):
        """
        Pełne przetworzenie pliku RCP (lista linii). Zwraca (wpisy_anomalii, wszyscy_info, linie_raportu).
        dzien_domkniecia (RRRR.MM.DD): niepełny ostatni dzień pliku (eksport z dnia wygenerowania) - bierzemy z niego tylko
        odbicia nocne zamykające zmianę z poprzedniego dnia (przeniesione jako 24:xx), reszta tego dnia jest pomijana.
        """
        dane = self.grupuj_zdarzenia(linie)
        self.domkniete_z_dnia = 0
        if dzien_domkniecia:
            self.domkniete_z_dnia = sum(1 for z in self.przeniesione if z == dzien_domkniecia)
            dane = {k: v for k, v in dane.items() if k[0] != dzien_domkniecia}
        self.przetworz_slownik_zdarzen(dane)
        return self.generuj_raporty()

    def grupuj_zdarzenia(self, linie):
        wszystkie_zdarzenia = []
        for linia in linie:
            linia = linia.strip()
            if not linia: continue
            f = linia.split(';')
            if len(f) == 3:
                wszystkie_zdarzenia.append({'data': f[0][:10], 'czas': f[0][11:], 'pracownik': f[1], 'kod': f[2]})

        pracownicy = set(z['pracownik'] for z in wszystkie_zdarzenia)
        naprawione_zdarzenia = []
        self.przeniesione = []  # daty, z których odbicia nocne przeniesiono do poprzedniego dnia (24:xx)
        
        limit_nocny = self.u['midnight_limit'] if self.u['chk_midnight'] else "00:00"
        limit_nocny_minuty = parse_czas_do_minut(limit_nocny)
        
        for p in pracownicy:
            zdarzenia_pracownika = [z for z in wszystkie_zdarzenia if z['pracownik'] == p]
            zdarzenia_pracownika.sort(key=lambda x: (x['data'], x['czas']))
            
            # Usuwamy wczesne, "sieroce" wyjścia na samym początku pliku
            while zdarzenia_pracownika and zdarzenia_pracownika[0]['kod'] in ['16', '25', '18']:
                if self.u['chk_midnight'] and parse_czas_do_minut(zdarzenia_pracownika[0]['czas']) <= limit_nocny_minuty: 
                    zdarzenia_pracownika.pop(0)
                else: break
            
            naprawione_zdarzenia_pracownika = []
            for curr in zdarzenia_pracownika:
                # To samo odbicie nocne zarejestrowane dwa razy (np. dwa razy 00:00 kod 16) - pierwsze już zamknęło
                # wczorajszą zmianę, drugie byłoby osieroconym wyjściem na początku dnia
                prev = naprawione_zdarzenia_pracownika[-1] if naprawione_zdarzenia_pracownika else None
                if prev and prev.get('_oryg') == (curr['data'], curr['czas'], curr['kod']):
                    continue
                # Przesuwamy zdarzenia po północy do poprzedniego dnia, by zachować chronologię
                if self.u['chk_midnight']:
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
                                        curr['_oryg'] = (curr['data'], curr['czas'], curr['kod'])
                                        self.przeniesione.append(curr['data'])
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
        return dane_zgrupowane

    def pobierz_dzial_pracownika(self, nr_pracownika):
        nr_czysty = nr_pracownika.strip().replace('\ufeff', '')
        dzial = self.baza_dzialow.get(nr_czysty)
        if not dzial:
            dzial = self.baza_dzialow.get(nr_pracownika)
        if not dzial and nr_czysty.isdigit():
            dzial = self.baza_dzialow.get(str(int(nr_czysty)))
        return dzial.strip() if dzial else "Nieprzypisani"
    def przetworz_slownik_zdarzen(self, dane_zgrupowane):
        self.dane_do_zapisu.clear()
        self.kontekst_pracownikow.clear()

        int_wej, int_wyj = int(self.u['wej_minuty']), int(self.u['wyj_minuty'])
        tol_wej, tol_wyj = int(self.u['wej_tol']), int(self.u['wyj_tol'])
        limit_wej, limit_wyj = int(self.u['dup_wej_min']), int(self.u['dup_wyj_min'])
        
        lista_pracownikow_7h = [x.strip() for x in self.u['pracownicy_7h'].replace(';', ',').split(',') if x.strip()]
        lista_s6_14 = [x.strip() for x in self.u['pracownicy_6_14'].replace(';', ',').split(',') if x.strip()]
        lista_s13_21 = [x.strip() for x in self.u['pracownicy_13_21'].replace(';', ',').split(',') if x.strip()]
        lista_s8_16 = [x.strip() for x in self.u['pracownicy_8_16'].replace(';', ',').split(',') if x.strip()]
        lista_s16_24 = [x.strip() for x in self.u['pracownicy_16_24'].replace(';', ',').split(',') if x.strip()]

        for (data, pracownik), zdarzenia in dane_zgrupowane.items():
            zdarzenia.sort(key=lambda x: parse_czas_do_minut(x['czas']))
            
            jest_na_7h = pracownik in lista_pracownikow_7h
            wymiar_pracy_minuty = 420 if jest_na_7h else 480
            wymiar_pracy_prog = 415 if jest_na_7h else 475
            
            # FILTROWANIE DUPLIKATÓW TEGO SAMEGO KODU
            if self.u['chk_duplikaty']:
                bez_duplikatow, ost_czas = [], {}
                for z in zdarzenia:
                    k, c = z['kod'], z['czas']
                    if k == '00' and '00' in ost_czas and oblicz_roznice_minut(ost_czas['00'], c) <= limit_wej: continue
                    if k == '16' and '16' in ost_czas and oblicz_roznice_minut(ost_czas['16'], c) <= limit_wyj: continue
                    ost_czas[k] = c
                    bez_duplikatow.append(z)
                zdarzenia = bez_duplikatow

            # FILTROWANIE POMYŁKOWYCH ODBIĆ
            if self.u['chk_pomylki']:
                try: limit_pom = int(self.u['pomylki_min'])
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

            if self.u['chk_przepustka'] and zdarzenia:
                if zdarzenia[-1]['kod'] == '25': zdarzenia[-1]['kod'] = '16'

            # Usuwanie KOD 18
            czyste_zdarzenia = []
            skip_next_00 = False
            for z in zdarzenia:
                if z['kod'] == '18' and self.u['chk_usun_18']:
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
                z1_od, z1_do = self.u['z1_od'], self.u['z1_do']
                z2_od, z2_do = self.u['z2_od'], self.u['z2_do']
                
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
                                if typ_zmiany == "Zmiana 1" and self.u['chk_zmiana1'] and self.u['zmiana1_czas'] <= format_czas_gui(c_start)[:5] < '06:00': c_start = '06:00'
                                elif typ_zmiany == "Zmiana 2" and self.u['chk_zmiana2'] and self.u['zmiana2_czas'] <= format_czas_gui(c_start)[:5] < '14:00': c_start = '14:00'
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
                            if self.u['chk_wej']: c_roboczy = zaokraglij_czas(c_roboczy, self.u['wej_kierunek'], int_wej, tol_wej)
                        elif typ_zmiany == "Zmiana 1":
                            if self.u['chk_zmiana1'] and self.u['zmiana1_czas'] <= format_czas_gui(c_roboczy)[:5] < '06:00': c_roboczy = '06:00'
                            if self.u['chk_wej']: c_roboczy = zaokraglij_czas(c_roboczy, self.u['wej_kierunek'], int_wej, tol_wej)
                        elif typ_zmiany == "Zmiana 2":
                            if self.u['chk_zmiana2'] and self.u['zmiana2_czas'] <= format_czas_gui(c_roboczy)[:5] < '14:00': c_roboczy = '14:00'
                            if self.u['chk_wej']: c_roboczy = zaokraglij_czas(c_roboczy, self.u['wej_kierunek'], int_wej, tol_wej)
                        elif typ_zmiany == "Sztywna 06:00-14:00":
                            if "04:00" <= format_czas_gui(c_roboczy)[:5] < '06:00': c_roboczy = '06:00'
                            if self.u['chk_wej']: c_roboczy = zaokraglij_czas(c_roboczy, self.u['wej_kierunek'], int_wej, tol_wej)
                        elif typ_zmiany == "Sztywna 13:00-21:00":
                            if "11:00" <= format_czas_gui(c_roboczy)[:5] < '13:00': c_roboczy = '13:00'
                            if self.u['chk_wej']: c_roboczy = zaokraglij_czas(c_roboczy, self.u['wej_kierunek'], int_wej, tol_wej)
                        elif typ_zmiany == "Sztywna 08:00-16:00":
                            if "06:00" <= format_czas_gui(c_roboczy)[:5] < '08:00': c_roboczy = '08:00'
                            if self.u['chk_wej']: c_roboczy = zaokraglij_czas(c_roboczy, self.u['wej_kierunek'], int_wej, tol_wej)
                        elif typ_zmiany == "Sztywna 16:00-00:00":
                            if "14:00" <= format_czas_gui(c_roboczy)[:5] < '16:00': c_roboczy = '16:00'
                            if self.u['chk_wej']: c_roboczy = zaokraglij_czas(c_roboczy, self.u['wej_kierunek'], int_wej, tol_wej)
                    else:
                        if self.u['chk_wej']: c_roboczy = zaokraglij_czas(c_roboczy, self.u['wej_kierunek'], int_wej, tol_wej)
                    z['czas_skorygowany'] = c_roboczy

            for z in zdarzenia:
                if z['kod'] == '16':
                    c_roboczy = z['czas']
                    is_last_wyjscie = (z == wyjscia[-1]) if wyjscia else False
                    
                    if typ_zmiany == "godziny ruchome" and self.u['chk_flex'] and wejscia and is_last_wyjscie:
                        pierw_wej_skoryg = wejscia[0]['czas_skorygowany']
                        min_in = parse_czas_do_minut(pierw_wej_skoryg)
                        surowy_span = int(oblicz_roznice_minut(wejscia[0]['czas'], wyjscia[-1]['czas']))
                        zaokraglony_span = surowy_span
                        reszta = surowy_span % int_wyj
                        
                        if reszta != 0:
                            if self.u['wyj_kierunek'] == "dół":
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
                        if self.u['chk_wyj']: c_roboczy = zaokraglij_czas(c_roboczy, self.u['wyj_kierunek'], int_wyj, tol_wyj)
                        if self.u['chk_ochrona'] and typ_zmiany in ["Zmiana 1", "Zmiana 2", "Sztywna 06:00-14:00", "Sztywna 13:00-21:00", "Sztywna 08:00-16:00", "Sztywna 16:00-00:00"] and is_last_wyjscie:
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
                            lista_wyjatkow = [d.strip().lower() for d in self.u['dzialy_wyjatek'].split(',') if d.strip()]
                            
                            limit_minut = int(self.u['nadgodziny_min']) if self.u['chk_nadgodziny'] else 0
                            skok = int(self.u['nadgodziny_skok_min']) if self.u['chk_nadgodziny_skok'] else 0
                            
                            czy_wyjatek = self.u['chk_nadgodziny_wyjatek'] and dzial_pracownika.lower() in lista_wyjatkow
                            if czy_wyjatek:
                                limit_minut = int(self.u['nadgodziny_wyjatek_min'])
                                skok = int(self.u['nadgodziny_wyjatek_skok_min'])

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
        
        lista_ignorowanych = [x.strip() for x in self.u['pracownicy_ignorowani'].replace(';', ',').split(',') if x.strip()]
        
        wszystkie_daty = set(d for d, p in self.dane_do_zapisu.keys())
        dni_robocze = set()
        for d in wszystkie_daty:
            try:
                if czy_dzien_roboczy(d):
                    dni_robocze.add(d)
            except: pass
            
        pracownicy_z_pliku = set(p for d, p in self.dane_do_zapisu.keys())
        wszyscy_pracownicy = set(self.baza_pracownikow.keys()).union(pracownicy_z_pliku)

        # Stała kolejność raportu (w 3.1.2 zależała od kolejności zbioru - przy każdym uruchomieniu inna)
        for pracownik in sorted(wszyscy_pracownicy):
            nazwisko = self.baza_pracownikow.get(pracownik, "---")
            dzial = self.pobierz_dzial_pracownika(pracownik)
            na_liscie_ignorowanych = pracownik in lista_ignorowanych
            okres = self.okresy.get(pracownik) or {}

            for data in sorted(list(dni_robocze)):
                klucz = (data, pracownik)
                # Poza okresem z panelu - jak ignorowany. Pracownik z datą "nie pracuje od" jest na liście ignorowanych
                # (starsze wersje programu), ale przed tą datą jest sprawdzany normalnie.
                w_okresie = (not okres.get("od") or data >= okres["od"]) and (not okres.get("do") or data < okres["do"])
                jest_ignorowany = not w_okresie or (na_liscie_ignorowanych and not okres.get("do"))
                
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
                if self.u['chk_ostrzegaj_polnoc']:
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

    def tresc_pliku_erp(self, dane_do_zapisu=None):
        """Treść pliku do importu w ERP (jak finalizuj_zapis w 3.1.2)."""
        dane_do_zapisu = self.dane_do_zapisu if dane_do_zapisu is None else dane_do_zapisu
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
        return "\n".join([r['linia'] for r in wynikowe_rekordy]) + "\n"

    @staticmethod
    def tresc_raportu_brakow(linie_raportu):
        """Treść pliku *_RAPORT_BRAKOW_N.txt (jak finalizuj_zapis w 3.1.2)."""
        return ("--- RAPORT NIEPRAWIDŁOWOŚCI RCP ---\n"
                f"Zarejestrowano nieprawidłowości u {len(linie_raportu)} osób.\nWykryte braki mogły zostać zignorowane lub ręcznie poprawione.\n\n"
                + "\n".join(linie_raportu))


def wczytaj_plan_urlopow(sciezka):
    """
    Plan nieobecności z Excela (Comarch) -> {nr pracownika: zbiór dat 'RRRR.MM.DD'}.
    Logika 1:1 z laduj_urlopy() wersji 3.1.2. Wymaga pandas (+ xlrd dla .xls, openpyxl dla .xlsx).
    """
    import pandas as pd
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
                
    return baza_urlopow
