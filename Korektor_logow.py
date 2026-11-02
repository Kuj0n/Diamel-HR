import os
import ctypes
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk  # NOWY IMPORT
from konfiguracja_app import sciezka_do_zasobu
from gui import AppHR

def pokaz_splash_screen(root, po_zakonczeniu_callback):
    # Ukrywamy główne okno programu na czas ładowania
    root.withdraw()
    
    splash = tk.Toplevel(root)
    splash.overrideredirect(True) # Wyłącza systemowe ramki (krzyżyk, minimalizację)
    splash.configure(bg="white")
    
    # Wymiary okienka ładowania
    splash_w = 600
    splash_h = 350
    
    # Wyliczanie środka ekranu
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    x = (screen_w // 2) - (splash_w // 2)
    y = (screen_h // 2) - (splash_h // 2)
    splash.geometry(f"{splash_w}x{splash_h}+{x}+{y}")
    
    # Próba wczytania obrazka poziomego (musi być .png lub .jpg)
    img_path = sciezka_do_zasobu(os.path.join("Zasoby", "HR połączenia.png"))
    if not os.path.exists(img_path):
        img_path = sciezka_do_zasobu("HR połączenia.png") # Fallback
        
    try:
        # Wczytujemy grafikę przez bibliotekę PIL (Pillow)
        oryginalny_obraz = Image.open(img_path)
        
        # Ustalamy maksymalny rozmiar tak, aby zostawić miejsce na pasek ładowania
        # Metoda thumbnail() idealnie zachowuje proporcje grafiki
        oryginalny_obraz.thumbnail((560, 240), Image.Resampling.LANCZOS)
        
        # Konwersja na format zrozumiały dla Tkinter
        bg_image = ImageTk.PhotoImage(oryginalny_obraz)
        
        splash.bg_image = bg_image # Referencja, żeby obrazek nie zniknął z pamięci
        lbl_img = tk.Label(splash, image=bg_image, bg="white")
        lbl_img.pack(pady=(20, 10))
    except Exception as e:
        # Fallback na zwykły tekst, jeśli brakuje pliku graficznego
        lbl_title = tk.Label(splash, text="KOREKTOR LOGÓW HR\nDIAMEL", font=("Arial", 22, "bold"), bg="white", fg="#2196F3")
        lbl_title.pack(expand=True)
        
    # Pasek postępu
    style = ttk.Style()
    style.theme_use('clam')
    style.configure("TProgressbar", thickness=6)
    
    progress = ttk.Progressbar(splash, orient="horizontal", length=500, mode="determinate", style="TProgressbar")
    progress.pack(side="bottom", pady=(15, 20))
    
    # Etykieta zmieniającego się statusu
    lbl_status = tk.Label(splash, text="Inicjalizacja środowiska bazowego...", font=("Arial", 10, "italic"), bg="white", fg="gray")
    lbl_status.pack(side="bottom")
    
    # Sekwencja statusów i procenty (kiedy dany tekst ma wskoczyć)
    komunikaty = [
        (0, "Inicjalizacja środowiska bazowego..."),
        (12, "Ładowanie silnika matematycznego MVC..."),
        (25, "Przygotowanie połączenia z bazą pracowników..."),
        (37, "Ładowanie modułów Menedżera Korekt..."),
        (55, "Kalibracja Roger RCP Master 4..."),
        (80, "Kalibracja Comarch ERP XL HR..."),
        (95, "Uruchamianie interfejsu graficznego...")
    ]
    
    def aktualizuj_postep(krok=0):
        if krok <= 100:
            progress['value'] = krok
            
            # Sprawdzanie i zmiana tekstu
            for prog, text in reversed(komunikaty):
                if krok >= prog:
                    lbl_status.config(text=text)
                    break
                    
            # 5 sekund ładowania (100 kroków co 50 milisekund = 5000 ms)
            splash.after(70, aktualizuj_postep, krok + 1)
        else:
            # Ładowanie zakończone
            splash.destroy() # Zamykamy splash screen
            root.deiconify() # Pokazujemy prawdziwy program
            po_zakonczeniu_callback() # Wywołujemy funkcje startowe (AppHR)

    # Start paska ładowania
    aktualizuj_postep(0)


if __name__ == "__main__":
    try:
        # Zapewnia, że skróty na pasku zadań będą zgrupowane (Anti-FP)
        myappid = "diamel.hr.korektor.main"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    root = tk.Tk()
    
    try:
        icon_path = sciezka_do_zasobu(os.path.join("Zasoby", "ikona.ico"))
        if not os.path.exists(icon_path):
            icon_path = sciezka_do_zasobu("ikona.ico")
            
        if os.path.exists(icon_path):
            root.iconbitmap(default=icon_path)
    except Exception:
        pass

    # Przekazujemy logikę startową do zmiennej
    def start_aplikacji():
        app = AppHR(root)
        
    # Odpalamy magię!
    pokaz_splash_screen(root, start_aplikacji)
    
    root.mainloop()