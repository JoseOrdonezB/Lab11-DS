# Observatorio de Turismo Sostenible · Guatemala — Laboratorios 10 y 11 (CC3066)

Tablero interactivo en **Streamlit + Plotly** sobre las llegadas internacionales de viajeros (INGUAT/Migración, 2009–jun 2026).
Reutiliza los modelos del Laboratorio 1 (ARIMA, Seasonal Naive, Prophet); **no se entrenan modelos nuevos**.

## Ejecutar
```bash
pip install -r requirements.txt
streamlit run app/app.py
```

## Estructura
- `app/app.py` — tablero. Las vistas V1, V2↔V3, V5, V6, V7 y V8 son descriptivas (todo el historial observado del Lab 1).
  La pestaña ④ incluye además el pronóstico oficial publicado por el pipeline del Laboratorio 11, leyendo únicamente
  `published/current.json` y la versión aprobada que apunta (ejercicio 6).
- `data/` — archivos ya exportados que lee el tablero (`base_viajeros.csv.gz`, `series_mensuales.csv`, `predicciones_lab1.csv`, `metricas_lab1.csv`).
- `scripts/exportar_modelos_lab1.py` — regenera `data/` desde `Base_Migracion_2009-2026jun.xlsx` con los mismos modelos y parámetros del Lab 1.

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
| 7.2 | Monitoreo: actualización, calidad y variación de resultados vs. la versión vigente | `pipeline/monitoreo.py` |
| 8 | Candidato en `runs/<run_id>/` | `pipeline/run.py` |
| 9 | Autorización: salidas finitas, no negativas, rango plausible y series obligatorias cumplen | `pipeline/run.py` |
| 10-11 | Versión inmutable en `published/versions/vAAAA.MM.DD-NN/` y puntero atómico `published/current.json` | `pipeline/publicar.py` |

## Controles de calidad

| Control | Qué verifica | WARN | FAIL (detiene) |
|---|---|---|---|
| C1 columnas y tipos | Las 8 columnas existen con el tipo esperado | nunca | falta una columna o el tipo no sirve |
| C2 fechas y cobertura | Año y mes válidos; todos los meses de la cobertura configurada | segmentos con meses sin filas (quedan como faltantes) | fecha inválida o mes sin información en la serie Total |
| C3 unicidad | Claves repetidas (año, mes, vía, frontera, país, región, tipo) | hay repetidas, pero pocas (se suman, no se borran) | más de 1 % de filas repetidas |
| C4 valores faltantes | Nulos por columna | nulos en Frontera o País (permitidos) | nulos en cualquier otra columna |
| C5 valores y denominadores | Negativos, no finitos y ceros en el backtest | ceros observados en el backtest (se excluyen del MAPE) | negativos o no finitos |
| C6 regla metodológica | Fuente mensual (sin columnas diarias), tipos de viajero conocidos y Total sin «Viajero» = suma de las tres vías | nunca | cualquiera de las tres falla |

Cada ejecución escribe `controles.csv` (control, severidad, estado, n_afectados, detalle, run_id, timestamp) y `reporte_controles.md`
(qué verifica cada control, cuándo advierte, cuándo detiene y el resultado de esa corrida; lo genera `pipeline/reporte.py`).

Pruebas de los controles y de la detención del pipeline (datos sintéticos, no requieren el dato institucional):

```bash
python -m pytest tests -q
```

## Monitoreo y alertas (ejercicio 7)

Cada ejecución corre tres verificaciones de monitoreo (`pipeline/monitoreo.py`), independientes de los controles de calidad
y de la regla de aceptación, y escribe `monitoreo.csv` en `runs/<run_id>/` (y en la versión publicada, si se aprueba):

| Verificación | Qué revisa |
|---|---|
| Actualización | Si la fuente y la serie Total llegan hasta el último mes de la cobertura configurada |
| Calidad | Si los faltantes, duplicados o huecos de cobertura aumentaron de forma relevante respecto a la versión vigente |
| Resultados | Estimaciones negativas o no finitas, y variaciones de pronóstico superiores a `umbrales.variacion_pct_alerta` (30 % por defecto) frente a la versión vigente |

Las alertas quedan como `ALERTA` en `monitoreo.csv`, se agregan a las advertencias del run (`run_summary.json`) y se registran en
MLflow (tags `monitor_*` y la métrica `monitoreo_alertas`). Una variación alta genera una alerta para revisión manual; por sí sola
no significa que el modelo perdió precisión (eso solo se confirma con observaciones comparables, ejercicio 5).

## Qué se guarda por ejecución

`runs/<run_id>/`: `controles.csv`, `reporte_controles.md`, `metricas.csv`, `estimaciones.csv`, `backtest_detalle.csv`, `monitoreo.csv`,
`parametros_modelo.json` (coeficientes ARIMA ajustados), `manifest.json` (commit, hashes, dependencias, períodos, run de MLflow),
`run.log` y `run_summary.json` (inicio, fin, etapas completadas, advertencias y resultado de la publicación).
Una versión aprobada es una copia inmutable de esos archivos en `published/versions/`.

## Restaurar una versión anterior

```bash
python -m pipeline.run --restaurar v2026.10.29-01
```

`current.json` vuelve a apuntar a esa versión (no se modifica el contenido de la versión restaurada); el tablero la consulta
de inmediato porque siempre lee el puntero vigente.

## Registro en MLflow

Cada ejecución de `python -m pipeline.run` es un run del experimento `observatorio-turismo-guatemala`.
Por defecto se guarda en `mlflow/` (base `mlflow/mlflow.db` y artefactos en `mlflow/artifacts/`); la variable `MLFLOW_TRACKING_URI` cambia el destino.
`mlflow/` no va a Git: los registros se entregan aparte.

| Qué pide el lab (4.1) | Dónde queda en el run |
|---|---|
| Identificador y fecha | nombre del run = `run_id` local; tags `inicio` y `fin`; `mlflow_run_id` también va en `estimaciones.csv`, `metricas.csv` y `manifest.json` |
| Versión del código | tags `commit_git` y `mlflow.source.git.commit` |
| Fuentes y su huella | params `fuente_archivo`, `fuente_sha256`, `fuente_filas`, `config_sha256` |
| Períodos de ajuste y evaluación | params `periodo_cobertura`, `periodo_ajuste_base`, `periodo_backtest`, `periodo_pronostico`... |
| Parámetros del procedimiento | params `arima_<serie>`, `log_<serie>`, `referencia`, umbrales `aceptacion_*`, `semilla`, versiones `dep_*` |
| Métricas de evaluación | métricas `<serie>_MAE`, `_RMSE`, `_MAPE_pct`, `_n_obs`, `_ref_MAE`, `_ref_RMSE`, `_cumple_regla` |
| Resultado de los controles | tags `control_C1` a `control_C6` y `controles_resultado`; métricas `controles_ok/warn/fail`; artefactos `controles/` |
| Estimaciones y configuración | artefactos `candidato/` y `configuracion/` |
| Modelo o parámetros para reproducirlo | artefacto `modelo/parametros_modelo.json` (orden, transformación log y coeficientes por serie) |

Estado del run: `FINISHED` si llegó a la decisión (publicado o rechazado) y `FAILED` si se detuvo (control crítico o error),
con la causa en el tag `causa`. Una ejecución detenida antes de la evaluación **no** tiene métricas de error.

```bash
mlflow ui --backend-store-uri sqlite:///mlflow/mlflow.db --port 5000      # abrir http://localhost:5000
python scripts/consultar_mlflow.py listar --salida docs/mlflow_ejecuciones.csv   # tabla de ejecuciones y causas de fallo
python scripts/consultar_mlflow.py comparar                                      # dos últimas ejecuciones evaluadas (4.2)
```

`comparar` revisa que tengan la misma fuente y configuración (hashes) y compara estimaciones y métricas con
`reproducibilidad.tolerancia_abs` (1e-6 viajeros/mes). En la misma máquina dos ejecuciones dan diferencia 0: ARIMA no tiene
componentes aleatorios. Entre computadoras con otras versiones de las librerías sí puede cambiar, sobre todo en Europa y Marítima,
donde ARIMA no converge y el optimizador se detiene en puntos distintos; por eso la comparación se hace con el mismo entorno.

## Docker (ejercicio 8)

Requisitos previos: Docker y Docker Compose instalados, y el dato institucional copiado a `data/raw/Base_Migracion_2009-2026jun.xlsx`
(nunca se incorpora a la imagen; se monta como volumen).

```bash
export GIT_COMMIT=$(git rev-parse HEAD)      # para que el run quede trazado al commit (no hay .git dentro del contenedor)
docker compose build                 # construye la imagen (tablero + pipeline + MLflow comparten la misma imagen)
docker compose up -d app mlflow      # tablero en http://localhost:8501, MLflow en http://localhost:5000
docker compose run --rm pipeline     # corre el pipeline una vez (usa config/pipeline.yaml montado)
docker compose run --rm pipeline --config config/pipeline_demo.yaml --restaurar <VERSION>   # restaurar (ver seccion de demo)
docker compose down                  # detener los servicios (los datos persisten en los volúmenes)
```

`./data`, `./config`, `./runs`, `./published` y `./mlflow` se montan como volúmenes (ver `docker-compose.yml`): persisten en el
host aunque se eliminen y vuelvan a crear los contenedores, y el dato institucional nunca queda dentro de la imagen (`.dockerignore`
excluye `data/raw`, `mlflow/`, `runs/` y `published/` incluso si alguien construye la imagen sin Compose).

Probado en este equipo el 2026-11-02: `docker compose build` construyó la imagen sin errores, `app` y `mlflow` quedaron
arriba (`docker compose ps`), y `docker compose run --rm pipeline` corrió el pipeline completo dentro del contenedor con
el mismo resultado que en local (las 7 series rechazadas). Europa difirió en ~20 viajeros/mes entre el entorno local y el
contenedor (3 805 vs. 3 825): es justo el caso de no convergencia de ARIMA entre entornos ya documentado más arriba, no un
error de la imagen.

## Prueba de fallo y recuperación (ejercicio 7.4-7.5)

Para demostrar que un problema real detiene el pipeline sin tocar lo publicado, y que una versión aprobada puede restaurarse:

```bash
# 1. Copia de la fuente con un problema introducido (ejemplo: falta la columna Frontera)
python -c "import pandas as pd; d = pd.read_excel('data/raw/Base_Migracion_2009-2026jun.xlsx'); d.drop(columns=['Frontera']).to_csv('data/raw/fuente_con_falla.csv', index=False)"

# 2. Correr el pipeline contra esa copia: debe detenerse (código 2) y no tocar published/
python -m pipeline.run --fuente data/raw/fuente_con_falla.csv

# 3. Confirmar que published/current.json no cambió, y que el run quedó documentado
cat published/current.json
cat runs/<run_id_del_paso_2>/reporte_controles.md

# 4. Corregir (usar la fuente real) y volver a correr
python -m pipeline.run

# 5. Restaurar una versión anterior aprobada y confirmar que el tablero la vuelve a consultar
#    (si published/ nunca tuvo una versión real aprobada, usa la config de demo: ver sección siguiente)
python -m pipeline.run --restaurar <VERSION_APROBADA>
streamlit run app/app.py   # la pestaña ④ debe mostrar la versión restaurada en el aviso superior
```

## Demostración con config de prueba (ejercicios 6 y 7.5)

Con los datos institucionales actuales, **ninguna serie cumple la regla de aceptación oficial** (ver
`docs/informe_adenda_entrega_final.md`, sección 5.5): nunca hay una versión en `published/` para mostrar
en el tablero ni para restaurar. Para demostrar que el mecanismo en sí funciona (publicación, tablero,
restauración), se usa una configuración de demostración aparte, con umbrales deliberadamente relajados y
carpetas separadas para no tocar `published/` ni `runs/` reales:

```bash
python -m pipeline.run --config config/pipeline_demo.yaml   # genera una versión "aprobada" en published_demo/
python -m pipeline.run --config config/pipeline_demo.yaml   # una segunda versión, para poder restaurar la primera después
ls published_demo/versions/
python -m pipeline.run --config config/pipeline_demo.yaml --restaurar <PRIMERA_VERSION>
PUBLISHED_DIR=published_demo streamlit run app/app.py        # el tablero lee published_demo/ en vez de published/
```

`config/pipeline_demo.yaml` está señalada en sus propios comentarios como "solo para demostración"; la
regla real (`config/pipeline.yaml`) no se modifica. `PUBLISHED_DIR` es una variable de entorno opcional
que `app/app.py` usa en vez de `published/` cuando está definida (por defecto usa `published/`, que debe
quedar intacto para la entrega real).

## Estado de la entrega

Implementado en este repositorio: alcance y diagrama (`Lab11.pdf`), pipeline con las 11 etapas, los 6 controles de calidad,
monitoreo (3 verificaciones), registro en MLflow, tablero leyendo `published/current.json` para la pestaña ④, Docker/Compose
y la regla de aceptación congelada (`config/pipeline.yaml`).

Corrida oficial del 2026-11-02 con el dato institucional real: **las 7 series rechazadas** (no solo `Total`), con MAE del
modelo entre 1.57x y 8.27x el de la referencia Seasonal Naive — ver el detalle y la explicación en
`docs/informe_adenda_entrega_final.md` (sección 5.5). `published/` queda sin ninguna versión aprobada, tal como se espera
que el pipeline se comporte en este caso; no se modificó la regla para forzar una aprobación.

**Pendiente de completar por el equipo** (requiere acciones manuales: comparar dos corridas, tomar capturas, correr la
prueba de fallo/recuperación y la demo de config de prueba): llenar los marcadores "Pegar aquí" en
`docs/informe_adenda_entrega_final.md` con la salida real de `scripts/consultar_mlflow.py comparar` (4.2), capturas de la UI
de MLflow (4.3), evidencia de la prueba de fallo y recuperación (7.4) y de la restauración con la config de demo (7.5), y
construir/probar la imagen Docker (8).
