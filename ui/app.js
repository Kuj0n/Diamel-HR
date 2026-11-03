/* Korektor Logów HR - logika okna. Obliczenia i pliki: Python (interfejs.py) przez window.pywebview.api */
'use strict';

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (t) => String(t ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const liczba = (n) => Number(n || 0).toLocaleString('pl-PL');
const odmiana = (n, jeden, kilka, wiele) => (n === 1 ? jeden : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? kilka : wiele);
const DNI = ['niedziela', 'poniedziałek', 'wtorek', 'środa', 'czwartek', 'piątek', 'sobota'];
const DNI_KR = ['nd', 'pn', 'wt', 'śr', 'cz', 'pt', 'sb'];
const RODZAJE = { blad: 'Błędy', niepelny: 'Niepełne', ostrzezenie: 'Ostrzeżenia', nieobecnosc: 'Nieobecności' };
const KODY = { '00': 'Wejście', '16': 'Wyjście', '18': 'Przerwa', '25': 'Przepustka' };

const IK = {
  ok: '<path d="M20 6 9 17l-5-5"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  plik: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>',
  kalendarz: '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18M8 3v4M16 3v4M8 15h3"/>',
  pobierz: '<path d="M12 3v12M7 10l5 5 5-5M5 21h14"/>',
  odswiez: '<path d="M21 12a9 9 0 1 1-3-6.7L21 8M21 3v5h-5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  kosz: '<path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/>',
  wstecz: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 8h.01M11 12h1v5h1"/>',
  uwaga: '<path d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>',
  upusc: '<path d="M12 16V4M7 9l5-5 5 5M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>',
  zegar: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  wej: '<path d="M3 12h13M12 7l5 5-5 5M20 4v16"/>',
  wyj: '<path d="M21 12H8M12 7l-5 5 5 5M4 4v16"/>',
  kopia: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
  wykres: '<path d="M3 17l6-6 4 4 8-8M15 7h6v6"/>',
  ksiezyc: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/>',
  ludzie: '<circle cx="9" cy="8" r="4"/><path d="M2 21a7 7 0 0 1 14 0M17 11a3 3 0 1 0 0-6M22 21a6 6 0 0 0-4-5.6"/>',
  wyslij: '<path d="M22 2 11 13M22 2l-7 20-4-9-9-4Z"/>',
  dalej: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  szukaj: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  serwer: '<rect x="3" y="4" width="18" height="7" rx="2"/><rect x="3" y="13" width="18" height="7" rx="2"/><path d="M7 7.5h.01M7 16.5h.01"/>',
};
const ik = (n, kl = '') => `<svg class="ik ${kl}" viewBox="0 0 24 24">${IK[n]}</svg>`;

// ------------------------------------------------------------------ stan okna
let INFO = {}, STAN = null, REG = null, KONTO = null, AKT = null, PRACOWNICY = [], WPISY = [];
let widok = 'pulpit';
const filtr = { tryb: 'problemy', rodzaje: new Set(['blad', 'niepelny', 'ostrzezenie', 'nieobecnosc']), dzialy: new Set(), szukaj: '', ukryjSprawdzone: false, sort: '' };
let wybranyId = null;
let szuflada = null;   // { d: dane dnia z Pythona, z: zdarzenia w edycji, kolejka: lista id }
let przeliczTimer = null;

async function api(nazwa, ...arg) {
  try {
    return await window.pywebview.api[nazwa](...arg);
  } catch (e) {
    toast(`Błąd programu (${nazwa}): ${e.message || e}`, 'blad');
    console.error(e);
    return null;
  }
}

// ------------------------------------------------------------------ motyw i rozmiar
const ciemnySystem = window.matchMedia('(prefers-color-scheme: dark)');
function ustawMotyw(m) {
  const efekt = m === 'system' ? (ciemnySystem.matches ? 'ciemny' : 'jasny') : m;
  document.documentElement.dataset.motyw = efekt;
  $$('#motyw button').forEach((b) => b.classList.toggle('akt', b.dataset.motyw === m));
}
ciemnySystem.addEventListener('change', () => INFO.program && ustawMotyw(INFO.program.motyw));
async function zmienProgram(klucz, wartosc) {
  INFO.program = await api('ustaw_program', klucz, wartosc);
  if (klucz === 'motyw') ustawMotyw(wartosc);
  if (klucz === 'rozmiar') document.documentElement.dataset.rozmiar = wartosc;
}

// ------------------------------------------------------------------ powiadomienia i okna dialogowe
function toast(tekst, rodzaj = '', akcja = null, czas = 5000) {
  const el = document.createElement('div');
  el.className = `toast ${rodzaj}`;
  el.innerHTML = `${ik(rodzaj === 'blad' ? 'uwaga' : rodzaj === 'ok' ? 'ok' : 'info')}<span>${tekst}</span>`;
  if (akcja) {
    const b = document.createElement('button');
    b.className = 'btn btn-maly';
    b.textContent = akcja.tekst;
    b.onclick = () => { akcja.fn(); el.remove(); };
    el.append(b);
  }
  $('#powiadomienia').append(el);
  setTimeout(() => el.remove(), rodzaj === 'blad' ? czas * 2 : czas);
}

let modalOtwarty = null;
function modal({ tytul, tresc = '', przyciski = [], szeroki = false, poOtwarciu = null }) {
  return new Promise((gotowe) => {
    const tlo = document.createElement('div');
    tlo.className = 'modal-tlo';
    tlo.innerHTML = `<div class="modal ${szeroki ? 'szeroki' : ''}" role="dialog"><h2>${tytul}</h2><div class="tresc-modala">${tresc}</div>
      ${przyciski.length ? `<div class="przyciski">${przyciski.map((p, i) => `<button class="btn ${p.klasa || ''}" data-i="${i}">${p.tekst}</button>`).join('')}</div>` : ''}</div>`;
    const zamknij = (w) => { tlo.remove(); modalOtwarty = null; gotowe(w); };
    tlo.addEventListener('click', (e) => {
      if (e.target === tlo) zamknij(null);
      const b = e.target.closest('[data-i]');
      if (b) zamknij(przyciski[+b.dataset.i].wartosc);
      const w = e.target.closest('[data-wybor]');
      if (w) zamknij(w.dataset.wybor);
    });
    modalOtwarty = { zamknij, el: tlo };
    $('#modal-miejsce').append(tlo);
    const dom = przyciski.findIndex((p) => p.domyslny);
    (dom >= 0 ? $(`[data-i="${dom}"]`, tlo) : $('.domyslny, input, textarea, .btn', tlo))?.focus();
    poOtwarciu?.(tlo, zamknij);
  });
}

// ------------------------------------------------------------------ start: aktualizacje, logowanie
window.addEventListener('pywebviewready', start);

async function start() {
  INFO = await api('informacje');
  ustawMotyw(INFO.program.motyw);
  document.documentElement.dataset.rozmiar = INFO.program.rozmiar;
  $('#start-wersja').textContent = $('#boczne-wersja').textContent = `DIAMEL · v${INFO.wersja}`;
  sprawdzAktualizacje(false);
  const d = await api('pobierz_dane');
  if (d?.ok) return wejdz(d);
  ekranLogowania(d?.zaloguj ? '' : d?.blad || '', !d?.zaloguj);
}

async function sprawdzAktualizacje(recznie) {
  AKT = await api('sprawdz_aktualizacje');
  odswiezDol();
  const miejsce = $('#start-aktualizacja');
  if (AKT?.nowsza) {
    miejsce.innerHTML = `<div class="baner zolty">${ik('pobierz')}<div class="tekst"><b>Dostępna wersja ${esc(AKT.wersja)}</b>Możesz zainstalować ją przed zalogowaniem.</div>
      <button class="btn btn-maly" id="start-instaluj">Zainstaluj</button></div>`;
    $('#start-instaluj').onclick = oknoAktualizacji;
  } else miejsce.innerHTML = '';
  if (recznie) {
    if (!AKT?.ok) toast(`Nie udało się sprawdzić aktualizacji: ${esc(AKT?.blad || '')}`, 'blad');
    else if (AKT.nowsza) oknoAktualizacji();
    else toast(`Masz najnowszą wersję (${esc(INFO.wersja)}).`, 'ok');
  }
}

async function oknoAktualizacji() {
  const w = await modal({
    tytul: `${ik('pobierz')} Aktualizacja do wersji ${esc(AKT.wersja)}`, szeroki: true,
    tresc: `<p>Obecna wersja: <b>${esc(INFO.wersja)}</b>. Program zamknie się na czas instalacji i uruchomi ponownie.</p>
      <div class="karta" style="white-space:pre-wrap; max-height:300px; overflow:auto; font-size:0.86rem">${esc(AKT.opis || 'Brak opisu zmian.')}</div>`,
    przyciski: [{ tekst: 'Później', wartosc: null }, { tekst: `${ik('pobierz')} Pobierz i zainstaluj`, klasa: 'btn-hr', wartosc: 'tak', domyslny: true }],
  });
  if (w !== 'tak') return;
  modal({ tytul: 'Pobieranie aktualizacji…', tresc: '<div class="postep" style="height:8px"><i id="akt-postep" style="width:0%"></i></div><p class="podp" id="akt-tekst" style="margin-top:10px">0%</p>' });
  window.postepAktualizacji = (p) => { const el = $('#akt-postep'); if (el) { el.style.width = `${p}%`; $('#akt-tekst').textContent = `${p}%`; } };
  window.aktualizacjaPobrana = (ok, blad) => {
    if (ok) return api('uruchom_instalator');
    modalOtwarty?.zamknij();
    toast(`Nie udało się pobrać aktualizacji: ${esc(blad)}`, 'blad');
  };
  api('pobierz_aktualizacje', AKT.link);
}

function ekranLogowania(blad = '', brakPolaczenia = false) {
  $('#ekran-start').classList.remove('ukryty');
  const t = $('#start-tresc');
  t.innerHTML = `
    <div><h2 style="font-size:1.3rem">Zaloguj się</h2><div class="podp">Lista pracowników, działy i reguły firmowe pobierane są z serwera diamel.pl</div></div>
    ${blad ? `<div class="blad">${esc(blad)}</div>` : ''}
    <div><label class="etykieta" for="l-login">Login</label><input class="pole" id="l-login" autocomplete="username" spellcheck="false"></div>
    <div><label class="etykieta" for="l-haslo">Hasło</label><input class="pole" id="l-haslo" type="password" autocomplete="current-password"></div>
    <label class="zaznacz"><input type="checkbox" id="l-zapamietaj" checked> Zapamiętaj na tym komputerze</label>
    <button class="btn btn-hr duzy" id="l-zaloguj">Zaloguj</button>
    <div style="display:flex; justify-content:space-between; gap:10px; font-size:0.86rem">
      <button class="link" id="l-przypomnij">Nie pamiętam hasła</button>
      ${brakPolaczenia ? '<button class="link" id="l-ponow">Spróbuj ponownie</button>' : ''}
    </div>
    <button class="btn btn-bez btn-maly" id="l-bez">Pracuj bez listy pracowników</button>`;
  const zaloguj = async () => {
    const login = $('#l-login').value, haslo = $('#l-haslo').value;
    if (!login || !haslo) return $('#l-login').focus();
    $('#l-zaloguj').disabled = true;
    $('#l-zaloguj').textContent = 'Logowanie…';
    const r = await api('zaloguj', login, haslo, $('#l-zapamietaj').checked);
    if (!r?.ok) return ekranLogowania(r?.blad || 'Logowanie nie powiodło się.');
    const d = await api('pobierz_dane');
    if (d?.ok) wejdz(d); else ekranLogowania(d?.blad || 'Nie udało się pobrać danych.');
  };
  $('#l-zaloguj').onclick = zaloguj;
  $$('#l-login, #l-haslo').forEach((el) => el.addEventListener('keydown', (e) => e.key === 'Enter' && zaloguj()));
  $('#l-przypomnij').onclick = async () => {
    const login = $('#l-login').value.trim();
    if (!login) { toast('Wpisz login - wyślemy prośbę o nowe hasło do administratora.'); return $('#l-login').focus(); }
    const r = await api('nie_pamietam_hasla', login);
    if (r?.ok) toast('Prośba o nowe hasło została wysłana. Administrator przyśle nowe hasło e-mailem.', 'ok', null, 9000);
    else toast(esc(r?.blad || 'Nie udało się wysłać prośby.'), 'blad');
  };
  $('#l-ponow')?.addEventListener('click', start);
  $('#l-bez').onclick = () => wejdz(null);
  $('#l-login').focus();
}

async function wejdz(dane) {
  KONTO = dane;
  $('#ekran-start').classList.add('ukryty');
  REG = await api('reguly');
  STAN = await api('stan');
  PRACOWNICY = (await api('pracownicy')) || [];
  odswiezDol();
  pokaz(widok);
}

function odswiezDol() {
  $('#dol-konto').innerHTML = KONTO ? `Zalogowano: <b>${esc(KONTO.login || 'tak')}</b>` : 'Bez listy pracowników';
  $('#dol-baza').innerHTML = KONTO ? `Baza pracowników: <b>${liczba(KONTO.pracownikow)}</b>` : '';
  const w = $('#dol-wersja');
  if (AKT?.nowsza) { w.innerHTML = `<span class="akt-nowa">● dostępna wersja ${esc(AKT.wersja)}</span>`; w.onclick = oknoAktualizacji; }
  else { w.innerHTML = `<span class="akt-ok">● v${esc(INFO.wersja || '')}${AKT?.ok ? ' · aktualna' : ''}</span>`; w.onclick = null; }
  const doSpr = STAN?.statystyki?.do_sprawdzenia || 0;
  $('#licznik-pulpit').textContent = doSpr;
  $('#licznik-pulpit').classList.toggle('ukryty', !doSpr);
  const lok = Object.keys(REG?.lokalne || {}).length;
  $('#licznik-reguly').textContent = lok;
  $('#licznik-reguly').classList.toggle('ukryty', !lok);
  $('#licznik-reguly').title = 'Zmiany lokalne (tylko na tym komputerze)';
}

// ------------------------------------------------------------------ nawigacja
const TYTULY = {
  pulpit: ['Korektor Logów HR', 'Korekta logów czasu pracy'], reguly: ['Ustawienia korekty', 'Reguły korekty'],
  historia: ['Ostatnio przetwarzane', 'Historia przetworzeń'],
  ustawienia: ['Program', 'Ustawienia'], zglos: ['Pomoc', 'Zgłoś błąd'],
};
function pokaz(w) {
  widok = w;
  $$('.poz').forEach((p) => p.classList.toggle('akt', p.dataset.widok === w));
  $$('.widok').forEach((s) => s.classList.toggle('ukryty', s.id !== `widok-${w}`));
  $('#pasek-nad').textContent = TYTULY[w][0];
  $('#pasek-tytul').textContent = TYTULY[w][1];
  $('#pasek-prawe').innerHTML = '';
  ({ pulpit: rysujPulpit, reguly: rysujReguly, historia: rysujHistorie, ustawienia: rysujUstawienia, zglos: rysujZgloszenie })[w]();
}
$$('.poz').forEach((p) => p.addEventListener('click', async () => { if (await moznaOpuscicDzien()) { zamknijSzuflade(); pokaz(p.dataset.widok); } }));
$$('#motyw button').forEach((b) => b.addEventListener('click', () => zmienProgram('motyw', b.dataset.motyw).then(() => widok === 'ustawienia' && rysujUstawienia())));

function nowyStan(s) {
  if (!s) return;
  STAN = s;
  if (s.ok === false && s.blad) toast(esc(s.blad), 'blad');
  WPISY = [];
  odswiezDol();
  if (widok === 'pulpit') rysujPulpit();
}

// ------------------------------------------------------------------ pliki
async function wybierzRcp() { const s = await api('wybierz_plik_rcp'); if (s) { PRACOWNICY = (await api('pracownicy')) || PRACOWNICY; nowyStan(s); if (widok !== 'pulpit') pokaz('pulpit'); } }
async function wybierzUrlopy() { const s = await api('wybierz_plik_urlopow'); if (s) nowyStan(s); }
window.poUpuszczeniu = async (s) => {
  $('#nakladka-upusc').classList.add('ukryty');
  PRACOWNICY = (await api('pracownicy')) || PRACOWNICY;
  nowyStan(s);
  if (s?.ok !== false && widok !== 'pulpit') pokaz('pulpit');
};
let licznikPrzeciagania = 0;
document.addEventListener('dragenter', (e) => { e.preventDefault(); licznikPrzeciagania++; $('#nakladka-upusc').classList.remove('ukryty'); });
document.addEventListener('dragleave', () => { if (--licznikPrzeciagania <= 0) { licznikPrzeciagania = 0; $('#nakladka-upusc').classList.add('ukryty'); } });
document.addEventListener('dragover', (e) => e.preventDefault());
document.addEventListener('drop', (e) => { e.preventDefault(); licznikPrzeciagania = 0; $('#nakladka-upusc').classList.add('ukryty'); });

// ------------------------------------------------------------------ pulpit
function dataKr(d) { const [r, m, dz] = d.split('.'); return `${dz}.${m}`; }
function dzienTyg(d, krotki = true) { const [r, m, dz] = d.split('.').map(Number); return (krotki ? DNI_KR : DNI)[new Date(r, m - 1, dz).getDay()]; }
function zmianaKr(t) { return { 'Zmiana 1': 'I zmiana', 'Zmiana 2': 'II zmiana', 'godziny ruchome': 'ruchome', '---': '–' }[t] || String(t || '').replace('Sztywna ', ''); }
function tagi(uwaga) {
  return uwaga.split(',').map((u) => u.trim()).filter(Boolean).map((u) => {
    const r = u === 'Nieobecność' ? 'nieobecnosc' : u.startsWith('Ostrzeżenie') ? 'ostrzezenie' : u.startsWith('Niepełne') ? 'niepelny' : 'blad';
    return `<span class="tag ${r}">${esc(u.replace('Ostrzeżenie: ', ''))}</span>`;
  }).join('');
}

function widoczneAnomalie() {
  const q = filtr.szukaj.trim().toLowerCase();
  let l = (STAN?.anomalie || []).filter((a) => filtr.rodzaje.has(a.rodzaj) && (!filtr.dzialy.size || filtr.dzialy.has(a.dzial))
    && (!filtr.ukryjSprawdzone || !a.status) && (!q || a.pracownik.includes(q) || a.nazwisko.toLowerCase().includes(q) || a.uwaga.toLowerCase().includes(q) || dataKr(a.data).includes(q)));
  if (filtr.sort) {
    const [pole, kier] = filtr.sort.split(':');
    l = [...l].sort((a, b) => String(a[pole]).localeCompare(String(b[pole]), 'pl') * (kier === 'd' ? -1 : 1) || a.data.localeCompare(b.data));
  }
  return l;
}

function rysujPulpit() {
  const el = $('#widok-pulpit');
  const s = STAN;
  if (!s?.rcp) {
    el.classList.remove('stala');
    el.innerHTML = `
      <div class="upusc duze" id="pulpit-upusc">
        <div class="ikona">${ik('upusc')}</div>
        <h2>Przeciągnij tutaj plik z Roger RCP</h2>
        <p>Plik tekstowy z odbiciami (data.godzina;numer;kod) - możesz od razu dorzucić plan nieobecności z Excela.</p>
        <div class="przyciski"><button class="btn btn-hr" id="p-rcp">${ik('plik')} Wybierz plik RCP</button><button class="btn" id="p-urlopy">${ik('kalendarz')} Plan nieobecności${s?.urlopy ? ' ✓' : ''}</button></div>
        <div class="skroty"><span><kbd>Ctrl</kbd>+<kbd>O</kbd> otwórz plik</span><span><kbd>Ctrl</kbd>+<kbd>S</kbd> zapisz dla ERP</span><span><kbd>F5</kbd> przetwórz ponownie</span><span><kbd>Enter</kbd> zatwierdź dzień</span></div>
      </div>
      <div id="pulpit-ostatnie"></div>`;
    $('#p-rcp').onclick = wybierzRcp;
    $('#p-urlopy').onclick = wybierzUrlopy;
    api('historia').then((h) => {
      const ost = (h || []).filter((w) => w.istnieje).slice(0, 3);
      if (!ost.length || !$('#pulpit-ostatnie')) return;
      $('#pulpit-ostatnie').innerHTML = `<div class="eyebrow" style="margin:4px 0 10px">Ostatnio przetwarzane</div><div class="siatka k3">${ost.map((w) => `
        <button class="karta plik" style="text-align:left; cursor:pointer" data-hist="${esc(w.id)}"><span class="ikona">${ik('plik')}</span>
          <span class="opis-pliku"><b>${esc(w.plik.split(/[\\/]/).pop())}</b><span>${esc(w.kiedy)} · ${esc(w.okres.replaceAll('.', '-'))}</span></span></button>`).join('')}</div>`;
      $$('[data-hist]').forEach((b) => b.onclick = () => otworzZHistorii(b.dataset.hist));
    });
    return;
  }
  const st = s.statystyki;
  const wszystkie = st.do_sprawdzenia + st.sprawdzone;
  const licz = (r) => s.anomalie.filter((a) => a.rodzaj === r).length;
  el.classList.add('stala');
  el.innerHTML = `
    <div class="siatka k2">
      <div class="karta plik"><span class="ikona">${ik('plik')}</span><div class="opis-pliku"><b title="${esc(s.rcp.sciezka)}">${esc(s.rcp.nazwa)}</b>
        <span>Roger RCP · ${liczba(st.zdarzen)} zdarzeń · ${dataKr(st.od)} – ${dataKr(st.do)}.${st.do.slice(0, 4)}</span></div>
        <button class="btn btn-maly" id="p-rcp" title="Ctrl+O">Zmień</button></div>
      ${s.urlopy ? `<div class="karta plik"><span class="ikona">${ik('kalendarz')}</span><div class="opis-pliku"><b title="${esc(s.urlopy.sciezka)}">${esc(s.urlopy.nazwa)}</b>
        <span>Plan nieobecności · ${liczba(s.urlopy.dni)} dni u ${liczba(s.urlopy.pracownikow)} osób</span></div><button class="btn btn-maly" id="p-urlopy">Zmień</button></div>`
      : `<div class="karta plik pusty" id="p-urlopy"><span class="ikona">${ik('kalendarz')}</span><div class="opis-pliku"><b>Dodaj plan nieobecności</b>
        <span>Excel (.xls/.xlsx) - dni urlopów nie będą zgłaszane jako nieobecności</span></div>${ik('plus')}</div>`}
    </div>
    <div class="siatka k4">
      <div class="karta stat"><b>${liczba(st.pracownikow)}</b><span>pracowników w pliku</span></div>
      <div class="karta stat zielony"><b>${liczba(st.w_pliku_erp)}</b><span>zdarzeń do pliku ERP${st.usuniete ? ` · ${liczba(st.usuniete)} usuniętych (duplikaty, przerwy)` : ''}</span></div>
      <div class="karta stat zolty"><b>${liczba(st.skorygowane)}</b><span>odbić z godziną poprawioną automatycznie</span></div>
      <div class="karta stat ${st.do_sprawdzenia ? 'czerwony' : 'zielony'}"><b>${liczba(st.do_sprawdzenia)}</b><span>do sprawdzenia · ${liczba(st.sprawdzone)} z ${liczba(wszystkie)} gotowe</span>
        <div class="postep"><i style="width:${wszystkie ? Math.round(100 * (wszystkie - st.do_sprawdzenia) / wszystkie) : 100}%"></i></div></div>
    </div>
    <section class="karta lista">
      <div class="naglowek">
        <div class="segment tryb-listy">
          <button data-tryb="problemy" class="${filtr.tryb === 'problemy' ? 'akt' : ''}">Do sprawdzenia <b>${liczba(st.do_sprawdzenia)}</b></button>
          <button data-tryb="wszystkie" class="${filtr.tryb === 'wszystkie' ? 'akt' : ''}" title="Wszystkie dni pracy w pliku dla ERP - także bez problemów">Wszystkie wpisy</button>
        </div>
        <div class="rozwijane wyrozniony" id="f-dzialy"><button class="pole" id="f-dzialy-przycisk">${ik('ludzie')}<span>${opisDzialow(s.dzialy)}</span></button></div>
        <div class="filtry ${filtr.tryb === 'wszystkie' ? 'ukryty' : ''}">${Object.entries(RODZAJE).map(([r, n]) => `<button class="znacznik ${filtr.rodzaje.has(r) ? 'akt' : ''} ${licz(r) ? '' : 'zero'}" data-rodzaj="${r}"><span class="kropka ${r}"></span>${n} <b>${licz(r)}</b></button>`).join('')}</div>
        <div class="szukaj">
          <input class="pole" id="f-szukaj" placeholder="Szukaj…  (Ctrl+F)" value="${esc(filtr.szukaj)}" style="width:230px">
          <button class="znacznik ${filtr.ukryjSprawdzone ? 'akt' : ''} ${filtr.tryb === 'wszystkie' ? 'ukryty' : ''}" id="f-sprawdzone" title="Ukryj sprawdzone">${ik('ok')} Ukryj gotowe</button>
        </div>
      </div>
      <div class="przewijana" id="lista-przewijana"></div>
    </section>
    <div class="akcje-dol">
      <button class="btn rozciagnij" id="p-przetworz" title="F5">${ik('odswiez')} Przetwórz ponownie z bieżącymi regułami${s.reczne ? ` <span class="podp">(${s.reczne} ${odmiana(s.reczne, 'ręczna korekta zostaje', 'ręczne korekty zostają', 'ręcznych korekt zostaje')})</span>` : ''}</button>
      <button class="btn" id="p-dodaj">${ik('plus')} Dodaj zdarzenie ręcznie</button>
    </div>
    <div class="koniec">
      <button class="btn btn-hr duzy" id="p-zapisz" title="Ctrl+S">${ik('pobierz')} Zapisz plik do importu w Comarch ERP XL</button>
      ${INFO.program.eksport_pdf ? `<button class="btn btn-raport" id="p-pdf">${ik('plik')} Raport PDF</button>` : ''}
      ${INFO.program.eksport_txt ? `<button class="btn btn-raport" id="p-txt">${ik('plik')} Raport TXT</button>` : ''}
    </div>`;
  if (s.zmienione_reguly) $('#pasek-prawe').innerHTML = `<button class="btn btn-maly btn-bez" id="pasek-reguly"><span class="tag niepelny">● ${s.zmienione_reguly} ${odmiana(s.zmienione_reguly, 'reguła zmieniona', 'reguły zmienione', 'reguł zmienionych')} lokalnie</span></button>`;
  $('#pasek-reguly')?.addEventListener('click', () => pokaz('reguly'));
  rysujListe();
  $('#p-rcp').onclick = wybierzRcp;
  $('#p-urlopy').onclick = wybierzUrlopy;
  $('#p-przetworz').onclick = przetworz;
  $('#p-dodaj').onclick = () => dodajZdarzenieRecznie();
  $$('[data-tryb]').forEach((b) => b.onclick = () => { filtr.tryb = b.dataset.tryb; rysujPulpit(); });
  $('#p-zapisz').onclick = () => zapiszErp();
  $('#p-pdf')?.addEventListener('click', () => eksport('pdf'));
  $('#p-txt')?.addEventListener('click', () => eksport('txt'));
  $$('[data-rodzaj]').forEach((b) => b.onclick = () => { filtr.rodzaje.has(b.dataset.rodzaj) ? filtr.rodzaje.delete(b.dataset.rodzaj) : filtr.rodzaje.add(b.dataset.rodzaj); b.classList.toggle('akt'); rysujListe(); });
  $('#f-dzialy-przycisk').onclick = (e) => { e.stopPropagation(); przelaczListeDzialow(s); };
  $('#f-szukaj').oninput = (e) => { filtr.szukaj = e.target.value; rysujListe(); };
  $('#f-sprawdzone').onclick = (e) => { filtr.ukryjSprawdzone = !filtr.ukryjSprawdzone; e.currentTarget.classList.toggle('akt'); rysujListe(); };
}

function opisDzialow(wszystkie) {
  const n = [...filtr.dzialy].filter((d) => wszystkie.includes(d)).length;
  return !n || n === wszystkie.length ? 'Wszystkie działy' : n === 1 ? esc([...filtr.dzialy].find((d) => wszystkie.includes(d))) : `Działy: ${n} z ${wszystkie.length}`;
}

function przelaczListeDzialow(s) {
  const box = $('#f-dzialy');
  const otwarta = $('.panel-listy', box);
  if (otwarta) return otwarta.remove();
  const ile = (d) => (filtr.tryb === 'wszystkie' ? WPISY.filter((w) => w.dzial === d) : s.anomalie.filter((a) => a.dzial === d && filtr.rodzaje.has(a.rodzaj))).length;
  const panel = document.createElement('div');
  panel.className = 'panel-listy lewa';
  panel.innerHTML = `<div class="gora-listy"><button class="btn btn-maly" data-dz="wszystkie">Wszystkie</button><button class="btn btn-maly btn-bez" data-dz="zaden">Odznacz</button></div>
    ${s.dzialy.map((d) => `<label><input type="checkbox" value="${esc(d)}" ${!filtr.dzialy.size || filtr.dzialy.has(d) ? 'checked' : ''}>${esc(d)}<small>${ile(d)}</small></label>`).join('')}`;
  panel.addEventListener('click', (e) => e.stopPropagation());
  const zastosuj = () => {
    const zazn = $$('input', panel).filter((c) => c.checked).map((c) => c.value);
    filtr.dzialy = zazn.length === s.dzialy.length ? new Set() : new Set(zazn.length ? zazn : ['\u0000']);
    $('#f-dzialy-przycisk span').innerHTML = zazn.length ? opisDzialow(s.dzialy) : 'Żaden dział';
    rysujListe();
  };
  $$('input', panel).forEach((c) => c.onchange = zastosuj);
  $$('[data-dz]', panel).forEach((b) => b.onclick = () => { $$('input', panel).forEach((c) => c.checked = b.dataset.dz === 'wszystkie'); zastosuj(); });
  box.append(panel);
}
document.addEventListener('click', () => $('#f-dzialy .panel-listy')?.remove());

function rysujListe() {
  const box = $('#lista-przewijana');
  if (!box) return;
  if (filtr.tryb === 'wszystkie') return rysujWszystkieWpisy(box);
  const l = widoczneAnomalie();
  const kol = [['status', ''], ['data', 'Dzień'], ['pracownik', 'Nr'], ['nazwisko', 'Pracownik'], ['dzial', 'Dział'], ['typ_zmiany', 'Zmiana'], ['uwaga', 'Problem']];
  const strz = (p) => filtr.sort.startsWith(p + ':') ? (filtr.sort.endsWith(':d') ? ' ↓' : ' ↑') : '';
  if (!l.length) {
    box.innerHTML = `<div class="pusto">${STAN.anomalie.length ? 'Brak pozycji dla wybranych filtrów.' : 'Nie znaleziono problemów - plik jest gotowy do zapisu.'}</div>`;
    return;
  }
  box.innerHTML = `<table class="tab"><thead><tr>${kol.map(([p, n]) => `<th data-sort="${p}">${n}${strz(p)}</th>`).join('')}<th></th></tr></thead><tbody>
    ${l.map((a) => `<tr data-id="${esc(a.id)}" class="${a.status ? 'sprawdzony' : ''} ${a.id === wybranyId ? 'wybrany' : ''}">
      <td>${a.status === 'sprawdzone' ? `<span class="stan-ikona ok" title="Sprawdzone">${ik('ok')}</span>` : a.status ? `<span class="stan-ikona pom" title="Pominięte">–</span>` : '<span class="stan-ikona"></span>'}</td>
      <td class="data">${dataKr(a.data)}<small>${dzienTyg(a.data)}</small></td><td class="nr">${esc(a.pracownik)}</td>
      <td class="nazwisko">${esc(a.nazwisko)}</td><td class="dzial" title="${esc(a.dzial)}">${esc(a.dzial)}</td><td class="zmiana">${esc(zmianaKr(a.typ_zmiany))}</td>
      <td>${tagi(a.uwaga)}${a.reczna ? '<span class="tag reczna">poprawione ręcznie</span>' : ''}</td>
      <td style="text-align:right"><button class="btn btn-maly">Popraw</button></td></tr>`).join('')}</tbody></table>`;
  $$('tbody tr', box).forEach((tr) => tr.onclick = () => otworzDzien(tr.dataset.id));
  $$('th[data-sort]', box).forEach((th) => th.onclick = () => {
    const p = th.dataset.sort;
    filtr.sort = filtr.sort === `${p}:r` ? `${p}:d` : filtr.sort === `${p}:d` ? '' : `${p}:r`;
    rysujListe();
  });
}

async function przetworz() {
  const s = await api('przetworz');
  nowyStan(s);
  if (s?.statystyki) toast('Przetworzono ponownie z bieżącymi regułami.', 'ok', null, 2500);
}

// ------------------------------------------------------------------ korekta dnia (panel z prawej)
const doMin = (c) => { const [g, m] = c.split(':').map(Number); return g * 60 + m; };
const zMin = (m) => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
const naWidok = (c) => { const [g, m] = c.split(':').map(Number); return { hm: `${String(g % 24).padStart(2, '0')}:${String(m).padStart(2, '0')}`, plus1: g >= 24 }; };

async function otworzDzien(id, kolejka = null, sprawdz = true) {
  if (sprawdz && szuflada && szuflada.d.id !== id && !(await moznaOpuscicDzien())) return;
  const d = await api('dzien', id);
  if (!d) return;
  wybranyId = id;
  szuflada = { d, z: d.zdarzenia.map((z) => ({ czas: z.czas, kod: z.kod, czas_oryg: z.czas_oryg })), kolejka: kolejka || widoczneAnomalie().map((a) => a.id) };
  $$('#lista-przewijana tr').forEach((tr) => tr.classList.toggle('wybrany', tr.dataset.id === id));
  $(`#lista-przewijana tr[data-id="${CSS.escape(id)}"]`)?.scrollIntoView({ block: 'nearest' });
  rysujSzuflade();
}

function zamknijSzuflade() { szuflada = null; $('#szuflada-miejsce').innerHTML = ''; }

// Przed zamknięciem panelu albo przejściem do innego dnia: zmiany nie mogą zniknąć bez pytania.
// Zwraca true, gdy można iść dalej (zapisano albo porzucono), false = zostań w edycji.
async function moznaOpuscicDzien() {
  if (!szuflada) return true;
  $$('.zdarz[data-i]').forEach((w) => w.czytaj?.());
  if (!zmienione()) return true;
  const w = await modal({
    tytul: `${ik('uwaga')} Niezapisane zmiany`,
    tresc: `<p>W dniu <b>${esc(szuflada.d.nazwisko)}</b> (${dataKr(szuflada.d.data)}) są zmiany, które nie zostały zapisane.</p>`,
    przyciski: [{ tekst: 'Wróć do edycji', wartosc: null, domyslny: true }, { tekst: 'Porzuć zmiany', klasa: 'btn-czerwony', wartosc: 'porzuc' },
      { tekst: 'Zapisz zmiany', klasa: 'btn-hr', wartosc: 'zapisz' }],
  });
  if (w === 'zapisz') {
    if (!$$('.zdarz[data-i]').every((r) => r.czytaj())) { toast('Popraw godzinę w formacie GG:MM.', 'blad'); return false; }
    const s = await api('zapisz_dzien', szuflada.d.id, szuflada.z, 'sprawdzone');
    if (!s) return false;
    nowyStan(s);
    return true;
  }
  return w === 'porzuc';
}
async function zamknijSzufladePytaj() { if (await moznaOpuscicDzien()) zamknijSzuflade(); }

// Godziny zmiany z typu zmiany ('Zmiana 1', 'Sztywna 06:00-14:00') albo null (godziny ruchome)
function godzinyZmiany(typ) {
  const zm = { 'Zmiana 1': ['06:00', '14:00'], 'Zmiana 2': ['14:00', '22:00'] }[typ] || (String(typ).startsWith('Sztywna ') ? typ.slice(8).split('-') : null);
  return zm ? [doMin(zm[0]), zm[1] === '00:00' ? 1440 : doMin(zm[1])] : null;
}

// Nowe zdarzenie w sensownym miejscu: brak wejścia -> wejście przed pierwszym wyjściem, brak wyjścia -> wyjście po ostatnim wejściu
function noweZdarzenie(z, d) {
  const zm = godzinyZmiany(d.typ_zmiany);
  const wej = z.filter((e) => e.kod === '00'), wyj = z.filter((e) => e.kod === '16' || e.kod === '25');
  if (!z.length) return { czas: zMin(zm ? zm[0] : 360), kod: '00', czas_oryg: '' };
  if (!wej.length && wyj.length) {
    const pierwsze = doMin(wyj[0].czas);
    return { czas: zMin(zm && zm[0] < pierwsze ? zm[0] : Math.max(0, pierwsze - d.wymiar)), kod: '00', czas_oryg: '' };
  }
  const ost = z[z.length - 1];
  if (ost.kod === '00') {
    const od = doMin(ost.czas);
    return { czas: zMin(zm && zm[1] > od ? zm[1] : od + d.wymiar), kod: '16', czas_oryg: '' };
  }
  return { czas: zMin(Math.min(doMin(ost.czas) + 30, 47 * 60)), kod: '00', czas_oryg: '' };
}
const sortujZdarzenia = (z) => z.sort((a, b) => doMin(a.czas) - doMin(b.czas));

function zmienione() {
  const a = JSON.stringify(szuflada.d.zdarzenia.map((z) => [z.czas, z.kod]));
  const b = JSON.stringify([...szuflada.z].sort((x, y) => doMin(x.czas) - doMin(y.czas)).map((z) => [z.czas, z.kod]));
  return a !== b;
}

function rysujOs(zd, d) {
  const koniec = Math.max(24 * 60, ...zd.map((z) => doMin(z.czas) + 60));
  const skala = Math.ceil(koniec / 360) * 360;
  const proc = (m) => `${(100 * m / skala).toFixed(2)}%`;
  let html = '';
  const zm = godzinyZmiany(d.typ_zmiany);
  if (zm) html += `<div class="zmiana" style="left:${proc(zm[0])}; width:${proc(zm[1] - zm[0])}" title="Zmiana ${zMin(zm[0])}-${zMin(zm[1] % 1440)}"></div>`;
  let wej = null;
  const posort = [...zd].sort((a, b) => doMin(a.czas) - doMin(b.czas));
  for (const z of posort) {
    if (z.kod === '00') { if (wej === null) wej = doMin(z.czas); }
    else if ((z.kod === '16' || z.kod === '25') && wej !== null) { html += `<div class="praca" style="left:${proc(wej)}; width:${proc(doMin(z.czas) - wej)}"></div>`; wej = null; }
  }
  if (wej !== null) html += `<div class="brak" style="left:${proc(wej)}; width:${proc(Math.min(d.wymiar, skala - wej))}" title="Brak wyjścia"></div>`;
  if (posort.length && posort[0].kod !== '00' && !posort.some((z) => z.kod === '00')) {
    const w = doMin(posort[0].czas);
    html += `<div class="brak" style="left:${proc(Math.max(0, w - d.wymiar))}; width:${proc(Math.min(d.wymiar, w))}" title="Brak wejścia"></div>`;
  }
  html += posort.map((z) => `<div class="punkt k${z.kod}" style="left:${proc(doMin(z.czas))}" title="${KODY[z.kod] || z.kod} ${naWidok(z.czas).hm}"></div>`).join('');
  for (let g = 0; g <= skala / 60; g += 6) html += `<span class="godz" style="left:${proc(g * 60)}">${String(g % 24).padStart(2, '0')}${g >= 24 ? '⁺' : ''}</span>`;
  return `<div class="os">${html}</div>`;
}

function rysujSzuflade() {
  const { d, z } = szuflada;
  const oryg = new Set(d.zdarzenia.map((e) => `${e.czas}|${e.kod}`));
  const [r, m, dz] = d.data.split('.');
  const poz = szuflada.kolejka.indexOf(d.id);
  $('#szuflada-miejsce').innerHTML = `<div class="zaciemnienie" id="sz-tlo"></div>
    <aside class="szuflada" role="dialog">
      <div class="gora">
        <div><span class="eyebrow">Korekta dnia${poz >= 0 ? ` · ${poz + 1} z ${szuflada.kolejka.length}` : ''}</span>
          <h2>${esc(d.nazwisko)} · <span class="mono">${esc(d.nr)}</span></h2>
          <div class="podp">${esc(d.dzial)} · ${dzienTyg(d.data, false)} ${dz}.${m}.${r} · ${esc(zmianaKr(d.typ_zmiany))} · etat ${d.wymiar / 60}h</div></div>
        <button class="btn btn-ikona btn-bez" id="sz-zamknij" title="Zamknij (Esc)">${ik('x')}</button>
      </div>
      <div class="tresc-szuflady">
        ${d.uwaga ? `<div class="komunikat">${tagi(d.uwaga)}${d.reczna ? '<span class="tag reczna">poprawione ręcznie</span>' : ''}</div>` : `<div class="komunikat"><span class="tag reczna">bez uwag</span><span class="podp">Dzień bez wykrytych problemów</span></div>`}
        <div><div class="podp" style="margin-bottom:6px">Oś dnia</div>${rysujOs(z, d)}</div>
        <div class="zdarzenia">
          ${z.length ? '' : '<div class="pusto" style="padding:14px">Brak zdarzeń w tym dniu.</div>'}
          ${z.map((e, i) => {
            const w = naWidok(e.czas);
            const nowe = !oryg.has(`${e.czas}|${e.kod}`);
            return `<div class="zdarz ${nowe ? (e.czas_oryg ? 'zmienione' : 'nowe') : ''}" data-i="${i}">
              <input class="pole" value="${w.hm}" data-pole="czas" maxlength="5" spellcheck="false">
              <label class="plus1" title="Po północy (następny dzień)"><input type="checkbox" data-pole="plus1" ${w.plus1 ? 'checked' : ''}>+1d</label>
              <div style="display:flex; align-items:center; gap:8px; min-width:0"><select class="pole" data-pole="kod">${Object.entries(KODY).map(([k, n]) => `<option value="${k}" ${k === e.kod ? 'selected' : ''}>${n} (${k})</option>`).join('')}</select>
                <span class="oryg">${e.czas_oryg && e.czas_oryg !== e.czas ? `z RCP ${naWidok(e.czas_oryg).hm}` : e.czas_oryg ? '' : 'dodane'}</span></div>
              <span class="przesun"><button class="btn btn-bez" data-gora="${i}" ${i ? '' : 'disabled'} title="Zamień z wyższym (rodzaj zdarzenia)">▲</button><button class="btn btn-bez" data-dol="${i}" ${i < z.length - 1 ? '' : 'disabled'} title="Zamień z niższym (rodzaj zdarzenia)">▼</button></span>
              <button class="btn btn-ikona btn-bez btn-czerwony" data-usun="${i}" title="Usuń zdarzenie">${ik('kosz')}</button></div>`;
          }).join('')}
          ${(zmienione() ? [] : d.propozycje).map((p, i) => `<div class="zdarz propozycja"><span>${ik('info')} <b>Propozycja:</b> ${esc(p.opis)}</span><button class="btn btn-hr btn-maly" data-prop="${i}">Zastosuj</button></div>`).join('')}
        </div>
        <button class="btn btn-maly" id="sz-dodaj">${ik('plus')} Dodaj zdarzenie (wejście, wyjście, przerwa, przepustka)</button>
        <div class="podp" style="margin-top:-6px">Zdarzenia układają się same według godziny - po zmianie godziny wpis przesuwa się na właściwe miejsce. ▲▼ zamienia rodzaje zdarzeń z sąsiednim wpisem.</div>
        ${d.reczna ? `<button class="btn btn-maly btn-bez" id="sz-cofnij">${ik('wstecz')} Cofnij ręczną korektę (wróć do wyniku z reguł)</button>` : ''}
      </div>
      <div class="stopka-szuflady">
        <button class="btn" style="flex:1" id="sz-pomin" title="Następny bez oznaczania">Pomiń</button>
        <button class="btn btn-hr" style="flex:2" id="sz-zatwierdz" title="Enter">${zmienione() ? 'Zapisz zmiany i następny' : 'Zatwierdź i następny'} ${ik('dalej')}</button>
      </div>
    </aside>`;
  $('#sz-tlo').onclick = zamknijSzufladePytaj;
  $('#sz-zamknij').onclick = zamknijSzufladePytaj;
  $('#sz-pomin').onclick = async () => { if (await moznaOpuscicDzien()) nastepny(false); };
  $('#sz-zatwierdz').onclick = zatwierdzDzien;
  $('#sz-dodaj').onclick = () => {
    const nowe = noweZdarzenie(z, d);
    z.push(nowe);
    sortujZdarzenia(z);
    rysujSzuflade();
    $(`.zdarz[data-i="${z.indexOf(nowe)}"] input[data-pole="czas"]`)?.select();
  };
  const zamien = (i, j) => { const k = z[i].kod; z[i].kod = z[j].kod; z[j].kod = k; rysujSzuflade(); };
  $$('[data-gora]').forEach((b) => b.onclick = () => zamien(+b.dataset.gora, +b.dataset.gora - 1));
  $$('[data-dol]').forEach((b) => b.onclick = () => zamien(+b.dataset.dol, +b.dataset.dol + 1));
  $('#sz-cofnij')?.addEventListener('click', async () => { nowyStan(await api('cofnij_reczna', d.id)); otworzDzien(d.id, szuflada.kolejka, false); });
  $$('[data-usun]').forEach((b) => b.onclick = () => { z.splice(+b.dataset.usun, 1); rysujSzuflade(); });
  $$('[data-prop]').forEach((b) => b.onclick = () => {
    const p = d.propozycje[+b.dataset.prop];
    if (p.akcja === 'dodaj') z.push({ czas: p.czas, kod: p.kod, czas_oryg: '' });
    if (p.akcja === 'usun') z.splice(p.indeks, 1);
    z.sort((a, b) => doMin(a.czas) - doMin(b.czas));
    d.propozycje = [];
    rysujSzuflade();
  });
  $$('.zdarz[data-i]').forEach((w) => {
    const i = +w.dataset.i;
    const czytaj = () => {
      const hm = $('[data-pole="czas"]', w).value.trim();
      const ok = /^([01]\d|2[0-3]):[0-5]\d$/.test(hm);
      $('[data-pole="czas"]', w).style.borderColor = ok ? '' : 'var(--czerwony)';
      if (!ok) return false;
      const [g, mm] = hm.split(':').map(Number);
      z[i].czas = zMin((g + ($('[data-pole="plus1"]', w).checked ? 24 : 0)) * 60 + mm);
      z[i].kod = $('[data-pole="kod"]', w).value;
      return true;
    };
    const poZmianie = () => {
      if (!czytaj()) return;
      const e = z[i];
      sortujZdarzenia(z);
      rysujSzuflade();
      $(`.zdarz[data-i="${z.indexOf(e)}"]`)?.animate([{ background: 'color-mix(in srgb, var(--kolor-2) 25%, transparent)' }, {}], 700);
    };
    $('[data-pole="czas"]', w).addEventListener('change', poZmianie);
    $('[data-pole="plus1"]', w).addEventListener('change', poZmianie);
    $('[data-pole="kod"]', w).addEventListener('change', poZmianie);
    w.czytaj = czytaj;
  });
}

async function zatwierdzDzien() {
  if (!szuflada) return;
  const wiersze = $$('.zdarz[data-i]');
  if (!wiersze.every((w) => w.czytaj())) return toast('Popraw godzinę w formacie GG:MM (00:00 - 23:59).', 'blad');
  const { d, z } = szuflada;
  const s = zmienione() ? await api('zapisz_dzien', d.id, z, 'sprawdzone') : await api('oznacz', d.id, 'sprawdzone');
  if (!s) return;
  nowyStan(s);
  nastepny(true);
}

function nastepny(poZatwierdzeniu) {
  const { d, kolejka } = szuflada;
  const status = new Map(STAN.anomalie.map((a) => [a.id, a.status]));
  const od = kolejka.indexOf(d.id);
  const dalej = [...kolejka.slice(od + 1), ...kolejka.slice(0, Math.max(od, 0))].find((id) => status.has(id) && !status.get(id));
  if (dalej) return otworzDzien(dalej, kolejka.includes(dalej) && widoczneAnomalie().some((a) => a.id === dalej) ? null : kolejka, false);
  zamknijSzuflade();
  if (poZatwierdzeniu) toast('Wszystkie pozycje z listy są sprawdzone. Możesz zapisać plik dla ERP.', 'ok', { tekst: 'Zapisz', fn: () => zapiszErp() });
}

async function dodajZdarzenieRecznie(nr = '', data = '') {
  const daty = [...new Set(WPISY.length ? WPISY.map((w) => w.data) : STAN.anomalie.map((a) => a.data))].sort();
  const w = await modal({
    tytul: `${ik('plus')} Dodaj zdarzenie ręcznie`,
    tresc: `<p class="podp">Dla pracownika, którego nie ma w pliku RCP w danym dniu (np. zapomniał odbić kartę).</p>
      <div style="display:grid; gap:12px; grid-template-columns: 1fr 1fr">
        <div style="grid-column: span 2"><label class="etykieta">Pracownik</label><input class="pole" id="d-prac" list="d-lista" style="width:100%" value="${esc(nr)}" placeholder="numer albo nazwisko">
          <datalist id="d-lista">${PRACOWNICY.map((p) => `<option value="${esc(p.nr)}">${esc(p.nazwisko)}</option>`).join('')}</datalist></div>
        <div><label class="etykieta">Dzień</label><input class="pole mono" id="d-data" style="width:100%" value="${esc(data || daty[0] || '')}" placeholder="RRRR.MM.DD"></div>
        <div><label class="etykieta">Godzina i rodzaj</label><div style="display:flex; gap:8px"><input class="pole mono waski" id="d-czas" value="06:00">
          <select class="pole" id="d-kod">${Object.entries(KODY).map(([k, n]) => `<option value="${k}">${n} (${k})</option>`).join('')}</select></div></div>
      </div>`,
    przyciski: [{ tekst: 'Anuluj', wartosc: null }, { tekst: 'Dodaj i otwórz dzień', klasa: 'btn-hr', wartosc: 'tak' }],
    poOtwarciu: (el) => { el._dane = () => ({ prac: $('#d-prac', el).value.trim(), data: $('#d-data', el).value.trim(), czas: $('#d-czas', el).value.trim(), kod: $('#d-kod', el).value }); window._dodaj = el; },
  });
  const f = window._dodaj._dane();
  if (w !== 'tak') return;
  const p = PRACOWNICY.find((x) => x.nr === f.prac || x.nazwisko.toLowerCase() === f.prac.toLowerCase()) || (/^\d{4}$/.test(f.prac) ? { nr: f.prac } : null);
  if (!p) return toast('Nie znaleziono pracownika - wpisz 4-cyfrowy numer.', 'blad');
  if (!/^\d{4}\.\d{2}\.\d{2}$/.test(f.data)) return toast('Dzień w formacie RRRR.MM.DD.', 'blad');
  if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(f.czas)) return toast('Godzina w formacie GG:MM.', 'blad');
  const s = await api('dodaj_zdarzenie', p.nr, f.data, f.czas, f.kod);
  if (s?.ok === false) return toast(esc(s.blad), 'blad');
  nowyStan(s);
  otworzDzien(`${f.data}|${p.nr}`);
}

// ------------------------------------------------------------------ zapis i raporty
async function zapiszErp(tryb = null) {
  if (!STAN?.rcp) return toast('Najpierw wczytaj plik RCP.');
  await api('ustaw_filtr_raportu', [...filtr.rodzaje], [...filtr.dzialy]);
  const r = await api('zapisz_erp', tryb);
  if (!r) return;
  if (r.pytanie) {
    const wybor = await modal({
      tytul: `${ik('uwaga')} Zostały niesprawdzone pozycje`,
      tresc: `<p>Na liście są jeszcze <b>${r.bledy} błędów</b> i <b>${r.ostrzezenia} ostrzeżeń</b> (np. niepełne godziny), których nie oznaczono jako sprawdzone.</p>
        <div class="wybor">
          <button class="domyslny" data-wybor="wroc"><b>Wróć do listy</b><span>Popraw pozostałe pozycje przed zapisem (zalecane).</span></button>
          <button data-wybor="wszystko"><b>Zapisz z niepoprawionymi wpisami</b><span>Plik zawiera wszystkie wpisy - również te błędne.</span></button>
          ${r.bledy ? `<button data-wybor="pomin"><b>Pomiń niepoprawione dni</b><span>${r.bledy} dni z błędami nie trafi do pliku ERP - zostaną wypisane w raporcie, do uzupełnienia w ERP ręcznie.</span></button>` : ''}
        </div>`,
    });
    if (wybor === 'wszystko' || wybor === 'pomin') return zapiszErp(wybor);
    if (wybor === 'wroc') { filtr.ukryjSprawdzone = true; rysujPulpit(); }
    return;
  }
  if (!r.ok) return toast(esc(r.blad), 'blad');
  const nazwy = r.pliki.map((p) => esc(p.split(/[\\/]/).pop()));
  toast(`Zapisano: <b>${nazwy[0]}</b>${nazwy.length > 1 ? `<br><span class="podp">oraz ${nazwy.slice(1).join(', ')}</span>` : ''}<br><span class="podp">w folderze ${esc(r.pliki[0].replace(/[\\/][^\\/]*$/, ''))}</span>${r.pominieto ? `<br>Pominięto dni z błędami: ${r.pominieto}` : ''}`,
    'ok', INFO.program.otworz_folder ? null : { tekst: 'Pokaż w folderze', fn: () => api('otworz_folder', r.pliki[0]) }, 9000);
}

async function eksport(format) {
  await api('ustaw_filtr_raportu', [...filtr.rodzaje], [...filtr.dzialy]);
  const r = await api('eksport_raportu', format);
  if (r?.ok) toast(`Zapisano raport <b>${esc(r.plik.split(/[\\/]/).pop())}</b><br><span class="podp">${esc(r.plik.replace(/[\\/][^\\/]*$/, ''))}</span>`, 'ok', { tekst: 'Pokaż w folderze', fn: () => api('otworz_folder', r.plik) }, 8000);
  else if (r && !r.anulowano) toast(esc(r.blad), 'blad');
}

// ------------------------------------------------------------------ reguły korekty
const zakresGodz = (od, do_, krok) => { const w = []; for (let m = doMin(od); m <= doMin(do_); m += krok) w.push(zMin(m)); return w; };
const liczby = (...a) => a.map(String);
const zakresLiczb = (od, do_) => Array.from({ length: do_ - od + 1 }, (_, i) => String(od + i));
const KARTY = [
  { tytul: 'Detekcja zmian', ikona: 'zegar', opis: 'Wejścia poza tymi oknami = godziny ruchome', pola: [
    { et: 'Zmiana 1 - wejścia od / do', klucze: ['z1_od', 'z1_do'], opcje: [zakresGodz('04:00', '05:45', 15), zakresGodz('06:00', '06:45', 15)] },
    { et: 'Zmiana 2 - wejścia od / do', klucze: ['z2_od', 'z2_do'], opcje: [zakresGodz('12:00', '13:45', 15), zakresGodz('14:00', '14:45', 15)] },
    { et: 'Ruchome: zaokrąglaj sumę pracy', mala: 'i przesuwaj wejście / wyjście', przel: 'chk_flex' },
    { et: 'Stałe: ochrona wypracowanego etatu', mala: '8h / 7h', przel: 'chk_ochrona' },
  ] },
  { tytul: 'Wejścia (kod 00)', ikona: 'wej', opis: 'Zaokrąglanie godziny wejścia', pola: [
    { et: 'Zaokrąglanie wejść', przel: 'chk_wej' },
    { et: 'Kierunek', kier: 'wej_kierunek', zalezy: 'chk_wej' },
    { et: 'Do pełnych / tolerancja (min)', klucze: ['wej_minuty', 'wej_tol'], opcje: [liczby(5, 10, 15, 30), zakresLiczb(0, 5)], zalezy: 'chk_wej' },
    { et: 'Stałe: podbij do 06:00 od', przel: 'chk_zmiana1', klucze: ['zmiana1_czas'], opcje: [zakresGodz('05:00', '05:59', 1)] },
    { et: 'Stałe: podbij do 14:00 od', przel: 'chk_zmiana2', klucze: ['zmiana2_czas'], opcje: [zakresGodz('13:00', '13:59', 1)] },
  ] },
  { tytul: 'Wyjścia (kod 16)', ikona: 'wyj', opis: 'Zaokrąglanie godziny wyjścia', pola: [
    { et: 'Zaokrąglanie wyjść', przel: 'chk_wyj' },
    { et: 'Kierunek', kier: 'wyj_kierunek', zalezy: 'chk_wyj' },
    { et: 'Do pełnych / tolerancja (min)', klucze: ['wyj_minuty', 'wyj_tol'], opcje: [liczby(5, 10, 15, 30), zakresLiczb(0, 5)], zalezy: 'chk_wyj' },
  ] },
  { tytul: 'Duplikaty i pomyłki', ikona: 'kopia', opis: 'Podwójne odbicia i pomylone klawisze', pola: [
    { et: 'Usuwaj podwójne odbicia', przel: 'chk_duplikaty' },
    { et: 'Odstęp: wejście / wyjście (min)', klucze: ['dup_wej_min', 'dup_wyj_min'], opcje: [zakresLiczb(1, 30), zakresLiczb(1, 30)], zalezy: 'chk_duplikaty' },
    { et: 'Koryguj odwrotne odbicia do (min)', mala: 'pomyłka klawisza', przel: 'chk_pomylki', klucze: ['pomylki_min'], opcje: [zakresLiczb(1, 15)] },
  ] },
  { tytul: 'Nadgodziny', ikona: 'wykres', opis: 'Kiedy i jak naliczać nadgodziny', pola: [
    { et: 'Ignoruj krótsze niż (min)', przel: 'chk_nadgodziny', klucze: ['nadgodziny_min'], opcje: [liczby(0, 5, 10, 15, 30, 45, 60)] },
    { et: 'Naliczaj skokowo co (min)', przel: 'chk_nadgodziny_skok', klucze: ['nadgodziny_skok_min'], opcje: [liczby(15, 30, 45, 60)] },
    { et: 'Wyjątek dla działów', przel: 'chk_nadgodziny_wyjatek', dzialy: 'dzialy_wyjatek' },
    { et: 'Wyjątek: ignoruj / skok (min)', klucze: ['nadgodziny_wyjatek_min', 'nadgodziny_wyjatek_skok_min'], opcje: [liczby(0, 5, 10, 15, 30, 45, 60), liczby(0, 1, 5, 10, 15, 30, 45, 60)], zalezy: 'chk_nadgodziny_wyjatek' },
  ] },
  { tytul: 'Północ, przerwy, przepustki', ikona: 'ksiezyc', opis: 'Zmiana nocna i kody specjalne', pola: [
    { et: 'Nocna zmiana: przesuń do wczoraj wyjścia do', przel: 'chk_midnight', klucze: ['midnight_limit'], opcje: [zakresGodz('01:00', '09:00', 60)] },
    { et: 'Ostrzegaj o końcu pracy o północy', mala: 'wyjście o 00:00', przel: 'chk_ostrzegaj_polnoc' },
    { et: 'Usuń przerwę (kod 18)', mala: 'i powiązane z nią wejście', przel: 'chk_usun_18' },
    { et: 'Ostatnia przepustka (25) → wyjście (16)', przel: 'chk_przepustka' },
  ] },
];
const LISTY_PANELU = [['pracownicy_7h', 'Etat 7h'], ['pracownicy_6_14', 'Sztywna 06:00-14:00'], ['pracownicy_13_21', 'Sztywna 13:00-21:00'], ['pracownicy_8_16', 'Sztywna 08:00-16:00'], ['pracownicy_16_24', 'Sztywna 16:00-00:00']];
const numery = (t) => String(t || '').split(/[,;]/).map((x) => x.trim()).filter(Boolean);

function kluczePola(p) { return [p.przel, p.kier, p.dzialy, p.lista, ...(p.klucze || [])].filter(Boolean); }

function rysujPole(p) {
  const u = REG.aktualne;
  const lok = kluczePola(p).some((k) => k in REG.lokalne);
  const wyl = (p.zalezy && !u[p.zalezy]) || (p.przel && (p.klucze || p.dzialy) && !u[p.przel]);
  const firm = kluczePola(p).map((k) => `${k in REG.lokalne ? `firmowa: ${typeof REG.firmowe[k] === 'boolean' ? (REG.firmowe[k] ? 'włączone' : 'wyłączone') : REG.firmowe[k]}` : ''}`).filter(Boolean).join(', ');
  let wart = '';
  (p.klucze || []).forEach((k, i) => {
    const op = p.opcje[i].includes(String(u[k])) ? p.opcje[i] : [String(u[k]), ...p.opcje[i]];
    wart += `${i ? '<span class="podp">/</span>' : ''}<select class="pole mono" data-klucz="${k}">${op.map((o) => `<option ${o === String(u[k]) ? 'selected' : ''}>${o}</option>`).join('')}</select>`;
  });
  if (p.kier) wart += `<div class="segment">${['góra', 'dół'].map((v) => `<button data-klucz="${p.kier}" data-wartosc="${v}" class="${u[p.kier] === v ? 'akt' : ''}">${v === 'góra' ? 'W górę' : 'W dół'}</button>`).join('')}</div>`;
  if (p.dzialy || p.lista) {
    const k = p.dzialy || p.lista, l = numery(u[k]);
    wart += `<span class="chipy">${p.dzialy ? `<span title="${esc(l.join('\n'))}">${l.length} działów</span>` : l.slice(0, 6).map((n) => `<span>${esc(n)}</span>`).join('') + (l.length > 6 ? `<span>+${l.length - 6}</span>` : '')}<span class="plus" data-lista="${k}">zmień</span></span>`;
  }
  if (p.przel) wart += `<button class="przelacznik ${u[p.przel] ? 'wl' : ''}" data-klucz="${p.przel}" data-przel="1" title="${u[p.przel] ? 'Włączone' : 'Wyłączone'}"></button>`;
  return `<div class="wiersz ${lok ? 'lokalna' : ''} ${wyl ? 'wylaczony' : ''}" ${lok ? `title="Zmienione na tym komputerze (${esc(firm)})"` : ''}>
    <span class="et"><span>${p.et}${p.mala ? `<small>${p.mala}</small>` : ''}</span>${lok ? `<button class="przywroc" data-przywroc="${kluczePola(p).join(',')}" title="Przywróć firmową wartość">${ik('wstecz')}</button>` : ''}</span>
    <span class="wartosci">${wart}</span></div>`;
}

function rysujReguly() {
  const el = $('#widok-reguly');
  const lok = Object.keys(REG.lokalne);
  $('#pasek-prawe').innerHTML = `<span class="podp">Zmiany zapisują się od razu${STAN?.rcp ? ' i plik jest przeliczany' : ''}</span>`;
  el.innerHTML = `
    ${REG.sa_firmowe ? `<div class="baner">${ik('serwer')}<div class="tekst"><b>Reguły firmowe${REG.wersja ? ` · wersja z ${esc(REG.wersja)}` : ''}</b>
        Ustalone w panelu administratora - takie same u wszystkich. Pola oznaczone <span class="tag niepelny">●</span> zmieniono tylko na tym komputerze.</div>
        ${lok.length ? `<button class="btn btn-maly" id="r-zaproponuj">Zaproponuj jako firmowe (${lok.length})</button><button class="btn btn-maly btn-bez" id="r-przywroc">Przywróć wszystkie firmowe</button>` : ''}</div>`
    : `<div class="baner zolty">${ik('uwaga')}<div class="tekst"><b>Brak reguł firmowych</b>${KONTO ? 'Administrator nie wczytał jeszcze reguł w panelu - program używa reguł domyślnych.' : 'Bez logowania program używa reguł domyślnych.'}
        ${lok.length ? ' Zmiany oznaczone <span class="tag niepelny">●</span> obowiązują na tym komputerze.' : ''}</div>${lok.length ? '<button class="btn btn-maly btn-bez" id="r-przywroc">Przywróć domyślne</button>' : ''}</div>`}
    <div class="siatka k3">
      ${KARTY.map((k) => `<section class="karta"><h3>${ik(k.ikona)}${k.tytul}</h3><p class="opis">${k.opis}</p>${k.pola.map(rysujPole).join('')}</section>`).join('')}
      <section class="karta"><h3>${ik('ludzie')}Pracownicy</h3><p class="opis">Przypisania zmian ustawia administrator w panelu HR</p>
        ${wierszListy('Ignorowani', 'bez raportu błędów', numery(REG.aktualne.pracownicy_ignorowani), numery(REG.niepracujacy_z_panelu).filter((n) => !numery(REG.aktualne.pracownicy_ignorowani).includes(n)))}
        ${LISTY_PANELU.map(([k, n]) => wierszListy(n, '', numery(REG.listy_z_panelu[k]))).join('')}
      </section>
    </div>`;
  $$('select[data-klucz]', el).forEach((s) => s.onchange = () => zmienRegule(s.dataset.klucz, s.value));
  $$('button[data-klucz]', el).forEach((b) => b.onclick = () => zmienRegule(b.dataset.klucz, b.dataset.przel ? !REG.aktualne[b.dataset.klucz] : b.dataset.wartosc));
  $$('[data-przywroc]', el).forEach((b) => b.onclick = async () => { for (const k of b.dataset.przywroc.split(',')) if (k in REG.lokalne) REG = await api('przywroc_firmowe', k); poZmianieRegul(); });
  $$('[data-lista]', el).forEach((b) => b.onclick = () => wybierzListe(b.dataset.lista));
  $('#r-przywroc')?.addEventListener('click', async () => {
    const w = await modal({ tytul: 'Przywrócić reguły firmowe?', tresc: `<p>Zmiany lokalne (${lok.length}) zostaną usunięte z tego komputera.</p>`, przyciski: [{ tekst: 'Anuluj', wartosc: null, domyslny: true }, { tekst: 'Przywróć', klasa: 'btn-hr', wartosc: 'tak' }] });
    if (w === 'tak') { REG = await api('przywroc_firmowe', null); poZmianieRegul(); }
  });
  $('#r-zaproponuj')?.addEventListener('click', zaproponujReguly);
}

// Lista numerów tylko do odczytu (zmienia administrator w panelu HR): etykieta nad numerami, nazwisko po najechaniu myszką.
// Niepracujący z panelu (też pomijani w raporcie) - osobno, do rozwinięcia.
function wierszListy(nazwa, mala, lista, niepracujacy = []) {
  const nazwisko = (nr) => PRACOWNICY.find((p) => p.nr === nr)?.nazwisko || '';
  const chip = (nr, kl = 'zablokowane') => `<span class="${kl}" title="${esc(nazwisko(nr) || 'brak na liście pracowników')}">${esc(nr)}</span>`;
  return `<div class="wiersz kolumna"><span class="et"><span>${nazwa}${mala ? ` <small style="display:inline">· ${mala}</small>` : ''}</span></span>
    <span class="chipy">${lista.map((nr) => chip(nr)).join('')}${!lista.length ? '<span class="podp">brak</span>' : ''}</span>
    ${niepracujacy.length ? `<details class="rozwin"><summary>oraz ${niepracujacy.length} ${odmiana(niepracujacy.length, 'osoba oznaczona', 'osoby oznaczone', 'osób oznaczonych')} w panelu HR jako niepracujące</summary>
      <span class="chipy">${niepracujacy.map((nr) => chip(nr, 'zablokowane przerywane')).join('')}</span></details>` : ''}</div>`;
}

function opisWartosci(k, v) { return typeof v === 'boolean' ? (v ? 'włączone' : 'wyłączone') : k === 'dzialy_wyjatek' || k === 'pracownicy_ignorowani' ? `${numery(v).length} pozycji` : v; }
function nazwaKlucza(k) {
  for (const karta of KARTY) for (const p of karta.pola) if (kluczePola(p).includes(k)) return `${karta.tytul} → ${p.et}`;
  return k === 'pracownicy_ignorowani' ? 'Pracownicy → Ignorowani' : k;
}

async function zaproponujReguly() {
  const lok = Object.entries(REG.lokalne);
  const w = await modal({
    tytul: 'Zaproponuj jako reguły firmowe', szeroki: true,
    tresc: `<p class="podp">Administrator dostanie e-mail i zdecyduje w panelu, czy zmiana obowiązuje wszystkich. Do tego czasu działa tylko u Ciebie.</p>
      <div class="lista-wyboru">${lok.map(([k, v]) => `<label><input type="checkbox" value="${k}" checked><span style="flex:1">${esc(nazwaKlucza(k))}</span>
        <span class="podp">${esc(opisWartosci(k, REG.firmowe[k]))} → <b style="color:var(--text)">${esc(opisWartosci(k, v))}</b></span></label>`).join('')}</div>
      <label class="etykieta" style="margin-top:14px">Dlaczego ta zmiana jest lepsza? (widzi administrator)</label><textarea class="pole" id="z-komentarz" style="min-height:80px"></textarea>`,
    przyciski: [{ tekst: 'Anuluj', wartosc: null }, { tekst: `${ik('wyslij')} Wyślij propozycję`, klasa: 'btn-hr', wartosc: 'tak' }],
    poOtwarciu: (el) => { window._prop = el; },
  });
  if (w !== 'tak') return;
  const klucze = $$('input[type=checkbox]:checked', window._prop).map((c) => c.value);
  const r = await api('zaproponuj_reguly', klucze, $('#z-komentarz', window._prop).value);
  if (r?.ok) toast('Propozycja wysłana do administratora.', 'ok');
  else toast(esc(r?.blad || 'Nie udało się wysłać propozycji.'), 'blad');
}

async function wybierzListe(klucz) {
  const dzialy = klucz === 'dzialy_wyjatek';
  const wybrane = new Set(numery(REG.aktualne[klucz]));
  const pozycje = dzialy ? [...new Set([...(STAN?.dzialy || []), ...(await api('dzialy') || []), ...wybrane])].filter((d) => d && d !== '---').sort((a, b) => a.localeCompare(b, 'pl')).map((d) => ({ w: d, n: d }))
    : [...PRACOWNICY.map((p) => ({ w: p.nr, n: p.nazwisko })), ...[...wybrane].filter((n) => !PRACOWNICY.some((p) => p.nr === n)).map((n) => ({ w: n, n: '---' }))];
  const w = await modal({
    tytul: dzialy ? 'Działy z wyjątkiem nadgodzin' : 'Ignorowani pracownicy', szeroki: true,
    tresc: `<input class="pole" id="w-szukaj" placeholder="Szukaj…" style="width:100%">
      <div class="lista-wyboru">${pozycje.map((p) => `<label data-szukaj="${esc((p.w + ' ' + p.n).toLowerCase())}"><input type="checkbox" value="${esc(p.w)}" ${wybrane.has(p.w) ? 'checked' : ''}>${dzialy ? '' : `<span class="mono">${esc(p.w)}</span>`}<span>${esc(p.n)}</span></label>`).join('') || '<div class="pusto">Brak listy - zaloguj się, żeby pobrać pracowników i działy.</div>'}</div>`,
    przyciski: [{ tekst: 'Anuluj', wartosc: null }, { tekst: 'Zapisz wybór', klasa: 'btn-hr', wartosc: 'tak' }],
    poOtwarciu: (el) => { window._lista = el; $('#w-szukaj', el).oninput = (e) => $$('[data-szukaj]', el).forEach((l) => l.classList.toggle('ukryty', !l.dataset.szukaj.includes(e.target.value.toLowerCase()))); },
  });
  if (w !== 'tak') return;
  zmienRegule(klucz, $$('input[type=checkbox]:checked', window._lista).map((c) => c.value).join(', '));
}

async function zmienRegule(k, v) {
  REG = await api('zmien_regule', k, v);
  poZmianieRegul();
}
function poZmianieRegul() {
  rysujReguly();
  odswiezDol();
  if (!STAN?.rcp) return;
  clearTimeout(przeliczTimer);
  przeliczTimer = setTimeout(async () => { nowyStan(await api('przetworz')); }, 350);
}

// ------------------------------------------------------------------ wszystkie wpisy (tryb listy na ekranie Korekta logów)
async function rysujWszystkieWpisy(box) {
  if (!WPISY.length) {
    box.innerHTML = '<div class="pusto">Wczytywanie…</div>';
    WPISY = (await api('wpisy')) || [];
    if (filtr.tryb !== 'wszystkie') return;
  }
  const q = filtr.szukaj.trim().toLowerCase();
  const anom = new Map(STAN.anomalie.map((a) => [a.id, a]));
  const l = WPISY.filter((w) => (!filtr.dzialy.size || filtr.dzialy.has(w.dzial))
    && (!q || w.nr.includes(q) || w.nazwisko.toLowerCase().includes(q) || dataKr(w.data).includes(q) || w.zdarzenia.includes(q)));
  const pokaz = l.slice(0, 1500);
  box.innerHTML = l.length ? `<table class="tab"><thead><tr><th>Dzień</th><th>Nr</th><th>Pracownik</th><th>Dział</th><th>Zmiana</th><th>Odbicia (po korekcie)</th><th>Uwagi</th></tr></thead><tbody>
    ${pokaz.map((w) => { const a = anom.get(w.id); return `<tr data-id="${esc(w.id)}" class="${w.id === wybranyId ? 'wybrany' : ''}"><td class="data">${dataKr(w.data)}<small>${dzienTyg(w.data)}</small></td><td class="nr">${esc(w.nr)}</td>
      <td class="nazwisko">${esc(w.nazwisko)}</td><td class="dzial" title="${esc(w.dzial)}">${esc(w.dzial)}</td><td class="zmiana">${esc(zmianaKr(w.typ_zmiany))}</td>
      <td class="zdarzenia-wiersz">${esc(w.zdarzenia)}</td><td>${a ? tagi(a.uwaga) : ''}${a?.reczna ? '<span class="tag reczna">ręcznie</span>' : ''}</td></tr>`; }).join('')}</tbody></table>
    ${l.length > pokaz.length ? `<div class="pusto">Pokazano ${liczba(pokaz.length)} z ${liczba(l.length)} - zawęź wyszukiwaniem albo działem.</div>` : ''}`
    : '<div class="pusto">Brak wpisów dla wybranych filtrów.</div>';
  $$('tbody tr', box).forEach((tr) => tr.onclick = () => otworzDzien(tr.dataset.id, pokaz.map((w) => w.id)));
}

// ------------------------------------------------------------------ historia
async function otworzZHistorii(id) {
  const s = await api('otworz_z_historii', id);
  if (s?.ok === false) return toast(esc(s.blad), 'blad');
  PRACOWNICY = (await api('pracownicy')) || PRACOWNICY;
  nowyStan(s);
  pokaz('pulpit');
}
async function rysujHistorie() {
  const el = $('#widok-historia');
  const h = (await api('historia')) || [];
  el.innerHTML = `<p class="podp" style="margin:0">Ostatnie ${h.length} przetworzonych plików na tym komputerze. Ręczne korekty nie są tu zapisywane - po ponownym otwarciu plik jest przeliczany od nowa.</p>
    ${h.map((w) => `<div class="karta historia-poz">
      <div><b>${esc(w.plik.split(/[\\/]/).pop())}</b>${w.istnieje ? '' : ' <span class="tag nieobecnosc">plik przeniesiony lub usunięty</span>'}
        <div class="meta"><span>${esc(w.kiedy)}</span><span>okres <b>${esc(w.okres.replaceAll('.', '-'))}</b></span><span>zdarzeń <b>${liczba(w.zdarzen)}</b></span>
          <span>do sprawdzenia <b>${liczba(w.do_sprawdzenia)}</b></span>${w.reczne ? `<span>ręcznych korekt <b>${w.reczne}</b></span>` : ''}
          ${(w.zapisy || []).length ? `<span>zapisano dla ERP <b>${w.zapisy.length}×</b>, ostatnio ${esc(w.zapisy[w.zapisy.length - 1].kiedy)}</span>` : '<span>nie zapisano dla ERP</span>'}</div></div>
      <div style="display:flex; gap:8px">${w.istnieje ? `<button class="btn btn-maly" data-folder="${esc(w.plik)}">${ik('folder')} Folder</button><button class="btn btn-maly" data-otworz="${esc(w.id)}">Otwórz ponownie</button>` : ''}</div>
      ${w.pliki.length ? `<details class="rozwin pliki-wynikowe"><summary class="btn btn-maly">${ik('dalej', 'strzalka')} Zapisane pliki: ${w.pliki.filter((p) => p.rodzaj === 'erp').length} ${odmiana(w.pliki.filter((p) => p.rodzaj === 'erp').length, 'poprawiony dla ERP', 'poprawione dla ERP', 'poprawionych dla ERP')}, ${w.pliki.length - w.pliki.filter((p) => p.rodzaj === 'erp').length} ${odmiana(w.pliki.length - w.pliki.filter((p) => p.rodzaj === 'erp').length, 'raport', 'raporty', 'raportów')}</summary>
        <table class="tab"><tbody>${w.pliki.map((p) => `<tr><td><span class="tag ${p.rodzaj === 'erp' ? 'reczna' : 'ostrzezenie'}">${p.rodzaj === 'erp' ? `ERP · wersja ${p.numer}` : `raport ${p.rodzaj.toUpperCase()} · ${p.numer}`}</span></td>
          <td class="nazwisko">${esc(p.nazwa)}</td><td class="podp">${esc(p.kiedy)}</td><td class="podp">${p.kb} KB</td>
          <td style="text-align:right; white-space:nowrap"><button class="btn btn-maly" data-plik="${esc(p.sciezka)}">Otwórz</button> <button class="btn btn-maly btn-bez" data-folder="${esc(p.sciezka)}">${ik('folder')}</button></td></tr>`).join('')}</tbody></table></details>`
      : '<div class="podp" style="grid-column: span 2">Brak zapisanych plików dla ERP w folderze pliku.</div>'}</div>`).join('') || '<div class="pusto">Historia jest pusta.</div>'}`;
  $$('[data-plik]', el).forEach((b) => b.onclick = async () => { const r = await api('otworz_plik', b.dataset.plik); if (r && !r.ok) toast(esc(r.blad), 'blad'); });
  $$('[data-otworz]', el).forEach((b) => b.onclick = () => otworzZHistorii(b.dataset.otworz));
  $$('[data-folder]', el).forEach((b) => b.onclick = () => api('otworz_folder', b.dataset.folder));
}

// ------------------------------------------------------------------ ustawienia
function przel(klucz, et, mala = '') {
  return `<div class="wiersz"><span class="et"><span>${et}${mala ? `<small>${mala}</small>` : ''}</span></span><button class="przelacznik ${INFO.program[klucz] ? 'wl' : ''}" data-prog="${klucz}"></button></div>`;
}
function rysujUstawienia() {
  const el = $('#widok-ustawienia');
  const p = INFO.program;
  const seg = (klucz, opcje) => `<div class="segment">${opcje.map(([v, n]) => `<button data-prog-seg="${klucz}" data-wartosc="${v}" class="${p[klucz] === v ? 'akt' : ''}">${n}</button>`).join('')}</div>`;
  el.innerHTML = `<div class="siatka k2">
    <section class="karta"><h3>${ik('info')}Wygląd</h3><p class="opis">Motyw możesz też zmienić w menu z lewej</p>
      <div class="wiersz"><span class="et">Motyw</span>${seg('motyw', [['jasny', 'Jasny'], ['ciemny', 'Ciemny'], ['system', 'Jak w Windows']])}</div>
      <div class="wiersz"><span class="et">Wielkość tekstu</span>${seg('rozmiar', [['maly', 'Mała'], ['normalny', 'Normalna'], ['duzy', 'Duża']])}</div></section>
    <section class="karta"><h3>${ik('plik')}Raporty</h3><p class="opis">Lista problemów do sprawdzenia i wydruku</p>
      ${przel('eksport_txt', 'Raport TXT', 'zapisywany razem z plikiem ERP')}
      ${przel('eksport_pdf', 'Raport PDF', 'przycisk „Raport PDF” na pulpicie')}
      ${p.eksport_pdf ? przel('pdf_przy_zapisie', 'PDF zapisywany razem z plikiem ERP') + przel('pdf_kratki', 'Kratki do odhaczania', 'przy każdej pozycji') + przel('pdf_podpisy', 'Miejsce na podpisy', 'sprawdził / zatwierdził') : ''}</section>
    <section class="karta"><h3>${ik('folder')}Zapis plików</h3><p class="opis">Gdzie trafia plik do importu w ERP</p>
      <div class="wiersz"><span class="et"><span>Folder zapisu<small>${esc(p.folder_zapisu || 'obok pliku z Roger RCP')}</small></span></span>
        <span class="wartosci">${p.folder_zapisu ? '<button class="btn btn-maly btn-bez" id="u-folder-dom">Domyślny</button>' : ''}<button class="btn btn-maly" id="u-folder">Wybierz…</button></span></div>
      ${przel('otworz_folder', 'Otwórz folder po zapisie')}</section>
    <section class="karta"><h3>${ik('serwer')}Konto i dane</h3><p class="opis">Lista pracowników i reguły firmowe z serwera diamel.pl</p>
      <div class="wiersz"><span class="et">Zalogowano</span><b>${esc(KONTO ? KONTO.login || 'tak' : 'nie')}</b></div>
      <div class="wiersz"><span class="et">Pracowników w bazie</span><span class="mono">${KONTO ? liczba(KONTO.pracownikow) : '–'}${KONTO?.wersja_bazy ? ` · ${esc(KONTO.wersja_bazy)}` : ''}</span></div>
      <div class="wiersz"><span class="et">Reguły firmowe</span><span>${REG.sa_firmowe ? esc(REG.wersja || 'tak') : 'brak'}</span></div>
      <div class="wiersz"><span class="et"></span><span class="wartosci">${KONTO ? `<button class="btn btn-maly" id="u-odswiez">${ik('odswiez')} Odśwież dane</button><button class="btn btn-maly btn-czerwony" id="u-wyloguj">Wyloguj</button>` : '<button class="btn btn-maly btn-hr" id="u-zaloguj">Zaloguj</button>'}</span></div></section>
    <section class="karta" style="grid-column: span 2"><h3>${ik('pobierz')}O programie</h3><p class="opis">Korektor Logów HR v${esc(INFO.wersja)} · ${esc(INFO.data)} · © Mateusz Kujawa, DIAMEL</p>
      <div class="wiersz"><span class="et">${AKT?.nowsza ? `Dostępna wersja <b>${esc(AKT.wersja)}</b>` : 'Aktualizacje'}</span>
        <span class="wartosci"><button class="btn btn-maly" id="u-zmiany">Historia zmian</button><button class="btn btn-maly" id="u-www">Strona programu</button><button class="btn btn-maly ${AKT?.nowsza ? 'btn-hr' : ''}" id="u-akt">${AKT?.nowsza ? 'Zainstaluj' : 'Sprawdź aktualizacje'}</button></span></div></section>
  </div>`;
  $$('[data-prog]', el).forEach((b) => b.onclick = async () => { await zmienProgram(b.dataset.prog, !p[b.dataset.prog]); rysujUstawienia(); });
  $$('[data-prog-seg]', el).forEach((b) => b.onclick = async () => { await zmienProgram(b.dataset.progSeg, b.dataset.wartosc); rysujUstawienia(); });
  $('#u-folder').onclick = async () => { INFO.program = await api('wybierz_folder_zapisu'); rysujUstawienia(); };
  $('#u-folder-dom')?.addEventListener('click', async () => { await zmienProgram('folder_zapisu', ''); rysujUstawienia(); });
  $('#u-odswiez')?.addEventListener('click', async () => {
    const w = await modal({
      tytul: `${ik('odswiez')} Odśwież dane z serwera`,
      tresc: `<p>Co pobrać z panelu HR na diamel.pl?</p>
        <div class="lista-wyboru">
          <label><input type="checkbox" id="o-prac" checked><span style="flex:1"><b style="font-weight:600">Baza pracowników</b><br><span class="podp">nazwiska, działy, przypisania zmian, niepracujący · teraz: ${liczba(KONTO.pracownikow)} osób${KONTO.wersja_bazy ? `, stan z ${esc(KONTO.wersja_bazy)}` : ''}</span></span></label>
          <label><input type="checkbox" id="o-reg" checked><span style="flex:1"><b style="font-weight:600">Reguły firmowe</b><br><span class="podp">zaokrąglanie, duplikaty, nadgodziny, ignorowani · teraz: ${REG.sa_firmowe ? esc(REG.wersja || 'tak') : 'brak - reguły domyślne'}</span></span></label>
        </div>${Object.keys(REG.lokalne).length ? `<p class="podp" style="margin-top:10px">Twoje zmiany lokalne reguł (${Object.keys(REG.lokalne).length}) zostają - nadal mają pierwszeństwo przed firmowymi.</p>` : ''}`,
      przyciski: [{ tekst: 'Anuluj', wartosc: null }, { tekst: `${ik('pobierz')} Pobierz`, klasa: 'btn-hr', wartosc: 'tak', domyslny: true }],
      poOtwarciu: (el) => { window._odswiez = el; },
    });
    if (w !== 'tak') return;
    const prac = $('#o-prac', window._odswiez).checked, reg = $('#o-reg', window._odswiez).checked;
    if (!prac && !reg) return toast('Nic nie zaznaczono - dane bez zmian.');
    const d = await api('pobierz_dane', prac, reg);
    if (d?.ok) {
      KONTO = d; REG = await api('reguly'); PRACOWNICY = (await api('pracownicy')) || []; odswiezDol(); rysujUstawienia();
      const opis = [];
      const p = d.zmiany.pracownicy, r = d.zmiany.reguly;
      if (p) opis.push(`<b>Baza pracowników:</b> ${p.bez_zmian ? `bez zmian (${liczba(p.jest)} osób)` : `${liczba(p.bylo)} → ${liczba(p.jest)} osób${p.dodani ? `, nowi: ${p.dodani}` : ''}${p.usunieci ? `, usunięci: ${p.usunieci}` : ''}${p.zmienieni ? `, zmienieni: ${p.zmienieni}` : ''}`}`);
      if (r) opis.push(`<b>Reguły firmowe:</b> ${!r.na_serwerze ? 'na serwerze nie ma reguł firmowych - działają reguły domyślne' : !r.zmienionych ? `bez zmian (${esc(r.jest)})` : `${esc(r.bylo || 'brak')} → ${esc(r.jest)}, zmienionych ustawień: ${r.zmienionych}`}`);
      toast(opis.join('<br>'), r && !r.na_serwerze ? '' : 'ok', null, 10000);
      if (STAN?.rcp && ((p && !p.bez_zmian) || (r && r.zmienionych))) { nowyStan(await api('przetworz')); toast('Plik przeliczono ponownie z nowymi danymi (ręczne korekty zostały).', 'ok'); }
    }
    else if (d?.zaloguj) ekranLogowania('Sesja wygasła - zaloguj się ponownie.');
    else toast(esc(d?.blad || 'Nie udało się pobrać danych.'), 'blad');
  });
  $('#u-wyloguj')?.addEventListener('click', async () => {
    const w = await modal({ tytul: 'Wylogować?', tresc: '<p>Zapamiętany dostęp na tym komputerze zostanie usunięty. Przy następnym uruchomieniu trzeba będzie podać hasło.</p>', przyciski: [{ tekst: 'Anuluj', wartosc: null, domyslny: true }, { tekst: 'Wyloguj', klasa: 'btn-czerwony', wartosc: 'tak' }] });
    if (w === 'tak') { await api('wyloguj'); KONTO = null; ekranLogowania(); }
  });
  $('#u-zaloguj')?.addEventListener('click', () => ekranLogowania());
  $('#u-zmiany').onclick = () => modal({ tytul: 'Historia zmian', szeroki: true, tresc: `<div style="white-space:pre-wrap; font-size:0.86rem; max-height:60vh; overflow:auto">${esc(INFO.changelog)}</div>`, przyciski: [{ tekst: 'Zamknij', wartosc: null }] });
  $('#u-www').onclick = () => api('otworz_strone', 'https://diamel.pl/hr/aktualizacje-hr.php');
  $('#u-akt').onclick = () => (AKT?.nowsza ? oknoAktualizacji() : sprawdzAktualizacje(true).then(() => widok === 'ustawienia' && rysujUstawienia()));
}

// ------------------------------------------------------------------ zgłoszenie błędu
let dodatkowe = [];
function rysujZgloszenie() {
  const el = $('#widok-zglos');
  el.innerHTML = `<section class="karta" style="max-width:820px; display:grid; gap:14px">
    <p class="podp" style="margin:0">Zgłoszenie trafia e-mailem do autora programu. Opisz, co się stało i których pracowników / dni dotyczy.</p>
    <div><label class="etykieta">Twój adres e-mail (do odpowiedzi)</label><input class="pole" id="z-email" style="width:100%" type="email"></div>
    <div><label class="etykieta">Opis problemu</label><textarea class="pole" id="z-opis" placeholder="np. pracownik 0123, 06.10 - program usunął wyjście o 14:02…"></textarea></div>
    <div><label class="etykieta">Załączniki <span id="z-rozmiar"></span></label><div class="lista-wyboru" id="z-zalaczniki" style="margin-top:0"><div class="pusto" style="padding:14px">Wczytaj plik RCP - jego pliki dołączą się same.</div></div></div>
    <div class="wiersz" style="border:0"><span class="et"><span>Dodatkowe pliki<small id="z-dodatkowe">${dodatkowe.length ? dodatkowe.map((p) => esc(p.split(/[\\/]/).pop())).join(', ') : 'np. zrzuty ekranu'}</small></span></span>
      <span class="wartosci"><button class="btn btn-maly" id="z-dodaj">Dodaj pliki</button>${dodatkowe.length ? '<button class="btn btn-maly btn-bez" id="z-wyczysc">Wyczyść</button>' : ''}</span></div>
    <button class="btn btn-hr duzy" id="z-wyslij">${ik('wyslij')} Wyślij zgłoszenie</button></section>`;
  // Pliki tego RCP (przed korektą, poprawione, raporty) - dołączane automatycznie, można odznaczyć
  api('pliki_do_zgloszenia').then((z) => {
    if (!z?.pliki.length || !$('#z-zalaczniki')) return;
    $('#z-zalaczniki').innerHTML = z.pliki.map((p) => `<label><input type="checkbox" value="${esc(p.sciezka)}" data-kb="${p.kb}" ${p.zaznacz ? 'checked' : ''}>
      <span style="flex:1; min-width:0"><b style="font-weight:500">${esc(p.nazwa)}</b><br><span class="podp">${esc(p.opis)}</span></span><span class="podp">${p.kb} KB</span></label>`).join('');
    const suma = () => { const kb = $$('#z-zalaczniki input:checked').reduce((s, c) => s + +c.dataset.kb, 0); $('#z-rozmiar').innerHTML = `<span class="podp">· razem ${(kb / 1024).toFixed(1)} MB z ${z.limit_mb} MB</span>`; };
    $$('#z-zalaczniki input').forEach((c) => c.onchange = suma);
    suma();
  });
  $('#z-dodaj').onclick = async () => { dodatkowe = [...dodatkowe, ...((await api('wybierz_zalaczniki')) || [])]; const e = $('#z-email').value, o = $('#z-opis').value; rysujZgloszenie(); $('#z-email').value = e; $('#z-opis').value = o; };
  $('#z-wyczysc')?.addEventListener('click', () => { dodatkowe = []; rysujZgloszenie(); });
  $('#z-wyslij').onclick = async () => {
    const email = $('#z-email').value.trim(), opis = $('#z-opis').value.trim();
    if (!/^\S+@\S+\.\S+$/.test(email)) return toast('Podaj poprawny adres e-mail.', 'blad');
    if (opis.length < 5) return toast('Opisz problem.', 'blad');
    $('#z-wyslij').disabled = true;
    $('#z-wyslij').textContent = 'Wysyłanie…';
    const r = await api('zglos_blad', email, opis, $$('#z-zalaczniki input:checked').map((c) => c.value), dodatkowe);
    if (r?.ok) { dodatkowe = []; toast('Zgłoszenie wysłane. Dziękuję!', 'ok'); rysujZgloszenie(); }
    else { toast(esc(r?.blad || 'Nie udało się wysłać zgłoszenia.'), 'blad'); $('#z-wyslij').disabled = false; $('#z-wyslij').innerHTML = `${ik('wyslij')} Wyślij zgłoszenie`; }
  };
}

// ------------------------------------------------------------------ skróty klawiszowe
document.addEventListener('keydown', (e) => {
  if (!$('#ekran-start').classList.contains('ukryty')) return;
  if (modalOtwarty) { if (e.key === 'Escape') modalOtwarty.zamknij(null); return; }
  const wPolu = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName);
  if (e.ctrlKey && e.key.toLowerCase() === 'o') { e.preventDefault(); return wybierzRcp(); }
  if (e.ctrlKey && e.key.toLowerCase() === 's') { e.preventDefault(); return zapiszErp(); }
  if (e.key === 'F5') { e.preventDefault(); return STAN?.rcp && przetworz(); }
  if (szuflada) {
    if (e.key === 'Escape') return zamknijSzufladePytaj();
    if (e.key === 'Enter' && document.activeElement?.tagName !== 'BUTTON' && document.activeElement?.tagName !== 'TEXTAREA') {
      e.preventDefault();
      document.activeElement?.blur?.();
      return zatwierdzDzien();
    }
    return;
  }
  if (widok !== 'pulpit' || !STAN?.rcp) return;
  if (filtr.tryb === 'wszystkie' && (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter') && !(e.ctrlKey)) return;
  if (e.ctrlKey && e.key.toLowerCase() === 'f') { e.preventDefault(); return $('#f-szukaj')?.focus(); }
  if (wPolu && e.key !== 'ArrowDown') return;
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    const l = widoczneAnomalie();
    if (!l.length) return;
    const i = l.findIndex((a) => a.id === wybranyId);
    wybranyId = l[Math.max(0, Math.min(l.length - 1, i < 0 ? 0 : i + (e.key === 'ArrowDown' ? 1 : -1)))].id;
    document.activeElement?.blur?.();
    $$('#lista-przewijana tr').forEach((tr) => tr.classList.toggle('wybrany', tr.dataset.id === wybranyId));
    $(`#lista-przewijana tr[data-id="${CSS.escape(wybranyId)}"]`)?.scrollIntoView({ block: 'nearest' });
  }
  if (e.key === 'Enter' && wybranyId) otworzDzien(wybranyId);
});
