# Resumen ejecutivo

## Resultado evaluado

Cuatro reescrituras locales y ciclo-equivalentes de RTL reducen un **5,98% el score PPA compuesto estimado** sobre un núcleo SHA-1 corregido y derivado del benchmark abierto de Verilog-to-Routing.

- Retardo crítico: **11,43% mejor**, con IC95% pareado de 10,87% a 11,98%.
- Energía por bloque: **6,14% mejor**, con IC95% pareado de 5,77% a 6,52%.
- Área total: **estadísticamente neutral**; la estimación central mejora un 0,03%, pero el intervalo cruza cero.
- Score PPA compuesto: **5,98% mejor**, con IC95% de 5,69% a 6,27%.
- Timing, energía y score mejoran en las 64 implementaciones pareadas.
- La equivalencia formal EQY pasa y se conserva la ejecución de 80 ciclos por bloque.

La potencia activa mediana aumenta un 5,83%. El informe mantiene visible este intercambio: el circuito utiliza más potencia instantánea, pero completa antes el mismo trabajo y reduce la energía modelada por bloque.

## Qué cambia

El RTL aceptado modifica cuatro asignaciones continuas:

1. La función `choose` de SHA-1 se expresa como producto de sumas.
2. La función `majority` se factoriza con otra topología booleana.
3. El XOR de cuatro entradas del message schedule se balancea explícitamente.
4. El acumulador de ronda de 32 bits se reasocia en sumas parciales.

No cambia ningún registro, puerto, transición de estado, comando, salida, latencia ni throughput. El patch exacto contiene cuatro asignaciones eliminadas y cuatro añadidas.

## Verificación y medición

El evaluador congela el RTL de referencia, la interfaz, vectores, comportamiento temporal, herramientas, arquitectura FPGA, actividad, 64 seeds de implementación y política de aceptación.

El `sha.v` aceptado queda identificado por SHA-256 y supera comprobaciones estructurales, regresión temporal, validación NIST SHA-1 y equivalencia secuencial EQY antes de medir PPA. Baseline y RTL aceptado utilizan después los mismos 64 seeds de VPR, lo que permite comparar de forma pareada área, retardo crítico y energía por bloque.

En el seed representativo 20:

| Propiedad post-síntesis / route | Baseline | RTL aceptado |
|---|---:|---:|
| Niveles del timing graph | 46 | 42 |
| Camino crítico | 14,9802 ns | 13,4066 ns |
| Bloques CLB | 188 | 187 |
| Nodos `.names` de ABC | 1.643 | 1.652 |

La mejora no procede de una reducción universal del número de nodos. La nueva topología se empaqueta y enruta mejor sobre el objetivo congelado.

## Frontera de la afirmación

Las cifras proceden de una arquitectura FPGA académica de VTR y de su modelo de potencia PTM45. No son PPA ASIC, resultados de una FPGA comercial, datos de silicio ni signoff, y no pueden trasladarse numéricamente a otro diseño o proceso. SHA-1 se utiliza como benchmark computacional legado, no como recomendación criptográfica.

## Aplicación a un piloto de cliente

Un piloto confidencial sustituiría el proxy académico por el RTL, estrategia formal, librerías, constraints, workloads, herramientas y política de aceptación del cliente. La entrega conservaría la misma forma: un patch pequeño y revisable, prueba formal, mediciones reproducibles, trade-offs explícitos y una afirmación técnica delimitada.
