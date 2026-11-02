from datetime import datetime, timedelta

def parse_czas_do_minut(czas_str):
    """ Zamienia czas HH:MM na całkowitą liczbę minut, obsługuje godziny >= 24 """
    if not czas_str or czas_str == "---": return 0
    godz, minuty = map(int, czas_str.split(':'))
    return godz * 60 + minuty

def formatuj_minuty_do_czasu(minuty_total):
    """ Zamienia minuty na format HH:MM, pozwalając na swobodne wyjście poza 24h """
    godz = minuty_total // 60
    minuty = minuty_total % 60
    return f"{godz:02d}:{minuty:02d}"

def zaokraglij_czas(czas_str, kierunek, interwal, tolerancja=0):
    """ Zaokrągla czas do najbliższego interwału zgodnie z kierunkiem i tolerancją. """
    if not czas_str or czas_str == "---": return czas_str
    try:
        minuty_total = parse_czas_do_minut(czas_str)
        
        if kierunek == "góra":
            nowe_minuty = ((minuty_total + interwal - 1) // interwal) * interwal
            if minuty_total - (nowe_minuty - interwal) <= tolerancja:
                nowe_minuty = nowe_minuty - interwal
        else: # dół
            nowe_minuty = (minuty_total // interwal) * interwal
            if (nowe_minuty + interwal) - minuty_total <= tolerancja:
                nowe_minuty = nowe_minuty + interwal
                
        return formatuj_minuty_do_czasu(nowe_minuty)
    except Exception:
        return czas_str

def oblicz_roznice_minut(czas1_str, czas2_str):
    """ Zwraca wartość bezwzględną różnicy czasu w minutach (bezpieczna arytmetyka) """
    try:
        min1 = parse_czas_do_minut(czas1_str)
        min2 = parse_czas_do_minut(czas2_str)
        return abs(min2 - min1)
    except Exception:
        return 0