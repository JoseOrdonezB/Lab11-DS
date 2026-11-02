# Reporte de validación temporal — corrida 20261101-195824-43e3ea

- Regla congelada: **2026-11-01**
- Criterio de desempeño: MAE ≤ 20% del nivel medio mensual observado en el backtest.
- Observaciones mínimas: 6 por serie.
- Series obligatorias: Total.
- Referencia: Seasonal Naive (se calcula y se reporta; **no es un requisito** superarla).
- Período de backtest: 2025-07 a 2026-06 (origen expansivo, un paso hacia adelante).
- Decisión de la corrida: **APROBADO**.
- Fuente (SHA-256): `cdaba77918ae889c847ba8459503f9cce2441efac41b3d3aa0f05ac9ab283846`
- Config (SHA-256): `7818d835f7ae2c52133fb8bf9f0b3e8c3119b9be63b47253f598833a5e0f0718`

## Resultados por serie

| Serie | n | Nivel medio | MAE | MAE / nivel | RMSE | MAPE | Excl. MAPE | Ref. MAE | MAE / ref. | ¿Supera ref.? | Estado | Motivo |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| Total | 12 | 275,328 | 40,387 | 14.7% | 45,026 | 14.6% | 0 | 12,027 | 3.36 | no | aprobado | cumple; no supera la referencia (3.36x), se reporta sin bloquear |
| Vía Aérea | 12 | 104,259 | 14,714 | 14.1% | 16,870 | 14.3% | 0 | 9,348 | 1.57 | no | aprobado | cumple; no supera la referencia (1.57x), se reporta sin bloquear |
| Vía Terrestre | 12 | 171,069 | 25,376 | 14.8% | 32,750 | 14.9% | 0 | 12,530 | 2.03 | no | aprobado | cumple; no supera la referencia (2.03x), se reporta sin bloquear |
| Vía Marítima | 12 | 592 | 554 | 93.7% | 623 | 101.0% | 0 | 67 | 8.27 | no | referencia | MAE 554 > 20% del nivel medio (592) |
| América del Centro | 12 | 170,028 | 24,862 | 14.6% | 29,419 | 14.7% | 0 | 12,187 | 2.04 | no | aprobado | cumple; no supera la referencia (2.04x), se reporta sin bloquear |
| América del Norte | 12 | 72,774 | 14,254 | 19.6% | 16,155 | 19.5% | 0 | 6,464 | 2.21 | no | aprobado | cumple; no supera la referencia (2.21x), se reporta sin bloquear |
| Europa | 12 | 15,242 | 3,963 | 26.0% | 4,302 | 28.4% | 0 | 1,151 | 3.44 | no | referencia | MAE 3963 > 20% del nivel medio (15242) |

El nivel medio es el promedio mensual observado de la serie en los 12 meses del backtest. El MAPE excluye observaciones iguales a cero; la columna «Excl. MAPE» indica cuántas se excluyeron. La referencia se evalúa sobre los mismos meses que el modelo.

## Enero y febrero de 2026

El backtest de origen expansivo estima cada mes usando solo información anterior al mes evaluado. Para enero de 2026 el ajuste termina en diciembre de 2025; para febrero, en enero de 2026. No se usa el valor observado del mes que se está estimando.

| Serie | Mes | Observado | ARIMA | Referencia | Error ARIMA | APE ARIMA | Error ref. | APE ref. |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Total | 2026-01 | 300,664 | 344,119 | 289,544 | 43,454 | 14.45% | -11,120 | 3.70% |
| Total | 2026-02 | 236,844 | 281,083 | 254,429 | 44,239 | 18.68% | 17,585 | 7.42% |
| Vía Aérea | 2026-01 | 113,435 | 119,663 | 101,124 | 6,228 | 5.49% | -12,311 | 10.85% |
| Vía Aérea | 2026-02 | 106,821 | 105,027 | 92,703 | -1,794 | 1.68% | -14,118 | 13.22% |
| Vía Terrestre | 2026-01 | 187,229 | 220,082 | 188,420 | 32,853 | 17.55% | 1,191 | 0.64% |
| Vía Terrestre | 2026-02 | 130,023 | 195,777 | 161,726 | 65,754 | 50.57% | 31,703 | 24.38% |
| Vía Marítima | 2026-01 | 644 | 859 | 603 | 215 | 33.34% | -41 | 6.37% |
| Vía Marítima | 2026-02 | 758 | 1,022 | 612 | 264 | 34.77% | -146 | 19.26% |
| América del Centro | 2026-01 | 188,957 | 216,986 | 187,170 | 28,029 | 14.83% | -1,787 | 0.95% |
| América del Centro | 2026-02 | 129,776 | 181,978 | 155,565 | 52,202 | 40.22% | 25,789 | 19.87% |
| América del Norte | 2026-01 | 73,594 | 82,816 | 68,398 | 9,223 | 12.53% | -5,196 | 7.06% |
| América del Norte | 2026-02 | 70,562 | 61,715 | 63,957 | -8,847 | 12.54% | -6,605 | 9.36% |
| Europa | 2026-01 | 19,158 | 13,881 | 17,867 | -5,277 | 27.54% | -1,291 | 6.74% |
| Europa | 2026-02 | 20,118 | 23,965 | 19,359 | 3,847 | 19.12% | -758 | 3.77% |

## Decisión y justificación

La versión se **aprueba** porque la serie obligatoria (Total) cumple la regla y las salidas son finitas, no negativas y están dentro del rango plausible.

El umbral del 20 % se fija sobre la escala de la variable: el nivel mensual del Total en el backtest es del orden de cientos de miles de viajeros, por lo que un error promedio de una quinta parte del nivel es una tolerancia explícita para planificación, no una promesa de precisión puntual. La comparación con Seasonal Naive se reporta para transparencia; el laboratorio no exige superar la referencia (5.5). Cuando el modelo no la supera, se explica y se aplica la regla sin cambiarla para aprobar.

Las series que no cumplen se publican como **referencia** (Seasonal Naive), no como estimaciones ARIMA aprobadas; el tablero debe distinguir ese estado.

## Limitaciones

- El backtest tiene 12 cortes; es una muestra corta para evaluar error predictivo.
- El código y la regla se especificaron después de observar los datos; el backtest es retrospectivo, no un experimento pre-registrado.
- Enero y febrero de 2026 se estiman sin fuga de información, pero la pandemia, la recuperación y el cambio metodológico 2022–2023 impiden un contrafactual limpio.
- 2026 solo tiene observaciones hasta junio; jul–dic 2026 no se puede validar todavía.
- En Vía Marítima y Europa ARIMA no converge en varios cortes; sus resultados se reportan y, si no cumplen la regla, se publican como referencia.
- Las estimaciones suponen continuidad del patrón histórico; no anticipan pandemias, shocks ni revisiones de la fuente.
