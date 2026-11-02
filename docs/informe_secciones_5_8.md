# 5. Regla de aceptación congelada y versiones aprobadas

## 5.1 Decisión congelada

La regla de aceptación se definió y congeló el **2026-11-01**, antes de la corrida oficial, y no se modificó después de ver los resultados. Vive en `config/pipeline.yaml` (`aceptacion:`), se copia al `manifest.json` de cada versión y se registra en MLflow.

Esta sección reemplaza el carácter provisional que tenía la regla en el informe de las secciones 1–4. Las corridas del 31 de octubre quedan como evidencia histórica de intentos rechazados; no se usaron para ajustar la regla final.

## 5.2 Regla aplicada

| Criterio | Valor congelado | Efecto |
|---|---|---|
| Error relativo | `MAE <= 20 %` del nivel medio observado en el backtest | Si una serie no cumple, se publica como referencia con Seasonal Naive |
| Observaciones mínimas | 6 observaciones comparables | Menos de 6: no se evalúa por desempeño |
| Serie obligatoria | `Total` | Si `Total` no cumple, la versión se rechaza |
| Controles críticos | C1–C6 en OK (los WARN se documentan) | Un FAIL crítico detiene el pipeline antes de publicar |
| Salidas | Finitas, no negativas y dentro del rango plausible | Si falla, el candidato se rechaza |
| Referencia | Seasonal Naive se calcula y se reporta | **No es una compuerta de aceptación** (laboratorio, 5.5) |

El umbral de 20 % es una tolerancia de planificación, no una promesa de precisión puntual. La referencia se conserva porque ayuda a interpretar el error, pero el laboratorio no exige superarla; cuando ARIMA no la supera, se documenta sin bloquear la publicación.

## 5.3 Resultado del backtest

El backtest usa origen expansivo y un paso hacia adelante, con 12 cortes mensuales de **julio 2025 a junio 2026**. En cada corte el modelo se ajusta solo con información anterior al mes evaluado.

| Serie | MAE (viajeros/mes) | MAE / nivel | MAE / referencia | Estado publicado |
|---|---:|---:|---:|---|
| Total | 40,387 | 14.7 % | 3.36× | aprobado (ARIMA) |
| Vía Aérea | 14,714 | 14.1 % | 1.57× | aprobado (ARIMA) |
| Vía Terrestre | 25,376 | 14.8 % | 2.03× | aprobado (ARIMA) |
| Vía Marítima | 554 | 93.7 % | 8.27× | referencia (Seasonal Naive) |
| América del Centro | 24,862 | 14.6 % | 2.04× | aprobado (ARIMA) |
| América del Norte | 14,254 | 19.6 % | 2.21× | aprobado (ARIMA) |
| Europa | 3,963 | 26.0 % | 3.44× | referencia (Seasonal Naive) |

Cinco series cumplen y se publican con ARIMA. Vía Marítima y Europa no cumplen el 20 %: sus valores se publican como **referencia** con Seasonal Naive y el tablero lo indica. No se presenta como aprobado un modelo que no cumple la regla.

## 5.4 Versiones y reproducibilidad

Se generaron las versiones locales `v2026.11.01-01` a `v2026.11.01-04`. Las versiones `-03` y `-04` incluyen monitoreo y son equivalentes: `scripts/consultar_mlflow.py comparar` reportó **126 estimaciones y 79 métricas comparadas con diferencia máxima `0.000e+00`**. ARIMA no tiene componentes aleatorios; la reproducibilidad se evalúa en el mismo entorno.

El puntero final de la entrega local apunta a **`v2026.11.01-04`**. La corrida de Docker generó además `v2026.11.02-01`, que se conserva como evidencia de la ejecución en contenedor. Sus decisiones son las mismas; Europa cambia de 3,963 a 3,825 de MAE porque la imagen usa otra versión de Python y el optimizador de ARIMA se detiene en un punto distinto cuando no converge. La corrida local es la canónica.

# 6. Tablero integrado con la versión publicada

## 6.1 Contrato de lectura

El tablero no reajusta modelos ni lee candidatos. `app/publicacion.py` lee `published/current.json` y, desde la ruta indicada, carga `manifest.json`, `metricas.csv`, `estimaciones.csv`, `backtest_detalle.csv`, `reporte_validacion.md` y `monitoreo.json` cuando existen. El puntero es el único contrato entre el pipeline y el tablero.

## 6.2 Qué muestra la pestaña ⑤

- Versión aprobada, fecha de actualización, `run_id` y `mlflow_run_id`.
- Hashes de fuente y configuración, destino y unidad.
- Tabla de validación con `MAE`, `MAE / nivel`, `MAE / referencia`, meses evaluados y estado por serie.
- Distinción visual entre **observado** (verde azulado) y **estimación** (naranja si está aprobada; gris discontinuo si es referencia).
- Alertas de monitoreo de la última ejecución, con la aclaración de que no demuestran por sí solas pérdida de precisión.
- Limitaciones: jul–dic 2026 son estimaciones, el backtest es corto, las series de referencia no pasaron la regla y la pandemia impide un contrafactual limpio.

La pestaña ④ también muestra la estimación publicada para julio–diciembre de 2026 y etiqueta si la serie es aprobada o de referencia.

![Figura 2. Pestaña ⑤: versión aprobada, fecha, métricas, estados y limitaciones.](capturas/v9_version_publicada.png)

![Figura 3. Pestaña ④: pronóstico publicado de la versión aprobada.](capturas/v4_pronostico_publicado.png)

## 6.3 Estimaciones no disponibles

Si `current.json` no existe, está corrupto, la versión está incompleta o no está aprobada, el cargador devuelve `None` con un motivo y la interfaz muestra **«Estimaciones no disponibles»**. No se inventan valores ni se reajusta un modelo. La última versión válida que exista en disco no se modifica; el pipeline solo mueve el puntero cuando publica una versión aprobada.

## 6.4 Pruebas

`tests/test_tablero_publicacion.py` cubre: ausencia de versión, versión incompleta o no aprobada, lectura de una versión aprobada con estados por serie, restauración que cambia el puntero y `current.json` corrupto. La suite completa tiene **41 pruebas** con datos sintéticos y no requiere el dato institucional.

# 7. Monitoreo, fallo controlado y recuperación

## 7.1 Tres verificaciones

Cada ejecución escribe `monitoreo.csv`, `monitoreo.json` y `reporte_monitoreo.md` en el candidato, en la versión publicada y como artefactos de MLflow.

| Verificación | Qué comprueba | Alerta cuando |
|---|---|---|
| M1 actualización | La fuente llega al último mes de cobertura y el pronóstico cubre el período configurado | desfase mayor a 0 meses o pronóstico incompleto |
| M2 calidad | Faltantes, duplicados y meses sin información frente a la línea base de la versión anterior | faltantes +0.5 pp, duplicados +0.1 pp o cobertura +0 meses |
| M3 resultados | Negativos, valores no finitos y variación mes a mes o frente a la versión anterior | variación mensual > 35 % o frente a versión > 25 % |

Las alertas **no bloquean** la publicación por sí solas: son una señal para revisión. El error predictivo solo se actualiza con observaciones comparables; no se inventan errores para meses futuros. La línea base de M2 y las estimaciones previas quedan en `monitoreo.json` para la siguiente ejecución.

## 7.2 Resultado de la corrida canónica

M1 y M2 quedaron en **OK**. M3 generó una **ALERTA** real por la variación mes a mes de Europa (94.4 %) y Vía Marítima (36 %). Son series publicadas como referencia, con estacionalidad irregular; la alerta se registra y se muestra en el tablero, pero no cambia la versión publicada. Una variación alta es una señal para revisión, no una prueba de pérdida de precisión.

## 7.3 Prueba controlada de fallo

Se ejecutó el pipeline con una copia de la fuente a la que se le eliminó la columna `País`.

| Evidencia | Resultado |
|---|---|
| Run local | `20261101-195740-3246f1` |
| Estado MLflow | `FAILED` |
| Código de salida | `2` |
| Etapa final | `2_validacion` |
| Causa | `C1 columnas y tipos: Faltan columnas indispensables: ['País']` |
| Métricas de error | No se calcularon |
| `published/current.json` | SHA-256 sin cambios (`d855739c…`) |

El flujo se detuvo antes de preparar o reemplazar resultados. La versión vigente siguió siendo la misma y el tablero no perdió su fuente de datos.

## 7.4 Recuperación y restauración

Al corregir la fuente, la siguiente corrida publicó `v2026.11.01-03` y luego `v2026.11.01-04`; ambas son equivalentes (diferencia máxima `0.000e+00`). También se demostró la restauración de una versión anterior:

```bash
python -m pipeline.run --restaurar v2026.11.01-02
python -m pipeline.run --restaurar v2026.11.01-04
```

El tablero pasó a leer `v2026.11.01-02` y después volvió a `v2026.11.01-04`. Restaurar solo cambia el puntero; las versiones publicadas no se reescriben. El `current.json` restaurado registra `restaurada_en` y `version_anterior`.

# 8. Contenedores, persistencia y copia limpia

## 8.1 Servicios

El `Dockerfile` usa `python:3.12-slim` y una sola imagen para tablero, pipeline y MLflow. `docker-compose.yml` define:

| Servicio | Comando | Puerto host | Volúmenes |
|---|---|---|---|
| `mlflow` | `mlflow server` con SQLite y artefactos | `5001 → 5000` | `./mlflow:/app/mlflow` |
| `tablero` | `streamlit run app/app.py` | `8501 → 8501` | `./data` y `./published` en solo lectura |
| `pipeline` | `python -m pipeline.run` | — | `./data/raw` en solo lectura, `./published` y `./runs` |

El pipeline usa `MLFLOW_TRACKING_URI=http://mlflow:5000` y espera a que MLflow esté `healthy`. El puerto 5000 del host suele estar ocupado en macOS; por eso el tablero de MLflow se publica en 5001, pero dentro de la red el servicio sigue en `mlflow:5000`.

## 8.2 Aislamiento del dato institucional

`.dockerignore` excluye `data/raw/*`, `runs/`, `mlflow/`, `mlruns/` y `.git/`. El `.xlsx` no se copia a la imagen: se monta en solo lectura únicamente en el servicio `pipeline`. La verificación dentro de la imagen mostró que `/app/data/raw/` solo contiene `.gitkeep` y que `find /app -name "*.xlsx"` no devuelve archivos.

## 8.3 Persistencia

Se ejecutó `docker compose down`, que eliminó contenedores y red. Después:

- `published/current.json` conservó el mismo SHA-256 (`c78560c4…`).
- `mlflow/mlflow_docker.db` siguió en disco.
- El run `48daaef8440d…` siguió en la base con estado `FINISHED`.
- Al recrear con `docker compose up -d mlflow tablero`, el run siguió disponible por la API y el tablero respondió HTTP 200.

La corrida de Docker publicó `v2026.11.02-01` con la misma regla congelada y las mismas decisiones de aceptación.

## 8.4 Prueba desde una copia limpia

Se clonó el repositorio en un directorio temporal, se copió solo el `.xlsx` institucional a `data/raw/` y se ejecutó Compose desde el clon. La corrida terminó con código 0 y publicó **`v2026.11.02-02`** (`run_id 20261102-021301-d6d6d5`, MLflow `ed692d72e66a…`). `mlflow/mlflow_docker.db` se creó desde cero y el run quedó `FINISHED`. El clon solo mostró los cambios esperados: `published/current.json` modificado y la versión nueva sin seguimiento. No se usaron `runs/`, `mlflow/` ni archivos locales sin versionar de la copia original.

## 8.5 Nota de alcance

La base local `mlflow/mlflow.db` conserva una ruta de artefactos específica del host. Para no romper las corridas locales, Docker usa `mlflow/mlflow_docker.db` y artefactos en `/app/mlflow/artifacts`; ambas bases viven bajo `mlflow/`, que no se versiona. La imagen no incluye `.git`, por lo que el manifiesto de la corrida Docker registra `commit_git: sin-git`; la trazabilidad se completa con la versión publicada, los hashes de fuente y configuración, las dependencias y el registro en MLflow. La corrida local canónica sí registra el commit de Git.

# 9. Cierre y evidencia de la entrega

| Requisito | Evidencia |
|---|---|
| Regla de aceptación congelada | `config/pipeline.yaml`, `manifest.json` y MLflow; fecha 2026-11-01 |
| Versiones aprobadas | `v2026.11.01-01` a `v2026.11.01-04`; puntero final en `-04` |
| Tablero integrado | Pestaña ⑤ y pronóstico publicado; lectura de `current.json`; pruebas de versión ausente, incompleta y restauración |
| Monitoreo | M1–M3 en `monitoreo.csv/json` y `reporte_monitoreo.md`; alertas no bloqueantes |
| Fallo y recuperación | Run `20261101-195740-3246f1` con código 2; recuperación a `-03`/`-04`; restauración a `-02` y vuelta a `-04` |
| Docker | `Dockerfile`, `docker-compose.yml`, persistencia tras `down`, sin `.xlsx` en la imagen, copia limpia con `v2026.11.02-02` |
| Registro de ejecuciones | `docs/mlflow_ejecuciones.csv` con 3 corridas históricas, `v01`–`v04` y la corrida fallida; bases y artefactos en `mlflow/`, entregados aparte |

El flujo cumple el objetivo del laboratorio: actualizar estimaciones de forma controlada, identificar qué datos, código y configuración produjeron cada resultado y no reemplazar la versión vigente cuando un control o la regla de aceptación falla.
