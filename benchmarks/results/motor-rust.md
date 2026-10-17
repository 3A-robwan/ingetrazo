# Motor Rust experimental — mediciones (0.5.9, Bloque R)

Máquina de Marco (Linux, 16 hilos). `scripts/bench_engine.py ~/Descargas/plaza.igz --no-profile`,
una vez con `INGETRAZO_RUST=0` y otra con `=1`. Segundos.

## R1 — línea base (17-10, `c9f547f`)

| Operación | Python | Rust | Nota |
|---|---:|---:|---|
| abrir | 1,90 | 1,83 | objetos Python: no gana sin malla en Rust |
| guardar | 0,91 | 0,86 | |
| exportar STL | 3,35 | 3,21 | |
| exportar OBJ | 4,80 | 4,58 | |
| collect_geometry (láminas) | 3,96 | 3,75 | |
| líneas ocultas, planta | 150,4 | **5,0** | HLR (13-10) |
| líneas ocultas, iso | 140,9 | **6,0** | |
| triangular todo | 1,50 | 1,49 | |
| orientar el grupo más grande | 6,80 | 6,81 | |
| intersecar todo con todo (82 049 cruces) | 257 | 257 | 95 % en `_touching` (cajas, NumPy) |
| aplicar 2 000 cruces | 4,2 | 4,5 | `_cycle_adjacency`, `edits._pick` |

## R2

- **Intersecar — fase de cajas** (`touching_boxes`, rejilla x/y + la misma prueba en f64):
  todo con todo en plaza **266 → 8,7 s**, los 82 049 segmentos idénticos (mismo proceso, mismo orden).
  `tests/test_intersect_native.py` caza 5/5 sabotajes (eps, lista de cajas grandes, i=j, consulta sin eps en x / y).
  Ojo: entre ejecuciones Python da 82 033–82 049 cruces porque la selección es un `set` (su orden cambia): comparar siempre en el mismo proceso.
