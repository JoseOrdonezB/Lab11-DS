# Observatorio de Turismo Sostenible · Guatemala — Laboratorios 10 y 11 (CC3066)

Tablero interactivo en **Streamlit + Plotly** sobre las llegadas internacionales de viajeros (INGUAT/Migración, 2009–jun 2026).
Reutiliza los modelos del Laboratorio 1 (ARIMA, Seasonal Naive, Prophet); **no se entrenan modelos nuevos**.

## Ejecutar el tablero
```bash
pip install -r requirements.txt
streamlit run app/app.py
```

## Estructura
- `app/app.py` — tablero: V1 serie con nivel de detalle, V2↔V3 región→país enlazadas, V4 pronóstico vs observado y **pestaña ⑤ de versión publicada**.
- `app/publicacion.py` — lee `published/current.json` y los archivos de la versión aprobada. El tablero no reajusta modelos.
- `data/` — archivos ya exportados que lee el tablero (`base_viajeros.csv.gz`, `series_mensuales.csv`, `predicciones_lab1.csv`, `metricas_lab1.csv`).
- `scripts/exportar_modelos_lab1.py` — regenera `data/` desde `Base_Migracion_2009-2026jun.xlsx` con los mismos modelos y parámetros del Lab 1.
- `pipeline/` — orquestador, controles, modelos, monitoreo, publicación y reportes.
- `published/` — versiones inmutables y puntero `current.json` que consulta el tablero.
- `Dockerfile`, `docker-compose.yml`, `.dockerignore` — tablero, pipeline y MLflow en contenedores.
- `.streamlit/config.toml` — tema de color.

## Convención de color (igual en toda la app)
Verde azulado = dato observado · Naranja = estimación de un modelo · Gris = referencia / pandemia · Azul marino = texto y selección.

---

# Laboratorio 11: pipeline MLOps

El pipeline lee la base de Migración, valida los datos, estima y evalúa con los modelos del Lab 1 y publica una versión aprobada
que el tablero consulta. El tablero no reajusta nada: solo lee `published/current.json`.

## Cómo correrlo

```bash
pip install -r requirements-pipeline.txt
cp /ruta/a/Base_Migracion_2009-2026jun.xlsx data/raw/      # dato institucional, no va a Git
python -m pipeline.run                                      # usa config/pipeline.yaml
```

Opciones: `--config OTRO.yaml`, `--fuente RUTA` (acepta .xlsx, .csv y .csv.gz) y `--restaurar VERSION`.
Tarda cerca de 40 segundos (la mayor parte es el backtest).

Códigos de salida: `0` publicado · `1` error inesperado · `2` detenido por un control crítico · `3` candidato rechazado por la regla de aceptación.
En los códigos 1, 2 y 3 **no se toca** `published/`: el tablero sigue con la última versión aprobada.

## Etapas (coinciden con el diagrama)

| Etapa | Qué hace | Dónde |
|---|---|---|
| 1 | Lee la fuente y calcula SHA-256 de fuente y config | `pipeline/run.py` |
| 2 | Seis controles de calidad (FAIL crítico detiene todo) | `pipeline/controles.py` |
| 3 | Series mensuales; un mes sin filas queda en NaN, no en cero | `pipeline/preparar.py` |
| 4-5 | ARIMA (orden del Lab 1) y backtest de origen expansivo, un paso adelante, jul-2025 a jun-2026; referencia: Seasonal Naive | `pipeline/modelos.py` |
| 6 | Regla de aceptación por serie (`cumple_regla`) | `pipeline/modelos.py` |
| 7 | Estimaciones: backtest (`evaluacion`) y jul-dic 2026 (`pronostico`) | `pipeline/modelos.py` |
| 8 | Candidato en `runs/<run_id>/` | `pipeline/run.py` |
| 9 | Autorización: salidas finitas, no negativas, rango plausible y series obligatorias cumplen | `pipeline/run.py` |
| 10-11 | Versión inmutable en `published/versions/vAAAA.MM.DD-NN/` y puntero atómico `published/current.json` | `pipeline/publicar.py` |
| 12 | Monitoreo M1–M3 y reporte de la ejecución | `pipeline/monitoreo.py` |

## Regla de aceptación congelada (sección 5)

La regla se congeló el **2026-11-01**, antes de la corrida oficial, y no se modificó después de ver los resultados:

- `MAE <= 20 %` del nivel medio observado en el backtest de 12 cortes.
- Mínimo **6 observaciones** comparables.
- La serie **Total** es obligatoria: si no cumple, la versión se rechaza.
- **Seasonal Naive se reporta como referencia, pero no es una compuerta de aceptación.** El laboratorio no exige superarla (5.5);
  cuando ARIMA no la supera, se documenta sin bloquear.
- Si una serie no cumple, se publica como `estado="referencia"` con Seasonal Naive. Las series que cumplen se publican como
  `estado="aprobado"` con ARIMA.

La regla vive en `config/pipeline.yaml` (`aceptacion:`), se registra en el `manifest.json` de cada versión y en MLflow.

### Resultado de la corrida canónica local (`v2026.11.01-04`)

| Serie | MAE (viajeros/mes) | MAE / nivel | MAE / referencia | Estado |
|---|---:|---:|---:|---|
| Total | 40,387 | 14.7 % | 3.36× | aprobado (ARIMA) |
| Vía Aérea | 14,714 | 14.1 % | 1.57× | aprobado (ARIMA) |
| Vía Terrestre | 25,376 | 14.8 % | 2.03× | aprobado (ARIMA) |
| Vía Marítima | 554 | 93.7 % | 8.27× | referencia (Seasonal Naive) |
| América del Centro | 24,862 | 14.6 % | 2.04× | aprobado (ARIMA) |
| América del Norte | 14,254 | 19.6 % | 2.21× | aprobado (ARIMA) |
| Europa | 3,963 | 26.0 % | 3.44× | referencia (Seasonal Naive) |

Cinco series quedan aprobadas con ARIMA; Vía Marítima y Europa se publican como referencia. La corrida de Docker
(`v2026.11.02-01`) reproduce las mismas decisiones; Europa cambia ligeramente (MAE 3,825; 25.1 %) porque la imagen usa
otra versión de Python y el optimizador de ARIMA se detiene en un punto distinto. La corrida local es la canónica.

## Tablero: versión publicada (sección 6)

La pestaña **⑤ ¿Qué versión estoy viendo?** y la sección de pronóstico de la pestaña ④ leen exclusivamente
`published/current.json` y los archivos de la versión apuntada:

- Versión, fecha de actualización, `run_id`, `mlflow_run_id`, hashes de fuente y configuración.
- Métricas del backtest, con `MAE`, `MAE / nivel`, `MAE / referencia` y estado por serie.
- Distinción explícita entre **observado** (verde azulado) y **estimación** (naranja si está aprobada; gris discontinuo si es referencia).
- Limitaciones: jul–dic 2026 son estimaciones, el backtest es corto, las series de referencia no pasaron la regla y la pandemia
  impide un contrafactual limpio.
- Si no existe versión aprobada, el puntero está corrupto o la versión está incompleta, muestra **«Estimaciones no disponibles»**
  y el detalle técnico; no inventa valores ni reajusta modelos.
- Si una serie publicada es de referencia, el tablero lo indica y no la presenta como ARIMA aprobado.

Para probar la restauración:

```bash
python -m pipeline.run --restaurar v2026.11.01-02   # el tablero pasa a leer v02
python -m pipeline.run --restaurar v2026.11.01-04   # se vuelve a la versión canónica
```

Restaurar solo cambia el puntero; las versiones publicadas no se reescriben.

## Monitoreo y recuperación (sección 7)

Cada ejecución escribe `monitoreo.csv`, `monitoreo.json` y `reporte_monitoreo.md` en el candidato, en la versión publicada
y como artefactos de MLflow. Hay tres verificaciones:

| Verificación | Qué comprueba | Alerta cuando |
|---|---|---|
| M1 actualización | La fuente llega al último mes de cobertura y el pronóstico cubre el período configurado | falta un mes o el pronóstico no llega a dic-2026 |
| M2 calidad | Faltantes, duplicados y meses sin información frente a la línea base de la versión anterior | el aumento supera los umbrales de `monitoreo.calidad` |
| M3 resultados | Negativos, valores no finitos y variación mes a mes o frente a la versión anterior | supera `variacion_mensual_max` (35 %) o `variacion_version_max` (25 %) |

Las alertas **no bloquean** la publicación por sí solas: son una señal para revisión. Una variación alta no demuestra pérdida
de precisión; el error predictivo solo se actualiza cuando hay observaciones comparables. En la corrida canónica M1 y M2
quedan en OK y M3 genera una alerta real por la variación mes a mes de Europa (94 %) y Vía Marítima (36 %), ambas series de
referencia con estacionalidad irregular. La alerta queda registrada y visible en el tablero, sin ocultar la versión.

### Prueba controlada de fallo y recuperación

Se ejecutó el pipeline con una copia de la fuente sin la columna `País`:

- Run `20261101-195740-3246f1`, MLflow `FAILED`, código de salida `2`.
- El flujo se detuvo en `2_validacion` por `C1 columnas y tipos: Faltan columnas indispensables: ['País']`.
- No se calcularon métricas ni se reemplazó la versión vigente: el SHA-256 de `published/current.json` no cambió.
- Al corregir la fuente, la siguiente corrida publicó `v2026.11.01-03` y luego `v2026.11.01-04`.
- `v2026.11.01-03` y `v2026.11.01-04` son equivalentes: diferencia máxima `0.000e+00` en 126 estimaciones y 79 métricas
  (`scripts/consultar_mlflow.py comparar`).

## Docker y Compose (sección 8)

```bash
docker compose build
docker compose up -d mlflow tablero
docker compose run --rm pipeline        # corrida completa; publica una versión nueva
```

- Tablero: `http://localhost:8501`.
- MLflow: `http://localhost:5001` (el puerto 5000 del host suele estar ocupado en macOS; dentro de la red el servicio sigue en `mlflow:5000`).
- El pipeline usa `MLFLOW_TRACKING_URI=http://mlflow:5000` y espera a que MLflow esté `healthy`.
- `published/`, `runs/` y `mlflow/` se montan desde el host: **sobreviven a `docker compose down` y a la recreación de contenedores**.
- `data/raw/` se monta en solo lectura y está excluido por `.dockerignore`: **el dato institucional no entra a la imagen**.
- La imagen no copia `runs/`, `mlflow/` ni `.git`. La corrida de Docker queda identificada por la versión publicada, los hashes
  de fuente/configuración y el registro en `mlflow/mlflow_docker.db`.

Se usa una base separada `mlflow/mlflow_docker.db` porque la base local conserva una ruta de artefactos específica del host;
mezclar ambas en el mismo servidor rompería los artefactos de las corridas locales. Las dos bases viven en `mlflow/`, que no va a Git.

### Evidencia de persistencia

1. `docker compose down` eliminó los contenedores y la red.
2. `published/current.json` conservó el mismo SHA-256 y `mlflow/mlflow_docker.db` siguió en disco.
3. `docker compose up -d mlflow tablero` recreó los contenedores; el run `48daaef8440d…` siguió disponible en MLflow y el
   tablero respondió HTTP 200 con la versión publicada.

### Prueba desde una copia limpia

La prueba se hizo desde un `git clone` nuevo: se copió el `.xlsx` institucional a `data/raw/` (no está en Git), se levantó
Compose y se ejecutó `docker compose run --rm pipeline`. La corrida publicó `v2026.11.02-02` (run `20261102-021301-d6d6d5`),
creó `mlflow/mlflow_docker.db` desde cero y no usó `runs/`, `mlflow/` ni archivos locales sin versionar de la copia original.
La imagen no contiene el `.xlsx`: `/app/data/raw/` solo tiene `.gitkeep`.

## Controles de calidad

| Control | Qué verifica | WARN | FAIL (detiene) |
|---|---|---|---|
| C1 columnas y tipos | Las 8 columnas existen con el tipo esperado | nunca | falta una columna o el tipo no sirve |
| C2 fechas y cobertura | Año y mes válidos; todos los meses de la cobertura configurada | segmentos con meses sin filas (quedan como faltantes) | fecha inválida o mes sin información en la serie Total |
| C3 unicidad | Claves repetidas (año, mes, vía, frontera, país, región, tipo) | hay repetidas, pero pocas (se suman, no se borran) | más de 1 % de filas repetidas |
| C4 valores faltantes | Nulos por columna | nulos en Frontera o País (permitidos) | nulos en cualquier otra columna |
| C5 valores y denominadores | Negativos, no finitos y ceros en el backtest | ceros observados en el backtest (se excluyen del MAPE) | negativos o no finitos |
| C6 regla metodológica | Fuente mensual (sin columnas diarias), tipos de viajero conocidos y Total sin «Viajero» = suma de las tres vías | nunca | cualquiera de las tres falla |

Cada ejecución escribe `controles.csv` y `reporte_controles.md`; el reporte explica qué verifica cada control, cuándo advierte y
cuándo detiene.

## Qué se guarda por ejecución

`runs/<run_id>/`: `controles.csv`, `reporte_controles.md`, `metricas.csv`, `estimaciones.csv`, `backtest_detalle.csv`,
`parametros_modelo.json`, `monitoreo.csv`, `monitoreo.json`, `reporte_monitoreo.md`, `manifest.json`, `run.log` y
`run_summary.json`.
Una versión aprobada es una copia inmutable de esos archivos en `published/versions/`; `published/current.json` es el único
puntero que lee el tablero.

## Registro en MLflow

Cada ejecución de `python -m pipeline.run` es un run del experimento `observatorio-turismo-guatemala`.
Por defecto se guarda en `mlflow/` (base `mlflow/mlflow.db` y artefactos en `mlflow/artifacts/`); la variable `MLFLOW_TRACKING_URI`
cambia el destino. En Docker se usa `mlflow/mlflow_docker.db`. `mlflow/` no va a Git: los registros se entregan aparte.

| Qué pide el lab (4.1) | Dónde queda en el run |
|---|---|
| Identificador y fecha | nombre del run = `run_id` local; tags `inicio` y `fin`; `mlflow_run_id` también va en `estimaciones.csv`, `metricas.csv` y `manifest.json` |
| Versión del código | tags `commit_git` y `mlflow.source.git.commit` |
| Fuentes y su huella | params `fuente_archivo`, `fuente_sha256`, `fuente_filas`, `config_sha256` |
| Períodos de ajuste y evaluación | params `periodo_cobertura`, `periodo_ajuste_base`, `periodo_backtest`, `periodo_pronostico` |
| Parámetros del procedimiento | params `arima_<serie>`, `log_<serie>`, `referencia`, umbrales `aceptacion_*`, `semilla`, versiones `dep_*` |
| Métricas de evaluación | métricas `<serie>_MAE`, `_RMSE`, `_MAPE_pct`, `_n_obs`, `_ref_MAE`, `_ref_RMSE`, `_cumple_regla` |
| Resultado de los controles | tags `control_C1` a `control_C6` y `controles_resultado`; métricas `controles_ok/warn/fail`; artefactos `controles/` |
| Resultado del monitoreo | métricas `monitoreo_alertas`, `monitoreo_verificaciones`; tags `monitoreo_resultado`; artefactos `monitoreo/` |
| Estimaciones y configuración | artefactos `candidato/` y `configuracion/` |
| Modelo o parámetros para reproducirlo | artefacto `modelo/parametros_modelo.json` |

Estado del run: `FINISHED` si llegó a la decisión (publicado o rechazado) y `FAILED` si se detuvo (control crítico o error),
con la causa en el tag `causa`. Una ejecución detenida antes de la evaluación **no** tiene métricas de error.

```bash
mlflow ui --backend-store-uri sqlite:///mlflow/mlflow.db --port 5000      # abrir http://localhost:5000
python scripts/consultar_mlflow.py listar --salida docs/mlflow_ejecuciones.csv   # tabla de ejecuciones y causas de fallo
python scripts/consultar_mlflow.py comparar                                      # dos últimas ejecuciones evaluadas (4.2)
```

`docs/mlflow_ejecuciones.csv` resume las 3 corridas históricas, las versiones locales `v01`–`v04` y la corrida fallida.
`comparar` revisa que dos ejecuciones tengan la misma fuente y configuración (hashes) y compara estimaciones y métricas con
`reproducibilidad.tolerancia_abs` (1e-6 viajeros/mes).

## Pruebas

```bash
python -m pytest tests -q
```

41 pruebas con datos sintéticos: controles, detención del pipeline, regla de aceptación, monitoreo, lectura del tablero,
restauración y publicación. No requieren el dato institucional.

## Entrega final: evidencia

- Regla de aceptación congelada el 2026-11-01 (`config/pipeline.yaml`, `manifest.json`, MLflow).
- Versiones locales aprobadas `v2026.11.01-01` a `v2026.11.01-04`; puntero final en `v2026.11.01-04`.
- Versión de Docker `v2026.11.02-01` conservada como evidencia de la corrida en contenedor.
- Corrida fallida real `20261101-195740-3246f1` y recuperación documentada.
- Tablero leyendo `published/current.json`, con versión, fecha, métricas, estados y limitaciones.
- Monitoreo M1–M3 con reporte, artefactos y alertas no bloqueantes.
- Docker/Compose con persistencia, sin dato institucional en la imagen y puertos 8501/5001.
- Capturas del tablero en `capturas/v9_version_publicada.png` y `capturas/v4_pronostico_publicado.png`
  (figuras 2 y 3 del informe).
- Informe técnico en `Lab11.pdf` (secciones 5–8 anexadas al informe de las secciones 1–4).
