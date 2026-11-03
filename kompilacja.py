import os
import re
import json
import subprocess
import shutil

# --- KONFIGURACJA ---
# Program nie zawiera danych pracowników ani haseł - lista pracowników jest pobierana
# z serwera po zalogowaniu (serwer_hr.py), więc instalator może być publiczny.
folder_zasoby = "Zasoby"

plik_glowny = "aplikacja.py"
pliki_modulow = ["interfejs.py", "silnik.py", "raport_pdf.py", "obliczenia.py", "narzedzia.py", "kalendarz.py", "serwer_hr.py", "konfiguracja_app.py"]
folder_ui = "ui"  # wygląd okna (HTML/CSS/JS, czcionki) - Edge WebView2 przez pywebview

plik_ikony = os.path.join(folder_zasoby, "ikona.ico")

# Automatyczne wykrywanie kompilatora Inno Setup
inno_setup_compiler = r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not os.path.exists(inno_setup_compiler):
    inno_setup_compiler = r"C:\Program Files\Inno Setup 7\ISCC.exe"
    if not os.path.exists(inno_setup_compiler):
        print("❌ Błąd: Nie znaleziono kompilatora Inno Setup!")
        exit(1)

print("🔍 Analizowanie konfiguracji (wersja MVC)...")
with open("konfiguracja_app.py", "r", encoding="utf-8") as f:
    kod_konf = f.read()

# Wyciąganie wersji z konfiguracja_app.py
try:
    wersja = re.search(r'VERSION\s*=\s*"([^"]+)"', kod_konf).group(1)
    data_wydania = re.search(r'BUILD_DATE\s*=\s*"([^"]+)"', kod_konf).group(1)[:10]
    changelog_full = re.search(r'CHANGELOG\s*=\s*"""(.*?)"""', kod_konf, re.DOTALL).group(1).strip()
    github_repo = re.search(r'GITHUB_REPO\s*=\s*"([^"]+)"', kod_konf).group(1)
except AttributeError:
    print("❌ Błąd: Nie znaleziono VERSION w pliku konfiguracja_app.py."); exit(1)

# 1. STRUKTURA FOLDERÓW WYJŚCIOWYCH (Paczka = instalator do wydania na GitHub)
folder_wersji = wersja
folder_archiwum = os.path.join(folder_wersji, "Archiwum")
folder_paczka = os.path.join(folder_wersji, "Paczka")

os.makedirs(folder_archiwum, exist_ok=True)
os.makedirs(folder_paczka, exist_ok=True)

# 2. KOPIOWANIE WSZYSTKICH MODUŁÓW I ZASOBÓW DO ARCHIWUM
print("📂 Kopiowanie rozdzielonych modułów (MVC) i Zasobów do Archiwum...")
for m_plik in [plik_glowny] + pliki_modulow:
    if os.path.exists(m_plik): shutil.copy(m_plik, os.path.join(folder_archiwum, m_plik))

# Dodano kopiowanie folderu z zasobami (obrazki splash screen, itp.)
if os.path.exists(folder_zasoby):
    shutil.copytree(folder_zasoby, os.path.join(folder_archiwum, folder_zasoby), dirs_exist_ok=True)
    
if os.path.exists(plik_ikony): shutil.copy(plik_ikony, os.path.join(folder_archiwum, "ikona.ico"))
shutil.copytree(folder_ui, os.path.join(folder_archiwum, folder_ui), dirs_exist_ok=True)

# 2.5 GENEROWANIE PLIKU METADANYCH DLA WINDOWSA
v_parts = wersja.split('.')
v_parts += ['0'] * (4 - len(v_parts)) 
v_tuple_str = f"{v_parts[0]}, {v_parts[1]}, {v_parts[2]}, {v_parts[3]}"
v_str = f"{v_parts[0]}.{v_parts[1]}.{v_parts[2]}.{v_parts[3]}"

nazwa_stala = "Korektor_logow"
nazwa_instalatora_exe = f"Instalator_Korektor_HR_v{wersja}.exe"

version_info_content = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({v_tuple_str}), prodvers=({v_tuple_str}), mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable(u'041504b0', [StringStruct(u'CompanyName', u'Diamel'), StringStruct(u'FileDescription', u'Korektor Logów HR'), StringStruct(u'FileVersion', u'{v_str}'), StringStruct(u'InternalName', u'Korektor_logow'), StringStruct(u'OriginalFilename', u'{nazwa_stala}.exe'), StringStruct(u'ProductName', u'Specjalny Korektor Logów HR'), StringStruct(u'ProductVersion', u'{v_str}')])]), 
    VarFileInfo([VarStruct(u'Translation', [1045, 1200])])
  ]
)"""
with open(os.path.join(folder_archiwum, "wersja_info.txt"), "w", encoding="utf-8") as f:
    f.write(version_info_content)

# 3. LISTA ZMIAN TEJ WERSJI = OPIS WYDANIA NA GITHUB
wzorzec = rf'(v{wersja}.*?)(?=\nv\d+\.\d+|$)'
match = re.search(wzorzec, changelog_full, re.DOTALL)
changelog_wersji = match.group(1).strip() if match else f"v{wersja}\nBrak opisu zmian."

# 4. TWORZENIE PLIKU INFORMACYJNEGO DO INSTALATORA (Z CHANGELOGIEM)
plik_info_txt = os.path.join(folder_archiwum, "info_instalatora.txt")
tresc_info = f"""=========================================
 KOREKTOR LOGÓW HR - DIAMEL
=========================================

To oprogramowanie służy do weryfikacji i automatycznej korekty logów czasu pracy pochodzących z czytników (np. system Roger). 

Przetworzone, wolne od błędów i zaokrąglone logi są następnie przygotowywane pod bezkonfliktowy import do systemów kadrowych klasy ERP (np. Comarch Optima / XL).

Główne funkcjonalności:
- Zaawansowana filtracja podwójnych odbić i anomalii z czytników.
- Dynamiczne zaokrąglanie wejść i wyjść z logiką godzin ruchomych.
- Ochrona wypracowanego etatu (7h / 8h) przy zaokrągleniach.
- Lista do sprawdzenia z propozycjami poprawek i korektą dnia jednym kliknięciem.
- Reguły firmowe wspólne dla wszystkich komputerów (panel HR na diamel.pl).
- Raport braków odbić w TXT i PDF (pod drukarkę czarno-białą).

=========================================
 HISTORIA ZMIAN:
=========================================
{changelog_full}

© Mateusz Kujawa (Diamel)
"""
with open(plik_info_txt, "w", encoding="utf-8") as f: f.write(tresc_info)

# 5. KOMPILACJA PROGRAMU BAZOWEGO
print(f"⏳ Kompilacja struktury programu dla wersji {wersja}...")
# PyInstaller pakuje do srodka cały folder "Zasoby"
komenda_pyinstaller = (
    f'python -m PyInstaller --onedir --noconsole --clean --noconfirm '
    f'--icon="ikona.ico" --add-data "ikona.ico;." '
    f'--add-data "{folder_zasoby};{folder_zasoby}" '
    f'--add-data "{folder_ui};{folder_ui}" '
    f'--collect-all webview --collect-all clr_loader --collect-all pythonnet --hidden-import clr '
    f'--hidden-import fpdf --hidden-import xlrd --hidden-import openpyxl '
    f'--version-file="wersja_info.txt" '
    f'--hidden-import="ctypes" --collect-all ctypes '
    f'-n "{nazwa_stala}" "{plik_glowny}"'
)
subprocess.run(komenda_pyinstaller, shell=True, cwd=folder_archiwum, check=True)

dist_base = os.path.join(folder_archiwum, "dist")
sciezka_folderu_dist = os.path.join(dist_base, nazwa_stala)
if not os.path.exists(sciezka_folderu_dist):
    podfoldery = [f.path for f in os.scandir(dist_base) if f.is_dir()]
    sciezka_folderu_dist = podfoldery[0] if podfoldery else exit("❌ BŁĄD: PyInstaller nie stworzył folderu w dist!")

# 6. TWORZENIE PLIKU KONFIGURACYJNEGO INNO SETUP (.iss)
sciezka_wyjsciowa_ftp = os.path.abspath(folder_paczka)
sciezka_ikony_abs = os.path.abspath(os.path.join(folder_archiwum, "ikona.ico"))
sciezka_info_abs = os.path.abspath(plik_info_txt)

opcje_graficzne = ""
s_kolazu = os.path.abspath(os.path.join(folder_zasoby, "HR_polaczenia_pion.bmp"))
s_logo = os.path.abspath(os.path.join(folder_zasoby, "logo_male.bmp"))
if os.path.exists(s_kolazu): opcje_graficzne += f'\nWizardImageFile={s_kolazu}'
if os.path.exists(s_logo): opcje_graficzne += f'\nWizardSmallImageFile={s_logo}'

inno_skrypt = f"""
[Setup]
AppId=KorektorLogowHR_Diamel
AppName=Korektor Logów HR
AppVersion={wersja}
AppPublisher=Diamel
AppPublisherURL=https://diamel.pl/
DefaultDirName={{autopf}}\\Korektor Logow HR
DefaultGroupName=Korektor Logów HR
DisableWelcomePage=no
DisableProgramGroupPage=yes
OutputDir={sciezka_wyjsciowa_ftp}
OutputBaseFilename=Instalator_Korektor_HR_v{wersja}
SetupIconFile={sciezka_ikony_abs}
Compression=lzma2/ultra
SolidCompression=yes
PrivilegesRequired=lowest
UninstallDisplayIcon={{app}}\\{nazwa_stala}.exe
InfoBeforeFile={sciezka_info_abs}{opcje_graficzne}

[Languages]
Name: "pl"; MessagesFile: "compiler:Languages\\Polish.isl"

[Tasks]
Name: "desktopicon"; Description: "Utwórz skrót na pulpicie"; GroupDescription: "Dodatkowe ikony:";

[InstallDelete]
Type: files; Name: "{{app}}\\Korektor_logow_v*.exe"
Type: filesandordirs; Name: "{{app}}\\_internal"

[Files]
Source: "{os.path.abspath(sciezka_folderu_dist)}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{{group}}\\Korektor Logów HR"; Filename: "{{app}}\\{nazwa_stala}.exe"
Name: "{{autodesktop}}\\Korektor Logów HR"; Filename: "{{app}}\\{nazwa_stala}.exe"; Tasks: desktopicon

[Run]
Filename: "{{app}}\\{nazwa_stala}.exe"; Description: "Uruchom Korektor Logów HR"; WorkingDir: "{{app}}"; Flags: nowait postinstall skipifsilent

[Code]
const HWND_TOPMOST = -1; SWP_SHOWWINDOW = $0040; FLASHW_ALL = $00000006;
type TFlashWInfo = record cbSize: UINT; hwnd: HWND; dwFlags: DWORD; uCount: UINT; dwTimeout: DWORD; end;
function SetWindowPos(hWnd: HWND; h: HWND; X,Y,cx,cy: Integer; uFlags: UINT): BOOL; external 'SetWindowPos@user32.dll stdcall';
function FlashWindowEx(var pfwi: TFlashWInfo): BOOL; external 'FlashWindowEx@user32.dll stdcall';
procedure InitializeWizard;
var fwi: TFlashWInfo;
begin
  SetWindowPos(WizardForm.Handle, HWND_TOPMOST, 0,0,0,0, 3);
  fwi.cbSize := 20; fwi.hwnd := WizardForm.Handle; fwi.dwFlags := FLASHW_ALL; fwi.uCount := 5; FlashWindowEx(fwi);
end;
"""

plik_iss = os.path.join(folder_archiwum, "skrypt_instalatora.iss")
with open(plik_iss, "w", encoding="utf-8") as f: f.write(inno_skrypt)

# 7. KOMPILACJA INSTALATORA (.exe)
print("📦 Kompresowanie do bezpiecznego instalatora Windows...")
if subprocess.run(f'"{inno_setup_compiler}" "{plik_iss}"', shell=True).returncode != 0:
    exit("❌ BŁĄD: Inno Setup nie zbudował instalatora!")
print(f"\n🚀 SUKCES! Wersja: {wersja}. Plik czeka wewnątrz folderu 'Paczka'.")

# 8. PUBLIKACJA NA GITHUB
odp = input(f"\n🌐 Opublikować wydanie v{wersja} na GitHub ({github_repo})? [t/N]: ").strip().lower()
if odp == "t":
    gh = shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"
    if subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout.strip():
        print("❌ Niezatwierdzone zmiany w repozytorium - najpierw commit, potem ponów publikację.")
        exit(1)
    subprocess.run(["git", "push", "origin", "HEAD"], check=True)
    subprocess.run([gh, "release", "create", f"v{wersja}", os.path.join(folder_paczka, nazwa_instalatora_exe),
                    "--repo", github_repo, "--target", "master", "--title", f"v{wersja}", "--notes", changelog_wersji], check=True)
    print(f"✅ Opublikowano: https://github.com/{github_repo}/releases/tag/v{wersja}")
else:
    print("Publikację pominięto. Instalator jest w folderze Paczka.")