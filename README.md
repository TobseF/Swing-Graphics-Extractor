# Format `.RES` — Swing / Marble Master (Software 2000, 1997, MS-DOS)

Dokumentacja techniczna formatu grafiki gry, odtworzonego metodą inżynierii wstecznej.
**Ten dokument jest aktualizowany na bieżąco w miarę odkrywania nowych informacji.**

Ostatnia aktualizacja: analiza plików `CD.RES`, `FUNKEN1.RES`, `FUNKEN2.RES`, `FONTS.RES`,
`CORAIN.RES`, `PAUSE.RES`, `BUTTON.RES`, `KRANNORM.RES`, `COLOR.RES`, `BLOCK.RES`,
`BLOCKR.RES`, `BLOCKL.RES`, `GAMMA.RES`, `GAMMA.SWG`, `KEXPLO.RES`, `SMLMENU.RES`,
`SMRM1.RES`, `SMRM2.RES`, `EXTRAS.RES`, `HELPMODE.RES`, `NORMAL.SET`, `MAKE.SET`,
`SHOWSET.EXE`, `SWING.EXE`.

---

## 1. Status ogólny

| Element | Status |
|---|---|
| Nagłówek pojedynczego obrazu (16 B) | ✅ Rozpracowany |
| Padding po nagłówku (4 B) | ✅ Potwierdzony (wszystkie znane odmiany kodeka) |
| Format koloru pikseli | ✅ RGB555 |
| Kodek `type=4`/`type=1`/`type=6` (RLE parami) | ✅ Rozpracowany, potwierdzony wizualnie (CD.RES, PAUSE.RES, KRANNORM.RES, BLOCK.RES, SMLMENU.RES, SMRM1.RES, SMRM2.RES) |
| Kodek `type=2`/`type=7`/`type=3` (prosty strumień) | ✅ Rozpracowany, potwierdzony wizualnie (BUTTON.RES, FUNKEN2.RES, GAMMA.RES) |
| Token ucieczki | ✅ `0x0003` (najczęstszy) lub `0x0000` (rzadziej, np. COLOR.RES) — **wybierany per klatka próbą+walidacją, NIGDY oba naraz** (patrz §4.3 i §4.5, ważne poprawki!) |
| Wybór kodeka na podstawie `type` | ⚠️ `type=7` obserwowany w OBU kodekach (COLOR.RES=parami, FUNKEN2/CORAIN/GAMMA=prosty) — wymaga próby+walidacji, nie prostego mapowania (patrz §4.4) |
| Wykrywanie granic klatek w kontenerze wieloklatkowym | ✅ Działa niezawodnie na wszystkich 11 przebadanych plikach (0 B resztek) |
| Znaczenie pola `type` (poza wyborem kodeka) | ❓ Nieznane — potwierdzone dotąd: `{1,4,6}`→RLE parami zawsze, `{2}`→prosty zawsze, `{7}`→oba warianty, `{3}`→prosty (GAMMA.RES) |
| Znaczenie pola `extra` (ostatnie 4 B nagłówka) | ❓ Nieznane — NIE jest tokenem ucieczki (hipoteza obalona, patrz §4.3) |
| Znaczenie 4 bajtów paddingu | ❓ Nieznane (zawsze pomijane, wartość zwykle 0, ale nie zawsze) |
| `FONTS.RES` | ❌ Nie pasuje do modelu nagłówka ANI do formatu archiwum — jedyny nierozwiązany plik (patrz §6.2) |
| `CORAIN.RES` | ✅ **Rozwiązane!** Wynik to czysta animacja rozbłysku/eksplozji (patrz §4.3) |
| Format `.SWG` (osobny od `.RES`) | ✅ Rozpracowany — surowa bitmapa pełnoekranowa, patrz §9 |
| Format archiwum (`EXTRAS.RES`, `HELPMODE.RES`) | ✅ Rozpracowany w 100% — pliki-paczki z nazwanymi podplikami, patrz §10 |
| Format `.SET` (zestawy skórek kulek) | ✅ Rozpracowany — nagłówek 48 B + blok obrazów `.RES`, patrz §11 |

---

## 2. Struktura nagłówka (16 bajtów)

Little-endian, na początku każdego obrazu/klatki:

```
offset  rozmiar  pole          opis
0x00    u16      magic         zawsze 0x0014
0x02    u8       type          selektor kodeka danych pikseli (patrz §4)
0x03    u8       const_0f      zawsze 0x0F
0x04    u16      width         szerokość obrazu w pikselach
0x06    u16      height        wysokość obrazu w pikselach
0x08    u32      dataLen       znaczenie zależne od kodeka (patrz §4)
0x0C    u32      extra         nieznane — obserwowane wartości: 0, 3
```

Po 16-bajtowym nagłówku następują **4 bajty paddingu** (w większości obserwacji same zera),
a dopiero po nich właściwy strumień danych pikseli.

Struct Python do parsowania nagłówka:
```python
magic, typ, const_0f, w, h, datalen, extra = struct.unpack_from('<HBBHHII', data, offset)
```

---

## 3. Format koloru pikseli — RGB555

Każdy "literalny" piksel to 16-bitowe słowo (little-endian):

```
bit:  15 14 13 12 11 10 09 08 07 06 05 04 03 02 01 00
      x  R  R  R  R  R  G  G  G  G  G  B  B  B  B  B
```

- najwyższy bit (15) nieużywany / niezidentyfikowany
- R: bity 10–14 (5 bitów)
- G: bity 5–9 (5 bitów)
- B: bity 0–4 (5 bitów)

Konwersja do 8-bit/kanał: `wartość_8bit = wartość_5bit * 255 / 31`.

**Ważne:** przetestowano też RGB565, BGR565, BGR555 — tylko RGB555 dało realistyczne,
czytelne obrazy (potwierdzone wizualnie na `PAUSE.RES`, gdzie widoczny jest czerwony
spadochron i czytelny napis "Pause").

---

## 4. Dwa znane kodeki danych pikseli

Wybór kodeka zależy od pola `type` w nagłówku. Potwierdzone dotąd przyporządkowanie:

| `type` | Plik(i) źródłowe | Kodek |
|---|---|---|
| 1 | `KRANNORM.RES` | RLE parami (opisany w §4.1) |
| 4 | `CD.RES`, `PAUSE.RES` | RLE parami (opisany w §4.1) |
| 2 | `BUTTON.RES` | Prosty strumień (opisany w §4.2) |
| 7 | `FUNKEN1.RES`(wstępnie), `FUNKEN2.RES` | Prosty strumień (opisany w §4.2) |

**Hipoteza robocza:** wartości `type` nie mapują się 1:1 ani parzyste/nieparzyste na
kodek — dotąd zaobserwowano, że `{1, 4}` używają RLE parami, a `{2, 7}` prostego
strumienia. To **lista znanych przyporządkowań**, nie ogólna reguła — nie wiadomo,
jak zachowają się inne, jeszcze niesprawdzone wartości `type`. Konwerter na razie
traktuje `type∈{1,4}` jako RLE parami, a każdą inną wartość jako kodek prosty
(domyślny fallback).

### 4.1 Kodek `type=4` — RLE parami

Dane to sekwencja 16-bitowych słów, o łącznej długości **dokładnie `dataLen` słów**.
Dekodowanie odbywa się **wiersz po wierszu** (bieg escape+count nie przekracza szerokości
`width`, ale pojedynczy piksel/bieg może kończyć się dokładnie na granicy wiersza):

- token `0x0003` = **escape**: następne słowo to `count` — liczba kolejnych pikseli
  **przezroczystych** do pominięcia
- każdy inny token = **jeden piksel literalny** w formacie RGB555

**Aktualizacja:** token ucieczki może być też `0x0000`, nie tylko `0x0003` — patrz §4.3.

Pseudokod:
```python
idx = 0
for row in range(height):
    col = 0
    while col < width and idx < dataLen:
        token = words[idx]; idx += 1
        if token == 3:
            cnt = words[idx]; idx += 1
            col += cnt   # przezroczyste, pomiń
        else:
            piksel[col, row] = rgb555_to_rgb888(token)
            col += 1
```

**Walidacja:** dla `CD.RES` i `PAUSE.RES` liczba zużytych słów odpowiada dokładnie
`dataLen`, a przy `PAUSE.RES` (kontener 64 sklejonych klatek) suma wszystkich rekordów
zużywa plik **co do ostatniego bajtu** (815278/815278 B). Analogicznie potwierdzone
dla `KRANNORM.RES` (`type=1`, kontener **190 klatek**, animacja żurawia/haka z
migającym światełkiem) — plik zużyty w 100% (1420786/1420786 B), zero bajtów resztek.

### 4.2 Kodek `type=2` / `type=7` — prosty strumień 1 token = 1 piksel

Dane to sekwencja 16-bitowych słów, czytana **w sposób ciągły** (bez wyrównania do
wierszy — pojedynczy piksel/przebieg może "przechodzić" przez koniec wiersza do
następnego), aż do zapełnienia `width * height` pikseli:

- token `0x0003` = **jeden piksel przezroczysty** (bez żadnego licznika po nim!)
- każdy inny token = **jeden piksel literalny** RGB555

**Aktualizacja:** token ucieczki może być też `0x0000` — patrz §4.3.

Pseudokod:
```python
filled = 0
idx = 0
while filled < width*height:
    token = words[idx]; idx += 1
    if token == 3:
        filled += 1   # przezroczysty piksel
    else:
        row, col = divmod(filled, width)
        piksel[col, row] = rgb555_to_rgb888(token)
        filled += 1
```

**Ważna różnica względem `type=4`:** tu NIE MA licznika po escape — to była pierwotna
przyczyna zniekształceń przy próbie dekodowania `BUTTON.RES` algorytmem z `type=4`
(licznik z kolejnego słowa był błędnie "zjadany" jako liczba pikseli do pominięcia,
co przesuwało resztę strumienia).

**Walidacja:** dla `BUTTON.RES` liczba zużytych słów = `width*height` dokładnie
(oraz zgadza się z polem `dataLen`, które dla tego kodeka wygląda na **równe
`width*height`** — czyli redundantne, a nie faktyczną długością strumienia). Dla
`FUNKEN2.RES` (`8×8`) też zgadza się liczbowo, choć plik zawiera dodatkowe dane po
tej klatce (patrz §6, niepewność co do dalszej zawartości).

**Uwaga:** dla kodeka `type=2`/`7`, pole `dataLen` NIE jest wiarygodnym wskaźnikiem
końca strumienia — koniec wyznacza wypełnienie `width*height` pikseli, nie wartość
`dataLen`. To odróżnia go od `type=4`, gdzie `dataLen` jest autorytatywne.

### 4.3 Token ucieczki: `0x0003` lub `0x0000` — WYBIERANY PER KLATKA, NIGDY OBA NARAZ

**Historia tej sekcji jest ważna, bo pierwsze rozwiązanie okazało się błędne.**

Przy analizie `COLOR.RES` (30×30 kolorowe kulki, kontener 46 klatek) odkryto, że ten
plik koduje przezroczystość tokenem **`0x0000`**, nie `0x0003` jak wszystkie
wcześniej zbadane pliki.

**Pierwsza (błędna) próba naprawy:** kazać obu kodekom traktować **jednocześnie**
`0x0000` i `0x0003` jako token ucieczki. To poprawiło `COLOR.RES`, `BUTTON.RES`
(ujawniając 7 zamiast 2 klatek) i `FUNKEN2.RES` (10 zamiast 1 klatki) — ale
**spowodowało regresję**: `KRANNORM.RES` (wcześniej perfekcyjny) zaczął się
"łamać" na części klatek, a `BLOCK.RES`/`BLOCKR.RES` dostały dziury/przesunięcia.

**Przyczyna:** niektóre obrazy (np. `KRANNORM.RES`, `BLOCK.RES`) legalnie zawierają
**literalny piksel o wartości słowa `0`** (czysta czerń w RGB555). Diagnostyka na
`KRANNORM.RES` wykazała **dokładną korelację 1:1**: klatki, które się "łamały"
(zakresy 0–36 i 88–189), to dokładnie te zawierające token `0` w strumieniu danych
jako prawdziwy piksel; klatki bez takiego tokenu (37–87) wypadały poprawnie czystym
zbiegiem okoliczności. Traktowanie `0` jako escape bezwarunkowo "zjadało" te
legalne czarne piksele razem z (nieistniejącym) licznikiem po nich, rozjeżdżając
resztę obrazu.

**Poprawne rozwiązanie:** dla każdej klatki osobno próbować **jednego** tokenu na
raz, zaczynając od `0x0003`, z walidacją wyniku:
- w kodeku RLE parami: poprawność = cały budżet słów (`dataLen`) został zużyty
  ORAZ każdy wiersz (poza ewentualnie ostatnim — końcowe przezroczyste wiersze
  bywają po prostu nieobecne w danych, bez jawnego kodowania) wypełnił się
  dokładnie do szerokości `width`
- w kodeku prostym: poprawność = udało się wypełnić dokładnie `width*height`
  pikseli bez przedwczesnego wyczerpania danych

Jeśli próba z `0x0003` się nie powiedzie walidacji, dopiero wtedy próbowany jest
`0x0000` dla TEJ SAMEJ klatki. Dzięki temu:
- `KRANNORM.RES` — z powrotem 190/190 klatek bezbłędnie (escape=3 waliduje się
  poprawnie dla każdej klatki, `0x0000` nigdy nie jest nawet próbowany)
- `BLOCK.RES` (2 klatki), `BLOCKR.RES` (8 klatek), `BLOCKL.RES` (8 klatek) — wszystkie
  bez dziur/przesunięć
- `COLOR.RES`, `BUTTON.RES` (7 klatek), `FUNKEN2.RES` (10 klatek) — nadal poprawne,
  bo próba z `0x0003` nie waliduje się dla ich klatek z `escape=0`, więc dekoder
  poprawnie przechodzi na `0x0000`
- **`CORAIN.RES` — nieoczekiwanie również się naprawił!** Wcześniej "zaszumiony"
  wynik (ukośne paski) okazał się artefaktem błędnego tokenu ucieczki. Poprawny
  rezultat to czysta, 33-klatkowa animacja jasnego rozbłysku/eksplozji stopniowo
  rozpadającego się na pojedyncze cząsteczki — wcześniej oznaczony jako otwarty,
  nierozwiązany problem (§6.3 w poprzednich wersjach dokumentu), teraz zamknięty

**Odrzucona hipoteza pośrednia:** testowano też, czy `escape = wartość pola extra
z nagłówka`. Dawało to poprawny wynik dla `COLOR.RES` (extra=0, escape=0) czysto
przez zbieg okoliczności, ale **łamało `FUNKEN2.RES`** (extra=0, ale prawdziwy
escape to 3 dla tamtej klatki) — hipoteza obalona i porzucona.

### 4.5 Walidacja próby tokenu ucieczki musi odrzucać niedorzeczne liczniki

Na małych obrazkach (np. `KEXPLO.RES`, 14×15 px) zdarza się, że **obie** próby
(`escape=3` i `escape=0`) formalnie przechodzą walidację z §4.3 (cały `dataLen`
zużyty, wiersze wypełnione do szerokości) — ale tylko jedna z nich daje sensowny
obraz. Odkryto to na pierwszej klatce animacji eksplozji `KEXPLO.RES`: przy
`escape=3` obraz wychodził jako szum (szachownica ukośnych pasów), mimo że
walidacja formalnie "przechodziła".

**Przyczyna:** przy błędnym tokenie ucieczki, algorytm czasem "trafia" na
liczbę słów pasującą do szerokości wiersza czystym zbiegiem okoliczności —
zwłaszcza przy małych obrazkach, gdzie przestrzeń możliwości jest ograniczona.
Sprawdzenie rzeczywistych liczników przeskoku (`count` po tokenie escape)
ujawniło niedorzeczną wartość **5251** (dla obrazka o zaledwie 210 pikselach!)
pod `escape=3`, podczas gdy `escape=0` dawał same rozsądne liczniki (1–14).

**Dodatkowa reguła walidacji:** licznik przeskoku (`count`) nie może przekraczać
**całkowitej liczby pikseli obrazu** (`width*height`) — pojedynczy bieg
przezroczystości fizycznie nie może być dłuższy niż cały obraz. Jeśli taki
niedorzeczny licznik się pojawi, próba jest odrzucana, a dekoder przechodzi do
kolejnego kandydata (`escape=0`, potem ew. kodek prosty). Naprawiono w ten sposób
pierwszą klatkę `KEXPLO.RES` (29-klatkowa animacja eksplozji: jasna chmura →
dym → żarzące się resztki) bez żadnej regresji na pozostałych 10 znanych plikach.

### 4.4 Pole `type` nie determinuje jednoznacznie kodeka

`type=7` zaobserwowano w **obu** kodekach:
- `FUNKEN2.RES`, `CORAIN.RES` → kodek prosty
- `COLOR.RES` → kodek RLE parami

Dodatkowo odkryto **nową wartość `type=3`** (`GAMMA.RES`, 225×60, 10 klatek —
przyciski menu z niemieckimi napisami typu "Optionen") — obsługiwana poprawnie
przez domyślny fallback (kodek prosty), tak samo jak `type=2`.

To znaczy, że samo `type` nie wystarcza do wyboru kodeka dla wartości `7` —
potrzebna jest próba z walidacją. Zastosowane rozwiązanie (w konwerterze):

1. `type ∈ {1, 4, 6}` → zawsze kodek RLE parami, `dataLen` z nagłówka jest
   ufany bezpośrednio (sprawdzone jako niezawodne — działa dla wszystkich
   znanych plików, łącznie z kontenerami wieloklatkowymi).
2. `type = 2` → zawsze kodek prosty.
3. `type = 7` → najpierw **próba** kodeka RLE parami z walidacją (patrz §4.3
   dla dokładnych kryteriów walidacji). Jeśli walidacja się nie powiedzie,
   używany jest kodek prosty.
4. Każda inna/nieznana wartość `type` (w tym potwierdzone `3`) → domyślnie
   kodek prosty.

W KAŻDYM z powyższych przypadków token ucieczki jest dodatkowo wybierany
per klatka metodą próby+walidacji opisaną w §4.3 (najpierw `0x0003`, potem
`0x0000`).

**Ważna obserwacja poboczna:** w `PAUSE.RES` (kodek RLE parami, `type=4`)
ostatni wiersz niektórych klatek bywa niekompletny — dane po prostu się
kończą, zanim wiersz osiągnie pełną szerokość. To sugeruje, że **końcowe
przezroczyste piksele/wiersze nie muszą być jawnie zakodowane** — brak
dalszych danych = domyślna przezroczystość do końca klatki. Z tego powodu
walidacja w punkcie 3 dopuszcza niekompletność tylko dla **ostatniego**
wiersza, nie dla żadnego innego.

---

## 5. Kontenery wieloklatkowe

Pojedynczy plik `.RES` może zawierać wiele obrazów sklejonych sekwencyjnie, każdy ze
swoim pełnym nagłówkiem (16 B) + paddingiem (4 B) + danymi. Po zdekodowaniu jednej
klatki, następna zaczyna się dokładnie w miejscu, gdzie skończyły się dane poprzedniej.

Potwierdzone przykłady:
- `PAUSE.RES` → **64 klatki** (animacja obrotu postaci na spadochronie), plik zużyty
  w 100% (0 bajtów resztek)
- `KRANNORM.RES` → **190 klatek** (animacja żurawia/haka z migającym światełkiem
  ostrzegawczym), plik zużyty w 100% (0 bajtów resztek), `type=1`
- `COLOR.RES` → **46 klatek** (kolorowe kulki/gemy, każda w innym odcieniu), plik
  zużyty w 100% (0 bajtów resztek), `type=7`, escape=`0x0000`
- `BUTTON.RES` → **7 klatek** (pełny zestaw stanów przycisków UI: wł./wył.,
  strzałki nawigacji przód/wstecz), plik zużyty w 100%, `type=2`
- `FUNKEN2.RES` → **10 klatek** (animacja rozpraszającej się iskry), plik zużyty
  w 100%, `type=7`, kodek prosty
- `CORAIN.RES` → **33 klatki** (animacja rozbłysku/eksplozji rozpadającego się na
  cząsteczki), plik zużyty w 100%, `type=7`, kodek prosty
- `BLOCK.RES` → **2 klatki**, `type=4`
- `BLOCKR.RES` / `BLOCKL.RES` → **8 klatek każdy** (pomarańczowy trójkątny
  wskaźnik kierunkowy w prawo/lewo, różne fazy pulsowania), `type=4`
- `GAMMA.RES` → **10 klatek** (przyciski menu z niemieckimi napisami, np.
  "Optionen"), plik zużyty w 100%, `type=3` (nowa wartość, kodek prosty)
- `KEXPLO.RES` → **29 klatek** (animacja eksplozji: jasna chmura → dym →
  żarzące się resztki), plik zużyty w 100%, `type=7`
- `SMLMENU.RES` → **7 klatek** (menu główne "SINGLE PLAYER / MULTI PLAYER /
  INFO / HIGHSCORE / OPTIONS / SWING OUT" + warianty podświetlenia każdej
  pozycji), plik zużyty w 100%, `type=6` (nowa wartość, kodek RLE parami)
- `SMRM1.RES` → **12 klatek** (menu trybu gry: "Sudden Death", "New", "Load",
  poziomy trudności Easy/Normal/Hard/Expert/Custom + podświetlenia), plik
  zużyty w 100%, `type=6`
- `SMRM2.RES` → **6 klatek** (menu "Competition / Arcade / Splitscreen / New /
  Network / Join" + podświetlenia), plik zużyty w 100%, `type=6`

---

## 6. Otwarte problemy i niepewności

### 6.1 Fałszywe wykrywanie granicy klatki — ✅ rozwiązane
Wcześniej sądzono, że `BUTTON.RES` ma tylko 2 prawdziwe klatki, a reszta pliku to
szum powstały z przypadkowego trafienia wzorca nagłówka. Po poprawce tokenu
ucieczki (§4.3) okazało się, że to były **prawdziwe, poprawne klatki**, po prostu
źle dekodowane. Wszystkie 11 przebadanych plików `.RES` zużywają się teraz w 100%
(0 bajtów resztek) z aktualnym dekoderem.

### 6.2 `FONTS.RES` nie pasuje do modelu nagłówka — JEDYNY nierozwiązany problem
Parsowanie standardowym nagłówkiem 16 B dało bezsensowne wartości
(`w=3, h=57349`) — plik ma **inną strukturę na najwyższym poziomie**.

**Stan dochodzenia (wypróbowane i odrzucone hipotezy):**
- Nie jest to format archiwum opisany w §10 — pierwsze 4 bajty jako "liczba
  wpisów" (=3) nie prowadzą do sensownych 12-bajtowych nazw ASCII w
  spodziewanym miejscu.
- Przeszukano cały plik (64047 B) w poszukiwaniu osadzonych standardowych
  nagłówków obrazów (`magic=0x0014`, `const_0f=0x0F`) — **zero trafień**.
  Glify nie są więc zapisane jako standardowe obrazy `.RES`.
- Bajty 16–136 (121 B) to same zera, pierwszy niezerowy bajt pojawia się
  dopiero na offsecie 137 — sugeruje jakąś tabelę (szerokości znaków?
  offsety do glifów?), ale żadna prosta wielkość rekordu (1, 2 lub 4 bajty
  na wpis) nie daje sensownego podziału pasującego do standardowego
  zakresu ASCII (znaki drukowalne zaczynają się od kodu 32).
- Wypróbowano renderowanie surowych bajtów jako bitmapy (RGB555 i skala
  szarości 8-bit) przy różnych szerokościach (8–256 px) — żaden wariant
  nie ujawnił czytelnych kształtów liter.
- Sprawdzono hipotezę "3 kopie kolorystyczne tej samej czcionki" (podział
  danych na 3 równe części) — obalona; środkowa część zawiera powtarzający
  się wzorzec wypełniający (`0x0300` w kółko), nie dane pikseli.

**Do zbadania w przyszłości:** analiza `SWING.EXE` pod kątem kodu
renderującego tekst może ujawnić dokładny układ tego formatu (np. przez
znalezienie funkcji `DrawText`/`DrawChar` i prześledzenie, jak indeksuje
dane z `FONTS.RES`).

### 6.3 `CORAIN.RES` — ✅ rozwiązane
Wcześniej dekodował się "bez błędu", ale renderowany obraz przypominał zaszumione
ukośne pasy. Przyczyną był błędny token ucieczki (patrz §4.3) — po poprawce
(próba `0x0003`→`0x0000` per klatka z walidacją, zamiast akceptowania obu naraz)
plik dekoduje się czysto jako **33-klatkowa animacja rozbłysku/eksplozji**
rozpadającego się na pojedyncze cząsteczki, zużywając plik w 100%.

### 6.4 Znaczenie pola `extra` i dokładne znaczenie 4 B paddingu
Nieznane. Sprawdzono i **obalono** hipotezę, że `extra` = token ucieczki (działało
przypadkiem dla `COLOR.RES`, ale łamało `FUNKEN2.RES` — patrz §4.3). Obserwowane
wartości `extra`: `0` (FUNKEN2, CORAIN) oraz `3` (CD, PAUSE, BUTTON, KRANNORM).
Padding zawsze pomijany — nie sprawdzono systematycznie, czy zawsze jest zerowy
we wszystkich 66 plikach.

### 6.5 Plik `SWING.EXE` jeszcze nie przeanalizowany
Może zawierać dodatkowe wskazówki (np. tabele offsetów zasobów, jawne stałe
formatu, ewentualną paletę) — wciąż do zbadania.

---

## 7. Narzędzie konwertujące

Powstała samodzielna aplikacja HTML/JS (`RES_to_PNG_Converter.html`) implementująca
oba potwierdzone kodeki (§4.1, §4.2), automatycznie wybierane na podstawie pola
`type`. Działa w pełni lokalnie w przeglądarce (bez wysyłania plików na serwer),
obsługuje kontenery wieloklatkowe, eksport pojedynczych PNG oraz zbiorczy eksport
ZIP wszystkich klatek.

---

## 8. Dziennik ustaleń (chronologicznie)

1. **CD.RES** (32×32, `type=4`) — pierwszy złamany plik. Ustalono strukturę
   nagłówka, kodek RLE parami, oraz (błędnie na starcie) format koloru RGB565 →
   poprawiono na **RGB555** po teście na `PAUSE.RES`.
2. **PAUSE.RES** (64 klatki, `type=4`) — potwierdzenie, że pliki mogą być
   kontenerami wielu sklejonych obrazów; 100% zgodność rozmiaru pliku z sumą klatek.
3. **BUTTON.RES** (`type=2`) — odkryto **drugi kodek** (prosty strumień bez
   licznika po escape); poprzedni algorytm (z `type=4`) powodował widoczne
   zniekształcenia obrazu przez błędne "zjadanie" kolejnych pikseli jako liczników.
4. **FUNKEN2.RES** (`type=7`) — potwierdzono, że ten sam prosty kodek pasuje
   też do `type=7` (mały 8×8 sprite "iskry", poprawnie odczytany).
5. **CORAIN.RES** (`type=7`) — kodek formalnie "działa" (zużywa dokładnie
   właściwą liczbę słów), ale wynik wizualny budzi wątpliwości — otwarty problem.
6. **FONTS.RES** — nie pasuje do modelu nagłówka w ogóle — otwarty problem.
7. **KRANNORM.RES** (`type=1`, 190 klatek) — odkryto **trzecią wartość `type`
   mapującą się na już znany kodek RLE parami** (ten sam co `type=4`), a nie na
   nowy, osobny kodek. Wcześniejsza wersja konwertera (traktująca "wszystko poza
   `type=4`" jako kodek prosty) błędnie stosowała do tego pliku kodek prosty,
   co dawało zniekształcony obraz — poprawiono, dodając `type=1` do grupy RLE
   parami. Animacja żurawia/haka z migającym światełkiem zdekodowana bezbłędnie,
   plik zużyty w 100%.
8. **COLOR.RES** (`type=7`, 46 klatek, kolorowe kulki/gemy) — odkryto, że token
   ucieczki nie zawsze jest równy `0x0003` — ten plik używa `0x0000`. Sprawdzono
   kilka hipotez (m.in. że escape = wartość pola `extra` z nagłówka — okazała się
   fałszywa, obalona na `FUNKEN2.RES`). Rozwiązanie z tamtej sesji (akceptować
   **oba** tokeny jednocześnie) okazało się niepoprawne — patrz punkt 9.
9. **Regresja i poprawka tokenu ucieczki** — zgłoszono, że `KRANNORM.RES`
   (wcześniej perfekcyjny) zaczął się "łamać" na częściach klatek (zakresy
   0–36 i 88–189 z 190), a `BLOCK.RES`/`BLOCKR.RES` dostały dziury/przesunięcia,
   mimo że `BLOCKL.RES` pozostał poprawny w obu wersjach. Diagnostyka wykazała
   dokładną korelację: zepsute klatki `KRANNORM.RES` to te zawierające legalny
   literalny piksel o wartości `0` (czysta czerń), błędnie zjadany jako escape.
   **Poprawka:** token ucieczki wybierany jest per klatka metodą próby+walidacji
   (najpierw `0x0003`, w razie niepowodzenia `0x0000`), nigdy oba naraz — patrz
   §4.3. Naprawiło to regresję (KRANNORM 190/190, BLOCK/BLOCKR/BLOCKL czyste) BEZ
   utraty wcześniejszych postępów (COLOR/BUTTON/FUNKEN2 nadal poprawne) i jako
   nieoczekiwany bonus **rozwiązało też odwieczny problem szumu w `CORAIN.RES`**
   (§6.3) — okazał się być tym samym błędem tokenu ucieczki. Wszystkie 11 znanych
   plików `.RES` zużywają się teraz w 100% (0 B resztek).
10. **GAMMA.RES + GAMMA.SWG** — pierwsza napotkana para plików `.RES`+`.SWG`.
    `GAMMA.RES` ujawnił **nową wartość `type=3`** (225×60, 10 klatek — przyciski
    menu z niemieckimi napisami typu "Optionen"), obsłużoną poprawnie przez
    domyślny fallback (kodek prosty). `GAMMA.SWG` okazał się być **zupełnie
    innym formatem** — surową, nieskompresowaną bitmapą pełnoekranową 640×480
    RGB555 bez żadnego nagłówka (614400 B = dokładnie 640×480×2), przedstawiającą
    ekran ustawień korekcji gamma gry (4 podglądy logo "SWING" przy różnych
    poziomach jasności). Szczegóły w §9.
11. **KEXPLO.RES** (`type=7`, 29 klatek, animacja eksplozji) — pierwsza klatka
    (mały 14×15 obrazek) dekodowała się jako szum, mimo że walidacja z §4.3
    formalnie przechodziła zarówno dla `escape=3`, jak i `escape=0`. Odkryto,
    że przy złym tokenie ucieczki licznik przeskoku może osiągnąć niedorzeczną
    wartość (znaleziono `5251` dla obrazka o 210 pikselach) — dodano regułę
    odrzucającą próbę, gdy pojedynczy licznik przekracza `width*height` (patrz
    §4.5). Naprawiło to klatkę 0 bez regresji na pozostałych plikach.
12. **SMLMENU.RES / SMRM1.RES / SMRM2.RES** (menu gry) — odkryto **czwartą
    wartość `type=6`**, mapującą się na kodek RLE parami (jak `type=1` i `4`),
    a nie na kodek prosty (domyślny fallback dla nieznanych `type`, który był
    źle dobierany, dając częściowo poprawny, częściowo zaszumiony obraz —
    dokładnie objaw opisany przez użytkownika: "przesunięte belki/szum").
    Po dodaniu `type=6` do grupy RLE parami wszystkie trzy pliki dekodują się
    w 100% jako kompletne, wielopozycyjne menu gry (menu główne, wybór trybu,
    poziom trudności) wraz z wariantami podświetlenia każdej pozycji.
13. **EXTRAS.RES + HELPMODE.RES** — odkryto, że to **NIE są obrazy**, tylko
    **archiwa/paczki** zawierające wiele nazwanych podplików (widoczne czytelne
    nazwy ASCII w środku, np. `HEDGE.3LB`, `STONE.3LB`, `GSTAR.6SP`, `M00.DAT`).
    Zrekonstruowano format kontenera (patrz §10) — każdy podplik o rozszerzeniu
    `.3LB`/`.6SP` okazał się być zwykłym, już znanym plikiem `.RES` (zaczyna się
    od `magic=0x14, type=1`), dekodującym się bezbłędnie tym samym dekoderem.
    `EXTRAS.RES`: 38/38 podplików to obrazy (łącznie 1502 klatki — biblioteka
    **power-upów** do gry: kolczasty, kamienny, wieża, serce, czaszka,
    gwiazda, błyskawica/twist, flesz). `HELPMODE.RES`: 29/58 podplików to
    obrazy typu `.6SP` (1217 klatek) — **te same power-upy, ale w wyższej
    rozdzielczości (2× większe)**, pozostałe 29 to pliki `.DAT`
    (`M00.DAT`–`M44.DAT`) — prawdopodobnie teksty pomocy/dialogów, nie obrazy,
    nierozpoznawane tym dekoderem (inny cel, nie błąd). **Uwaga:** zwykłe,
    grywalne kulki (nie power-upy) NIE są w tych plikach — znalezione dopiero
    w formacie `.SET`, patrz punkt 14.
14. **NORMAL.SET + MAKE.SET + SHOWSET.EXE** (folder `KUGELN`) — namierzono
    wreszcie **zwykłe, grywalne kulki**. `NORMAL.SET` ("standard") zaczyna się
    od tekstowej sygnatury `"Gib mir 'ne Kugel\n"` (niem. "Daj mi kulkę") +
    nazwa zestawu, po czym następuje zwykły blok obrazów `.RES` — **46 kulek
    30×30 px**, dekodowanych bez żadnych zmian w dekoderze (format `.SET`
    opisany w §11). `MAKE.SET` okazał się fałszywym tropem — to zwykły
    makefile Watcom C/C++ do kompilacji `SHOWSET.EXE`, nie dane graficzne.
    Po bloku obrazów w `NORMAL.SET` zostaje 3033 B nierozpoznanej struktury,
    zaczynającej się identyczną sekwencją bajtów co `FONTS.RES` — poszlaka
    wskazująca na możliwy związek, odłożona na później zgodnie z priorytetem
    ustalonym przez użytkownika.

---

## 9. Format `.SWG` — surowe bitmapy pełnoekranowe

Niektóre zasoby graficzne występują jako osobny plik `.SWG` obok `.RES` o tej
samej nazwie (np. `GAMMA.RES` + `GAMMA.SWG`). To **zupełnie inny, znacznie
prostszy format** niż `.RES`:

- **Brak nagłówka** — plik zaczyna się od razu od danych pikseli
- **Brak kompresji** — każde 16-bitowe słowo (little-endian) to jeden piksel
  RGB555 (ten sam format koloru co w `.RES`, patrz §3), czytane wiersz po
  wierszu, bez żadnych tokenów ucieczki/przezroczystości
- **Stały rozmiar 640×480** — jedyny zbadany dotąd plik (`GAMMA.SWG`) ma
  dokładnie `640*480*2 = 614400` bajtów, co idealnie odpowiada tej rozdzielczości
  bez reszty
- Rezultat wizualny: pełnoekranowy ekran menu/ustawień gry (w wypadku
  `GAMMA.SWG` — ekran kalibracji gamma z czterema podglądami logo "SWING" przy
  różnych poziomach korekcji jasności i niemieckim tekstem interfejsu)

**Hipoteza robocza:** pliki `.SWG` to statyczne tła pełnoekranowe (menu, ekrany
ładowania, ustawienia), podczas gdy `.RES` to elementy UI/sprite'y nakładane na
te tła (w wypadku `GAMMA` — przyciski menu z `GAMMA.RES`). Nie sprawdzono jeszcze,
czy WSZYSTKIE pliki `.SWG` mają rozdzielczość 640×480, czy to może się różnić —
wymaga więcej próbek.

---

## 10. Format archiwum — pliki-paczki z nazwanymi podplikami

Niektóre pliki o rozszerzeniu `.RES` (np. `EXTRAS.RES`, `HELPMODE.RES`) wcale
nie są pojedynczym obrazem — to **archiwa** bundlujące wiele nazwanych
podplików, rozpoznawalne po tym, że standardowy nagłówek obrazu (§2) nie
pasuje (`magic ≠ 0x0014`), ale pierwsze bajty dają się odczytać jako liczbę
wpisów, po której następują czytelne nazwy ASCII w stylu 8.3 (np.
`HEDGE.3LB`, `GSTAR.6SP`).

**Struktura (w 100% zwalidowana — każdy bajt się zgadza):**

```
offset  rozmiar        pole           opis
0x00    u32            count          liczba wpisów w archiwum

Następnie `count` rekordów po 20 bajtów każdy:
0x00    char[12]       name           nazwa 8.3, dopełniona zerami (np. "HEDGE.3LB\0\0\0")
0x0C    u32            size           rozmiar danych tego wpisu w bajtach
0x10    u32            offset         offset danych wpisu, liczony od początku pliku

Zaraz po tabeli nagłówków: dane wszystkich wpisów, sklejone sekwencyjnie
w tej samej kolejności co tabela (offset pierwszego wpisu = koniec tabeli;
offset każdego kolejnego = offset poprzedniego + jego size).
```

Struct Python:
```python
count = struct.unpack_from('<I', data, 0)[0]
pos = 4
for i in range(count):
    name = data[pos:pos+12].split(b'\x00')[0].decode('ascii')
    size, offset = struct.unpack_from('<II', data, pos+12)
    pos += 20
```

**Zawartość podplików:** wpisy o rozszerzeniach `.3LB` i `.6SP` to zwyczajne
pliki w już poznanym formacie `.RES` (zaczynają się od `magic=0x0014,
type=1` — kodek RLE parami) — dekodowane bez żadnych zmian w istniejącym
dekoderze. Wpisy `.DAT` NIE są obrazami (nie pasują do nagłówka `.RES`) —
prawdopodobnie dane tekstowe/skryptowe (w `HELPMODE.RES` nazwy `M00.DAT`
do `M44.DAT` sugerują ponumerowane wiadomości/teksty pomocy).

**Potwierdzone przykłady:**
- `EXTRAS.RES` — 38 wpisów, wszystkie `.3LB`, wszystkie obrazy, plik zużyty
  w 100% (2467976/2467976 B). Zawartość: biblioteka **power-upów** do gry
  (zwykłe grywalne kulki są w osobnym formacie `.SET`, patrz §11).
- `HELPMODE.RES` — 58 wpisów (29× `.6SP` obrazy + 29× `.DAT` dane tekstowe),
  plik zużyty w 100% (7435338/7435338 B).

**Otwarte pytanie:** czy rozszerzenia `.3LB`/`.6SP` niosą jakieś dodatkowe
znaczenie (np. liczbę klatek animacji zakodowaną w nazwie), czy to tylko
dowolne etykiety nadane przez twórców gry — nie sprawdzono.

---

## 11. Format `.SET` — zestawy skórek kulek

Pliki `.SET` (folder `KUGELN` — niem. "kulki") to konfigurowalne w grze
**zestawy wyglądu kulek**. Struktura, potwierdzona na `NORMAL.SET`:

```
offset  rozmiar  pole            opis
0x00    19 B     signature       tekst ASCII "Gib mir 'ne Kugel\n" + bajt 0x00
0x14    12 B     name            nazwa zestawu, ASCII zero-padded (np. "standard")
0x20    4 B      unknown1        obserwowane: 0
0x24    4 B      unknown2        obserwowane: wartość niezerowa (możliwy checksum)
0x28    4 B      unknown3        obserwowane: 0
0x2C    4 B      imageBlockSize  rozmiar w bajtach bloku obrazów, który następuje
```

Zaraz po 48-bajtowym nagłówku zaczyna się **zwykły, już znany blok obrazów
`.RES`** (kontener wieloklatkowy, `type=1`/RLE parami) — dekodowany bez
ŻADNYCH zmian w istniejącym dekoderze. Pole `imageBlockSize` jest w
praktyce redundantne: istniejąca pętla dekodująca sama zatrzymuje się
dokładnie tam, gdzie kończy się ostatni prawidłowy nagłówek obrazu.

**Potwierdzony przykład — `NORMAL.SET`** (nazwa wewnętrzna: "standard"):
**46 kulek 30×30 px**, dokładnie te same barwy/wzory co w `COLOR.RES`
(jednokolorowe: niebieska, czerwona, zielona, turkusowa, fioletowa,
brązowa, czarna, magenta, pomarańczowa; wielobarwne/marmurkowe warianty;
srebrna; kulki z teksturą specjalną) — to najwyraźniej **standardowy,
domyślny zestaw kulek do gry**.

**Nierozpoznana reszta pliku:** po bloku obrazów (75624 z 78705 B)
zostaje 3033 B nieznanej struktury. Uwaga: te bajty zaczynają się
**dokładnie tą samą sekwencją** co pierwsze bajty `FONTS.RES`
(`01/03 00 00 00 | 03 00 05 e0 01 00 00 00` + długi ciąg zer) — silna
poszlaka, że to mniejsza instancja tej samej, wciąż nierozpracowanej
struktury (możliwe, że nazwy/etykiety kolorów kulek, zakodowane w tym
samym nieznanym formacie co czcionki). Odłożone na później zgodnie z
priorytetem — `FONTS.RES` i ta struktura nie są obecnie kluczowe.

**Plik `MAKE.SET` to fałszywy trop — nie jest to dane gry.** To zwykły
**makefile Watcom C/C++** (skrypt budowania) dla `SHOWSET.EXE`, przypadkiem
noszący rozszerzenie `.SET`. Zawiera jawny tekst: listę plików źródłowych
(`showset.obj`, `graphasm.obj`, `graphik.obj`, `newalloc.obj`), bibliotek
(`mss.lib`, `vidlib.lib`) i komend kompilatora (`wcc386`, `tasm`). Ciekawy
efekt uboczny: **ujawnia nazwy plików źródłowych narzędzia `SHOWSET.EXE`**
(podglądarki zestawów kulek) — przydatne, gdyby kiedyś analizować ten
plik wykonywalny.

---

*Ten dokument będzie aktualizowany po każdym kolejnym ustaleniu dotyczącym formatu.*
