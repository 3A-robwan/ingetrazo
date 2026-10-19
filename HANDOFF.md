# Przekazanie IngeTrazo — 19 października 2026

## Od czego zacząć

Po lokalnym punkcie zapisu użytkownik zlecił zbadanie i naprawę wybierania
krawędzi zasłoniętych ścianami. W lokalnych źródłach są trzy poprawki:
gumka i jej podgląd używają wyboru widocznych krawędzi; zasłonięcie w rzucie
równoległym korzysta z kierunku projekcji (również zbiorczo); punkt pod
kursorem na odcinku w perspektywie uwzględnia wagi `clip.w`.
Główne pliki: `tools/eraser.py`, `views/viewport.py`. Zasady ramki, całych
krzywych, X-ray i szkieletu pozostają. Nie zmieniano sprzątania osieroconych
miękkich krawędzi, które zaobserwowano pobocznie podczas diagnozy.

Dokładne sceny i zakres poprawki: `docs/occluded-edge-investigation.md`.
Nowe regresje są w `tests/test_eraser_visible_edges.py` oraz
`tests/test_occluded_edge_picking.py`; pierwsze wersje przed naprawą wykazały
odpowiednio 14 i 13 błędów. Starsze pliki `../qa/test_*_investigation.py`
opisują celowo stan błędny sprzed poprawki i nie są testami regresji naprawy.
Na polecenie użytkownika opublikowano wszystkie obecne poprawki na forku:

- [Wydanie eksperymentalne z 19 października](https://github.com/3A-robwan/ingetrazo/releases/tag/robwan-experimental-2026-10-19),
  tag `robwan-experimental-2026-10-19`, commit
  `8d5d9a8fcb53786f2403fd7afc64f46a9f63a907`.
- [Ogłoszenie upstream Discussions #752 / Show and tell](https://github.com/ingelibre/ingetrazo/discussions/752)
  zawiera listę ulepszeń, link do wydania i prośbę o uwagi w odpowiedziach.
- README i opis zmian wskazują nowe wydanie. To nadal nieoficjalne źródła
  wymagające Pythona 3.12+, bez nowego instalatora/EXE i bez aktualizacji bazy.

Publikację wykonano przez połączone konto GitHub; lokalny Git nie ma danych
logowania do wysyłania. Drzewo commitu wydania jest identyczne z lokalnym
punktem `9df67a4` (sprawdzono hashe wszystkich 34 zmienionych plików i całego
drzewa). Wcześniejszą lokalną historię, w tym `8375a13` i `9df67a4`, zachowano
na gałęzi `codex/local-before-github-2026-10-19`. Bieżąca gałąź ponownie
śledzi `fork/codex/guide-transforms-and-numeric-corrections`; po wydaniu
dochodzi jedynie zapis stanu publikacji w dokumentacji. Nie przesuwaj tagu
wydania przy późniejszych zmianach.

Świeża kontrola publikacji: **386 zaliczonych, 4 pominięte**, 31 dobranych
plików, w tym wszystkie 57 nowych regresji; `main.py --check` i
`git diff --check` przechodzą. Log `../qa/github-release-2026-10-19-tests.log`
zawiera polecenie z pełną listą. To inny zakres niż wcześniejsze 462/2.

Końcowa weryfikacja: **462 zaliczone, 2 pominięte** w jednym uruchomieniu
31 plików, w tym 57 nowych regresji. Log `../qa/occluded-edge-fixed-adjacent.log`.
Sprawdzono oba rzuty, perspektywę dwupunktową, częściowo widoczne krawędzie,
grupy/edycję grup, warstwy, przekrój, Shift, Esc, Delete, Cofnij/Ponów,
precyzję na własnej ścianie i zgodność obliczeń pojedynczych/zbiorczych.
Kontrola `main.py --check` i `git diff --check` przechodzą. Nie wykonywano
ręcznej próby w normalnym oknie ani pełnego zestawu projektu.
Kolejny krok: próba użytkownika na jego modelu lub kolejne wskazane zadanie.
Po zmianie źródeł trzeba ponownie uruchomić aplikację przez launcher.
Ogłoszenie jest opublikowane; nie dodano automatycznego monitorowania odpowiedzi.

Odczytaj `AGENTS.md`, a następnie `git status --short`, `git log -3 --oneline`
i odpowiedni fragment `docs/experimental-changes.md`. Nie trzeba odtwarzać
całej poprzedniej rozmowy ani ponownie pobierać repozytorium.

## Lokalizacja i historia

- Folder projektu na tym komputerze:
  `C:/Users/Administrator/Documents/ChatGPT/IngeTrazo`.
- Właściwe repozytorium: podfolder `source`; środowisko Python 3.12 i PySide6
  6.11.2: `source/.venv`. Git w folderze nadrzędnym jest osobnym pustym repo;
  polecenia historii i commitów wykonuj w `source`.
- Gałąź: `codex/guide-transforms-and-numeric-corrections`.
- Baza: `d8ee8c068f0b1a26fe1a84a8489d3facb3fa22bf` z 13 października 2026.
  Program nadal podaje wersję 0.5.8. Nie są to najnowsze źródła upstream.
- Poprzednio opublikowany punkt: `514ff849778b672f2ccd70ad5fc4830003226f6c`.
  [Eksperymentalne wydanie źródeł z 18 października](https://github.com/3A-robwan/ingetrazo/releases/tag/robwan-experimental-2026-10-18).
- Bieżące wydanie: `8d5d9a8`, tag `robwan-experimental-2026-10-19`;
  późniejszy commit dokumentacji nie zmienia kodu wydania.
- `origin`: `https://github.com/ingelibre/ingetrazo.git`;
  `fork`: `https://github.com/3A-robwan/ingetrazo.git`.
- Punkt zapisu z 19 października `8375a13` dodał ten dokument i poprawki
  opisane niżej. Nowy snapshot obejmuje także późniejsze poprawki wybierania
  zasłoniętych krawędzi. Bieżący hash odczytaj przez `git log`.
- Nie aktualizowano bazy: wcześniejsza próba połączenia z nowszym upstream
  wskazała osiem konfliktów. Aktualizacja wymaga osobnego zadania i sprawdzenia.

## Co zawiera lokalna kopia

### Już opublikowane w 514ff84

- Dynamiczne przełączanie Orbit/Pan klawiszem Shift podczas trzymania myszy,
  z trwałą opcją domyślnie włączoną w Preferencjach.
- Poprawianie wartości liczbowej po zakończeniu operacji w narzędziach
  rysowania i transformacji; kolejne korekty zajmują jeden krok Cofnij.
- Ctrl+A obejmuje pomocnicze linie i punkty. Przesuń (M) i Obrót (Q) obsługują
  prowadnice, podgląd, kopiowanie, szyki, Esc i Cofnij/Ponów.

### Nowsze poprawki opublikowane w wydaniu z 19 października

| Obszar | Oczekiwane zachowanie i główne pliki |
| --- | --- |
| Usuwanie odcinków | Z zamkniętego obrysu na ścianie znikają wyłącznie wskazane odcinki. Pozostałe zostają jako linie na scalonej powierzchni. `core/history.py`, `core/mesh.py`; `edges_to_remove` jest opcjonalne, domyślne czyszczenie szwów pozostaje dostępne. |
| Pamiętanie równoległości | Postój na wnętrzu krawędzi przez 0,5 s nabywa kierunek. Preferencje: 0,1–10 s. Wierzchołki nie przejmują kierunku. Skrzyżowanie z krawędzią, postój na przecięciu oraz powrót zachowują odniesienie i dokładne trafienie; Shift je blokuje. `core/inference.py`, `core/snap.py`, `views/viewport.py`. |
| Linie pomocnicze jako odniesienia | Kierunek prowadnicy podlega temu samemu czasowi. Ukryte/zasłonięte/wykluczone prowadnice i punkty nie dostarczają kierunku. Pick modelowej krawędzi pozostaje oddzielny. |
| Grubość podświetlenia | Dwa ustawienia 1–3 px, domyślnie 2: niebieska krawędź pod kursorem i pomarańczowe zaznaczenie. Rysowanie offsetowymi przebiegami GL z testem głębokości działa również na sterownikach ograniczających szerokie linie. Preferencje mają przewijanie i zapis/Anuluj. |
| Długość z zapamiętanego punktu | Od środka boku prostokąta można narysować prostopadły odcinek do środka prostokąta, wskazując wcześniej środek sąsiedniego boku. Przerywana prowadnica, kolor i Shift pozostają. `SnapResult` ma opcjonalne `constraint_dir`/`constraint_color`; `_acquired_point_on_line` obsługuje wspólne trafienie kierunku i punktu odniesienia. |
| Zaokrąglanie wewnętrznego narożnika | Łuk aktualizuje także otwór otaczającej ściany; dawny narożnik nie zostaje w jej danych i nie tworzy połączeń przy późniejszym przesuwaniu. `tools/arc.py::_TrimCornerCommand` scala fragment narożnika z właścicielem otworu przed usunięciem odcinków i sprząta osierocone wierzchołki. Zachowuje atrybuty hosta (także puste), obsługuje przeciwny zwrot normalnych w scalaniu, korekty promienia/segmentów i Cofnij/Ponów. Alt zachowuje odcinki. |

## Weryfikacja i jej granice

Poniższe wyniki to oddzielne, częściowo nakładające się uruchomienia, nie suma
wszystkich testów. Lokalne logi i obrazy znajdują się w folderze projektu `qa`.

| Zakres | Obserwowany wynik | Lokalny log |
| --- | --- | --- |
| Kontrola publikacji z 19 października | 386 zaliczonych, 4 pominięte; 31 plików, w tym wszystkie 57 nowych regresji. | `qa/github-release-2026-10-19-tests.log` |
| Wybieranie zasłoniętych krawędzi (przed publikacją) | 462 zaliczone, 2 pominięte, w tym 57 nowych regresji; 31 plików. | `qa/occluded-edge-fixed-adjacent.log` |
| Wspólny zestaw przed przekazaniem | 333 zaliczone: wszystkie 14 nowych plików regresji oraz istniejące testy łuków, historii, pamiętania krawędzi i orientacji po usuwaniu. | `qa/handoff-checkpoint-tests.log` |
| Narożnik na istniejącej ścianie + sąsiednie mechanizmy | 228 zaliczonych; 15 nowych przypadków. Dziewięć początkowych regresji nie przechodziło przed naprawą. | `qa/arc-inset-adjacent.log` |
| Prostopadłość i długość z punktu | 381 zaliczonych; 57 nowych przypadków. | `qa/perpendicular-midpoint-adjacent.log` |
| Równoległość z prowadnic | 286 zaliczonych oraz osobno 19 testów wybierania/precyzji. | `qa/parallel-guide-adjacent.log` |
| Grubość podświetlenia | 148 zaliczonych, 3 GL pominięte w offscreen. | `qa/edge-highlight-adjacent.log` |
| Usuwanie wskazanych odcinków | 17 nowych regresji oraz osobno 127 testów sąsiednich. | Opis w `docs/experimental-changes.md` |

Natywne renderowanie Windows OpenGL sprawdzono w ukrytych widgetach, a obrazy
obejrzano: grubości 1/2/3 przy skalowaniu 100% i 200% oraz prowadnica
prostopadłości. Dla łuku `qa/rounded-inset-control.png` pokazuje dawną dziurę,
a `qa/rounded-inset-fixed.png` pełną powierzchnię; log
`qa/rounded-inset-pixels.log` potwierdza przywrócone pole i brak dawnego wierzchołka.
Nie zastępuje to ręcznej próby wszystkich interakcji w normalnym oknie programu.

Pełny zestaw projektu nie jest zielony: wcześniejsza próba dała 4567 zaliczonych,
30 pominiętych i 5 błędów (tekst 3D i rozszerzenia), a część partii przerwał
natywny błąd Qt. Trzy błędy tekstu i jeden rozszerzeń odtworzono na czystej bazie;
drugiego błędu rozszerzeń nie sprawdzono osobno na bazie. Pełnego zestawu nie
powtarzano dla każdej późniejszej zmiany.

W Windows istnieje też błąd Qt przy kończeniu poprawnie wykonanego pytest.
`scripts/windows_pytest_exit.py` to wersjonowana kopia użytego lokalnego
`../qa/windows_pytest_exit.py`: po raportowaniu kończy wyłącznie własny proces
z rzeczywistym wynikiem pytest. Awaria w trakcie testu nadal jest błędem.

Przykład sprawdzenia (PowerShell w repozytorium `source`):

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
$env:PYTHONPATH = Join-Path (Get-Location).Path 'scripts'
$env:PYTEST_PLUGINS = 'windows_pytest_exit'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_arc_inset_corner.py tests/test_arc_rounds_corners.py
.\.venv\Scripts\python.exe main.py --check
```

## Start programu i pliki lokalne

- Użytkownik uruchamia `Uruchom-IngeTrazo.cmd` w głównym folderze projektu;
  wywołuje on `source/.venv/Scripts/python.exe main.py --new-window`.
  `--new-window` otwiera poprawioną kopię również obok zwykłej instalacji.
- To źródła uruchamiane w Pythonie, bez nowego instalatora/EXE. Kontrola
  `--check` przechodzi. Brak zewnętrznego konwertera DWG to znane ograniczenie.
- `../Poprawki-IngeTrazo.md` i `../Wymiary-po-operacji.md` to opisy po polsku.
  `docs/experimental-changes.md` opisuje zmianę zachowania i testy w repozytorium.
- `../IngeTrazo-poprawki.patch` obejmuje całość względem `d8ee8c0`, nie tylko
  ostatni commit. Nie nakładaj go ponownie na tę już zmodyfikowaną kopię.
  Lokalny generator: `../qa/build_local_patch.py` (kontroluje składnię/JSON,
  `git diff --check` i odwróconą aplikowalność patcha).
- Foldery `qa`, `issues-report`, launcher i dokumenty w katalogu nadrzędnym
  pozostają lokalnymi plikami poza repozytorium `source`. Nowy klon Git nie
  odtworzy ich ani środowiska `.venv`. Podstawowe instrukcje, przekazanie,
  źródła, testy i pomocnik kończenia pytest są wersjonowane.

## Wcześniejsze tematy użytkownika — bez nowej weryfikacji

To lista informacji do zachowania, a nie zadania do automatycznego rozpoczęcia:

- W 0.5.8 wymiary dodane z zewnątrz komponentu przesuwają się po wejściu
  w edycję i wracają po wyjściu. Ta konkretna obserwacja nie dotyczy zwykłej grupy.
- Wymiar dodany wewnątrz grupy/komponentu zostaje w miejscu po zamknięciu
  i przesunięciu obiektu. Wymiary nie podążają też za podglądem Move/Rotate,
  choć działają podczas Scale. Powyższe poprawki tego nie naprawiają.
- Move zaznaczonej całej luźnej bryły do wierzchołka innego prostokąta na YZ
  potrafił cofać operację; cel w środku krawędzi działał. Brak nowej weryfikacji.
- Prawie prostopadłe do ekranu ściany/krawędzie trudno wybrać oraz grupa może
  mieć stary obszar klikania po przesunięciu geometrii w jej wnętrzu. Zgłoszone
  na 0.5.7; potwierdzenia na obecnej zmodyfikowanej kopii brak.
- Wyrównanie tekstu wymiaru do linii użytkownik odłożył (pominięty punkt 4).
  Pytania o grupy zagnieżdżone, siatkę punktów zaznaczenia czy zoom nie stanowią
  automatycznego zlecenia zmian.
- Archiwalne zgłoszenia: [#621](https://github.com/ingelibre/ingetrazo/issues/621)
  (uwagi zbiorcze), [#627](https://github.com/ingelibre/ingetrazo/issues/627)
  (prowadnice), [#631](https://github.com/ingelibre/ingetrazo/issues/631)
  (usuwanie obrysu). Ich bieżącego stanu nie sprawdzano podczas przekazania.
  Pliki zgłoszeń i raport `../issues-report` są historycznymi materiałami;
  nie należy z nich wyciągać aktualnej liczby nierozwiązanych problemów.
  `../Closed-outline-delete-issue.md` i `../Tape-Measure-guide-issue.md` opisują
  dawne błędy upstream; nie są opisem stanu naszej poprawionej kopii.
