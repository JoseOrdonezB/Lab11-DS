# Reporte de controles de calidad — corrida 20261101-195824-43e3ea

- Fuente (SHA-256): `cdaba77918ae889c847ba8459503f9cce2441efac41b3d3aa0f05ac9ab283846`
- Config (SHA-256): `7818d835f7ae2c52133fb8bf9f0b3e8c3119b9be63b47253f598833a5e0f0718`
- Resumen: OK 4, WARN 2, FAIL 0, OMITIDO 0
- Decisión: APROBADO por controles: la ejecución continúa a preparación y modelado.

| Control | Estado | Afectados | Resultado |
|---|---|---|---|
| C1 columnas y tipos | OK | 0 | Las 8 columnas indispensables existen con el tipo esperado. |
| C2 fechas y cobertura | WARN | 37 | meses sin filas (quedan como faltantes, no como cero): Vía Marítima: 27 meses; América del Norte: 5 meses; Europa: 5 meses. |
| C3 unicidad | WARN | 42 | 42 filas (0.026 %) comparten clave (Año, Mes cod, Vía, Frontera, País, Región dos, Tipo de Viajero). Se conservan y se suman como registros parciales aditivos; no se eliminan en silencio. Está por debajo del umbral de advertencia (0.1 %); se avisa igual para que quede registrado. |
| C4 valores faltantes | OK | 0 | Sin ausencias en las columnas utilizadas. |
| C5 valores y denominadores | OK | 0 | Sin negativos ni valores no finitos. Sin denominadores iguales a cero en el backtest. |
| C6 regla metodológica | OK | 0 | Fuente mensual (sin columnas diarias), tipos de viajero válidos, y Total sin 'Viajero' = suma de vías (dif. máx. 5.82e-11). |

## Qué verifica cada control

**C1 Columnas y tipos**
- Verifica: Que existan las columnas indispensables del config y que su tipo sea compatible (entero, numérico, texto).
- Advertencia (WARN): Nunca.
- Detiene (FAIL): Falta una columna indispensable o tiene un tipo incompatible. Si falla, no se evalúan los demás controles.

**C2 Fechas y cobertura**
- Verifica: Que Año y Mes cod formen fechas válidas y que cada mes de la cobertura configurada tenga información.
- Advertencia (WARN): Hay filas fuera de la cobertura, o meses sin filas en alguna serie distinta de Total (quedan como faltantes, nunca como cero).
- Detiene (FAIL): Hay fechas inválidas, o un mes de la cobertura sin información en la serie Total.

**C3 Unicidad**
- Verifica: Que no haya filas con la misma clave (año, mes, vía, frontera, país, región, tipo de viajero).
- Advertencia (WARN): Hay claves repetidas pero su porcentaje no supera duplicados_pct_fallo (se suman como registros parciales, no se borran).
- Detiene (FAIL): El porcentaje de filas con clave repetida supera duplicados_pct_fallo del config.

**C4 Valores faltantes**
- Verifica: Nulos en las columnas utilizadas, distinguiendo ausencias permitidas (columnas_nulos_permitidos) de las que impiden estimar.
- Advertencia (WARN): Hay nulos solo en columnas permitidas (Frontera, País).
- Detiene (FAIL): Hay nulos en cualquier otra columna utilizada.

**C5 Valores y denominadores**
- Verifica: Conteos negativos, valores no finitos (inf o no numéricos) en Viajero y meses con valor observado cero en el backtest (denominador del MAPE).
- Advertencia (WARN): Hay meses observados iguales a cero en el backtest (se excluyen del MAPE).
- Detiene (FAIL): Hay algún conteo negativo o algún valor no finito.

**C6 Regla metodológica**
- Verifica: Que la serie mensual provenga de la fuente mensual (sin columnas diarias), que los tipos de viajero sean los conocidos y que Total sin el tipo excluido sea la suma de las vías.
- Advertencia (WARN): Nunca.
- Detiene (FAIL): La fuente trae columnas diarias, hay tipos de viajero desconocidos o Total no coincide con la suma de las vías.

Los controles son críticos: un FAIL detiene el pipeline antes de preparar datos o tocar `published/`.
Los meses sin cobertura nunca se convierten en cero.
