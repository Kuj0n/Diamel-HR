from datetime import datetime, timedelta

def oblicz_wielkanoc(rok):
    """
    Algorytm Meeusa/Jonesa/Butchera wyliczający dokładną datę Wielkanocy 
    dla kalendarza gregoriańskiego (niezawodny dla dowolnego roku).
    """
    a = rok % 19
    b = rok // 100
    c = rok % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    miesiac = (h + l - 7 * m + 114) // 31
    dzien = ((h + l - 7 * m + 114) % 31) + 1
    return datetime(rok, miesiac, dzien)

def pobierz_swieta_dla_roku(rok):
    """ Zwraca zbiór dat (w formacie YYYY.MM.DD) będących świętami ustawowo wolnymi w Polsce. """
    wielkanoc = oblicz_wielkanoc(rok)
    poniedzialek_wielkanocny = wielkanoc + timedelta(days=1)
    boze_cialo = wielkanoc + timedelta(days=60)
    # Zielone Świątki wypadają zawsze w niedzielę (Wielkanoc + 49 dni), 
    # ale dla porządku kalendarzowego możemy je również wygenerować.
    zielone_swiatki = wielkanoc + timedelta(days=49)
    
    swieta = {
        f"{rok}.01.01",  # Nowy Rok
        f"{rok}.01.06",  # Trzech Króli
        f"{rok}.05.01",  # Święto Pracy
        f"{rok}.05.03",  # Święto Konstytucji 3 Maja
        f"{rok}.08.15",  # Wniebowzięcie NMP
        f"{rok}.11.01",  # Wszystkich Świętych
        f"{rok}.11.11",  # Święto Niepodległości
        f"{rok}.12.24",  # Wigilia
        f"{rok}.12.25",  # Boże Narodzenie (dzień 1)
        f"{rok}.12.26",  # Boże Narodzenie (dzień 2)
        wielkanoc.strftime("%Y.%m.%d"),
        poniedzialek_wielkanocny.strftime("%Y.%m.%d"),
        zielone_swiatki.strftime("%Y.%m.%d"),
        boze_cialo.strftime("%Y.%m.%d")
    }
    return swieta

def czy_dzien_roboczy(data_str):
    """
    Sprawdza czy dany dzień (w formacie YYYY.MM.DD) jest roboczy.
    Zwraca False dla sobót, niedziel oraz polskich świąt ustawowych.
    """
    try:
        dt = datetime.strptime(data_str, "%Y.%m.%d")
        # 5 = Sobota, 6 = Niedziela
        if dt.weekday() >= 5:
            return False
            
        # Odpytywanie wygenerowanej dynamicznie puli świąt dla danego roku
        swieta_w_roku = pobierz_swieta_dla_roku(dt.year)
        if data_str in swieta_w_roku:
            return False
            
        return True
    except ValueError:
        return False