# Resumen ejecutivo

## Pregunta

¿Puede un proceso automatizado mejorar un bloque RTL secuencial real sin cambiar su interfaz, protocolo, latencia ni comportamiento observable ciclo a ciclo?

## Resultado

Sobre un núcleo SHA-1 corregido y derivado del benchmark abierto de Verilog-to-Routing, cuatro reescrituras locales de RTL consiguieron una **mejora del 5,98% en el PPA compuesto estimado**. El resultado se certificó sobre 64 seeds pareados de VPR que no fueron visibles durante la búsqueda.

- Retardo crítico: **11,43% mejor**, IC95% pareado de 10,87% a 11,98%.
- Energía por bloque: **6,14% mejor**, IC95% pareado de 5,77% a 6,52%.
- Área total: **estadísticamente neutral**; la estimación central mejora un 0,03%, pero el intervalo cruza cero.
- Score PPA compuesto: **5,98% mejor**, IC95% de 5,69% a 6,27%.
- Timing, energía y score mejoran en los 64 seeds pareados.
- La equivalencia formal EQY pasa y se conserva la ejecución de 80 ciclos por bloque.

La potencia activa mediana aumenta un 5,83%. Se muestra expresamente: el circuito consume más potencia instantánea, pero termina antes el mismo trabajo y reduce la energía total por bloque.

## Método

El generador de candidatos no define si su propio resultado es correcto. Un evaluador independiente congela el RTL de referencia, interfaz, testbench, comportamiento temporal, herramientas, arquitectura, actividad, seeds y política de aceptación.

Cada propuesta queda identificada por SHA-256 y debe pasar contrato estructural, regresión temporal y equivalencia formal EQY antes de ejecutar PPA. Cinco seeds pareados sirven únicamente para orientar la búsqueda. Al cerrar la búsqueda se certifican como máximo tres finalistas distintos y formalmente válidos sobre un conjunto fijo y disjunto de 64 seeds.

El líder provisional de cinco seeds fue rechazado durante la certificación porque apareció evidencia estadística de regresión de área. Otro finalista fue declarado campeón. Este rechazo demuestra que el sistema distingue entre una señal provisional y una mejora certificada.

## Interpretación

Las cuatro modificaciones cambian la topología de expresiones booleanas y aritméticas, no el algoritmo SHA-1 ni su microarquitectura. En el seed representativo 20, el grafo temporal baja de 46 a 42 niveles y el diseño pasa de 188 a 187 CLB, aunque el número de nodos `.names` de ABC aumenta ligeramente. La mejora procede de una topología que se empaqueta y enruta mejor, no simplemente de eliminar puertas.

## Alcance

Las cifras son estimaciones comparativas sobre una arquitectura FPGA académica de VTR y un modelo PTM45. No son resultados ASIC, de una FPGA comercial, de silicio fabricado ni de signoff. Un piloto empresarial sustituiría el evaluador académico por las librerías, constraints, workloads, herramientas y criterios de aceptación del cliente.

SHA-1 se utiliza únicamente como benchmark computacional legado, no como recomendación criptográfica.

## Siguiente paso propuesto

Realizar bajo confidencialidad un piloto acotado sobre un bloque computacional no crítico elegido por el cliente: congelar su contrato temporal y flujo PPA, aceptar únicamente parches revisables y formalmente equivalentes, y permitir que el propio equipo del cliente reproduzca cada mejora antes de ampliar el alcance.
