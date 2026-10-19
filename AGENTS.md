# IngeTrazo — wskazówki do kontynuacji

To nieoficjalna kopia IngeTrazo z poprawkami zamówionymi przez użytkownika.
Rozmawiaj z użytkownikiem po polsku. Zachowuj istniejący styl kodu, oznaczenia
autorstwa i licencję GPL-3.0-or-later.

## Kontekst

- Przy przejmowaniu pracy w nowym wątku przeczytaj `HANDOFF.md`. Szczegółowe
  zachowanie i wyniki sprawdzeń opisuje `docs/experimental-changes.md`.
- Bieżący kod i `git status` mają pierwszeństwo przed historycznym opisem stanu.
  Zachowuj wcześniejsze poprawki i niezapisane zmiany użytkownika.
- W lokalnym układzie Windows ten katalog to `IngeTrazo/source`; folder wyżej
  zawiera polskie opisy, launcher, patch oraz artefakty `qa`. Git obsługuj tutaj.

## Praca nad poprawkami

- Przed zmianą sprawdź odpowiednie narzędzie, komendę historii i istniejące testy.
  Uwzględniaj Cofnij/Ponów, podgląd/Esc oraz korekty liczbowe po operacji, jeżeli
  zmiana dotyczy tych ścieżek. Przy przyciąganiu sprawdzaj oba rzuty kamery;
  przy geometrii płaszczyznę pionową i scenę zawierającą także geometrię 3D.
- Po zakończeniu aktualizuj opis zmienionego zachowania i wyników weryfikacji.
  Na koniec etapu uaktualnij `HANDOFF.md`: stan, decyzje, ograniczenia i kolejny
  krok. Dawne zgłoszenia traktuj jako listę tematów, nie polecenie ich naprawy.
- Oddzielaj lokalne poprawki/commity od opublikowanych zmian. Publikuj na GitHub
  wtedy, gdy użytkownik o to poprosi; przygotowanie lokalnego punktu zapisu
  samo w sobie nie oznacza publikacji.

## Uruchamianie i weryfikacja

- W tym komputerze Python i zależności są w `.venv/Scripts/python.exe`.
  Uruchamianie: `.venv/Scripts/python.exe main.py --new-window`;
  kontrola startowa: `.venv/Scripts/python.exe main.py --check`.
- Dobieraj testy do zmiany. `HANDOFF.md` zawiera polecenia dla Windows oraz
  opis znanego błędu zamykania procesu Qt. Pomocnik
  `scripts/windows_pytest_exit.py` jest wyłącznie dodatkiem do uruchamiania
  pytest i zachowuje jego rzeczywisty wynik; nie włączaj go do aplikacji.
- Testy Qt offscreen nie potwierdzają obrazu OpenGL. Dotychczasowe natywne
  obrazy są w lokalnym `../qa`. Pełny zestaw projektu ma historyczne błędy;
  nie przedstawiaj zaliczonego zestawu wybranych testów jako pełnego wyniku.
