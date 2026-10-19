# Krawędzie zasłonięte ścianami — diagnoza z 19 października 2026

Badany stan przed poprawką: lokalny commit `8375a13`, gałąź
`codex/guide-transforms-and-numeric-corrections`. Po diagnozie użytkownik
zlecił naprawę trzech opisanych przyczyn; poprawka jest w lokalnych źródłach.
Chodzi o zasłonięcie przez ścianę, a nie o atrybut `hidden` krawędzi.

## Wynik diagnozy przed poprawką

Potwierdzono trzy niezależne przyczyny. Gumka nie sprawdza zasłonięcia,
a istniejący filtr zaznaczania kliknięciem ma błędy w obu rzutach kamery.
Sama zamiana wyboru gumki na `pick_visible_edge` usuwa prosty przypadek,
ale nie wystarcza do rozwiązania wszystkich odtworzonych sytuacji.

### 1. Gumka wybiera przez ściany

`tools/eraser.py::EraserTool.on_hover` i `_mark` wywołują `pick_edge`.
`views/viewport.py::pick_edge` przekazuje `visible_only=False` do `_pick_edge`.
W tej gałęzi wygrywa najmniejsza odległość od rzutu odcinka na ekranie;
nie ma pytania, czy pomiędzy kamerą a odcinkiem znajduje się ściana.

Odtworzenie na zamkniętym pudełku `(-3,-3,0)`–`(3,3,2)`, kamera skierowana
na `(0,0,1)`, odległość 20, yaw −45°, pitch 30°:

1. Najedź na rzut środka tylnej pionowej krawędzi `(-3,3,1)`.
2. Zwykłe zaznaczanie w tym przykładzie wybiera ścianę.
3. Gumka wybiera tylną krawędź i po puszczeniu myszy usuwa ją wraz z jej
   dwiema przyległymi ścianami.
4. Przeciągnięcie od przedniej krawędzi `(3,-3,1)` do tego miejsca zbiera
   obie krawędzie w jednym ruchu.

Potwierdzone w perspektywie i rzucie równoległym. Ten sam wybór powoduje
także ukrywanie tylnej krawędzi przez Shift+gumkę oraz jej usunięcie klawiszem
Delete po najechaniu gumką bez kliknięcia. Esc anuluje ruch, a Cofnij/Ponów
odtwarza wynik; błąd powstaje przy ustalaniu celu, przed komendą historii.

### 2. Zaznaczanie w rzucie równoległym bada niewłaściwy promień

`SelectTool._pick` prawidłowo prosi o `pick_visible_edge`, ale
`Viewport._is_occluded` buduje promień od `camera.eye()` do badanego punktu.
W rzucie równoległym promienie dla różnych pikseli muszą być równoległe.
Promień od jednego punktu oka może minąć ścianę, która w rzeczywistym obrazie
zasłania wskazaną krawędź. `_occluded_many` korzysta z tego samego założenia.

Minimalne odtworzenie: viewport 1000×600, widok Top, rzut równoległy,
target `(5,3,0)`, distance 12. Ściana na z=1: prostokąt `(0,0)`–`(2,2)`;
krawędź na z=0: `(1.75,1,0)`–`(1.85,1,0)`. Jej środek projektuje się
w przybliżeniu na `(306.863,420.711)`. Rzeczywisty promień z
`_pixel_to_ray` trafia najpierw w ścianę, ale `_is_occluded` odpowiada False.
Kliknięcie zaznacza zasłoniętą krawędź, a późniejszy Delete może ją usunąć.

### 3. Zaznaczanie w perspektywie sprawdza inny punkt odcinka

`Viewport.edge_point_under_cursor` wyznacza parametr na rzucie 2D, a następnie
używa go bezpośrednio do liniowej interpolacji końców odcinka w 3D.
W perspektywie te parametry nie są równe, gdy końce mają różne głębokości.
Test zasłonięcia może więc dotyczyć odkrytej części odcinka zamiast miejsca
pod kursorem.

Odtworzenie: viewport 1000×600, Top, perspektywa, target `(1,1,0)`, distance 6;
ta sama ściana na z=1, odcinek `(-4,1,-8)`–`(4,1,0)`. Punkt
`(-0.588235,1,-4.588235)` pod pikselem około `(391.360,300)` jest zasłonięty.
Jednak pomocnik zwraca punkt około `(-2.066667,1,-6.066667)`, którego rzut
to `(315.933,300)` — ponad 75 px od kursora — i który nie jest zasłonięty.
W efekcie filtr przepuszcza niewidoczny fragment krawędzi do zaznaczenia.

## Zachowania, które trzeba odróżnić od tych błędów

- **Ramka zaznaczania:** oba kierunki działają na rzucie 2D, bez filtrowania
  głębokości (`_box_loose_fast` i `SelectTool.on_box_select`). Obejmują także
  tylne krawędzie; Delete usuwa potem cały taki wybór. To istniejąca reguła
  ramki. Jej zmiana oznaczałaby zmianę sposobu zaznaczania całych brył.
- **Łuki i okręgi:** kliknięcie segmentu rozwija wybór do całego konturu
  o wspólnym `curve`, również po stronie zasłoniętej (`Mesh.curve_edges`,
  `SelectTool._expand`, `EraserTool._mark`). To jawnie zaprojektowane działanie.
- **Szkielet i X-ray:** dopuszczają wybór przez ściany, zgodnie z obrazem.
- **Usunięcie zwykłej krawędzi bryły:** usuwa również jej przyległe ściany,
  ale nie pozostałe twarde krawędzie. Kontrola sześcianu: 12→11 krawędzi,
  6→4 ściany; znika dokładnie wskazana krawędź, przeciwległa pozostaje.
- **Sprzątanie miękkich krawędzi:** `EraseSelectionCommand` globalnie usuwa
  osierocone `soft` krawędzie. Potwierdzono usunięcie wcześniej istniejącej,
  niezależnej miękkiej linii przy kasowaniu zwykłej linii w innym miejscu.
  To poboczny problem zakresu sprzątania; nie wyjaśnia twardych tylnych
  krawędzi poprawnego pudełka.

## Weryfikacja diagnozy przed poprawką

Lokalne reprodukcje są w `../qa/test_occluded_edge_investigation.py`,
`../qa/test_occluded_selection_investigation.py` oraz
`../qa/test_erase_scope_investigation.py`, poza repozytorium Git.
**Są to testy diagnostyczne stanu sprzed poprawki: zaliczenie przypadku błędu
potwierdzało jego odtworzenie, a nie naprawę.** Używają prawdziwego `Viewport`,
macierzy kamery i komend historii; nie wymagają renderowania OpenGL.
Ich oczekiwania opisujące błąd po naprawie powinny zawodzić. Nowe testy
regresyjne poprawnego działania są wersjonowane w `tests`.

Pierwszy plik: 20 zaliczonych obserwacji, w tym oba rzuty, usuwanie,
przeciąganie, Shift, Delete z hover, Esc, Cofnij/Ponów, ramka i kontrole
X-ray/szkielet. Wynik: `../qa/occluded-edge-investigation.log`.
Zaznaczanie: 7 zaliczonych obserwacji, w tym oba błędne kliknięcia,
sprawdzenie rzeczywistego promienia projekcji, hover, Delete/Cofnij i poprawne
przypadki kontrolne. Zakres usuwania: 3 zaliczone obserwacje (pudełko, cały
kontur walca i globalne sprzątanie osieroconej miękkiej krawędzi).
Wyniki zapisano obok w logach `occluded-selection-investigation.log`
i `erase-scope-investigation.log`. Razem to 30 nowych obserwacji diagnostycznych.

Oddzielnie uruchomiono 52 istniejące testy: `test_tape_eraser.py`,
`test_select_edge_over_group.py`, `test_pick_hidden_group_edge.py`,
`test_box_select.py`, `test_select_modifiers.py` i `test_erase_selected_segments.py`.
Wszystkie przeszły (`../qa/occluded-edge-adjacent.log`), co pokazuje również
brak pokrycia odtworzonych błędów w tym istniejącym zestawie. Nie jest to
wynik całego projektu. `git diff --check` nie zgłasza błędów białych znaków.

## Wprowadzona poprawka lokalna

- `tools/eraser.py`: podgląd i zbieranie celów ruchu korzystają z
  `pick_visible_edge`, tak jak zaznaczanie. Dotyczy też Shift+gumki i celu
  Delete z podświetlenia. Zachowano fallback `pick_edge` dla prostych adapterów.
- `views/viewport.py::edge_point_under_cursor`: odwzorowanie parametru
  ekranowego uwzględnia `clip.w` obu końców odcinka z tej samej macierzy MVP.
  Sprawdzenie widoczności dotyczy punktu pod kursorem także dla długich,
  skośnych krawędzi i perspektywy dwupunktowej.
- `Viewport._occlusion_ray`, `_is_occluded`, `_occluded_many`: w rzucie
  równoległym promień biegnie zgodnie z kierunkiem projekcji. Sprawdzanie
  od punktu ku płaszczyźnie near zapobiega błędom float32 przy odległym
  początku promienia i zachowuje tolerancję 1 mm przy punkcie. Uwzględnia
  także geometrię widoczną za pozycją oka. Zbiorcze obliczenia mają osobny
  początek dla każdego promienia, zachowując podział na bloki i szybki
  wariant wspólnego oka w perspektywie.

Zachowano zasady ramki, całych krzywych, X-ray/szkieletu, warstw i przekroju.
Poboczna obserwacja globalnego sprzątania osieroconych `soft` krawędzi nie
wchodzi w zakres tej poprawki.

Nowe regresje: `tests/test_eraser_visible_edges.py` oraz
`tests/test_occluded_edge_picking.py`. Obejmują odrzucenie zasłoniętego celu,
częściowo widoczne krawędzie, obie projekcje i perspektywę dwupunktową,
grupy i edycję grup, warstwy, przekroje, near clipping, precyzję na własnej
ścianie przy distance=10000/far=40000 oraz zgodność obliczeń pojedynczych
i zbiorczych przy 66 spanach i wymuszonych małych blokach. Interakcje obejmują
podgląd, kliknięcie, przeciąganie, Shift, Esc, Delete i Cofnij/Ponów.

Przed naprawą pierwsze wersje testów wykazały 14 błędów gumki i 13 błędów
wybierania. Lokalne logi: `eraser-visible-before.log` oraz
`occluded-picking-before.log` w `../qa`.

Końcowa weryfikacja poprawki: **462 zaliczone, 2 pominięte** w jednym
uruchomieniu 31 plików, w tym **57 nowych regresji** (25 gumki i 32
wybierania/zasłonięcia). Wspólny zestaw obejmuje także dotychczasowe testy
historii usuwania, warstw/ukrywania, ramki i modyfikatorów zaznaczania,
indeksu wybierania, wymiarów, zasłonięcia zbiorczego, przekroju, grup,
pamiętania równoległości i odniesień prostopadłych/przecięć.
Log: `../qa/occluded-edge-fixed-adjacent.log`.
Kontrola `.venv/Scripts/python.exe main.py --check` zakończona OK
(`../qa/occluded-edge-startup-check.log`); brak konwertera DWG pozostaje
znanym ograniczeniem. `git diff --check` nie zgłasza błędów białych znaków.

Nie wykonywano ręcznej próby w normalnym oknie ani pełnego zestawu testów.
Nie przygotowano nowego commitu ani publikacji.
