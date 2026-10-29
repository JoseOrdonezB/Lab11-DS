# Observatorio de Turismo Sostenible · Guatemala — Laboratorios 10 y 11 (CC3066)

Tablero interactivo en **Streamlit + Plotly** sobre las llegadas internacionales de viajeros (INGUAT/Migración, 2009–jun 2026).
Reutiliza los modelos del Laboratorio 1 (ARIMA, Seasonal Naive, Prophet); **no se entrenan modelos nuevos**.

## Ejecutar
```bash
pip install -r requirements.txt
streamlit run app/app.py
```

## Estructura
- `app/app.py` — tablero (avance: V1 serie con nivel de detalle, V2↔V3 región→país enlazadas, V4 pronóstico vs observado).
- `data/` — archivos ya exportados que lee el tablero (`base_viajeros.csv.gz`, `series_mensuales.csv`, `predicciones_lab1.csv`, `metricas_lab1.csv`).
- `scripts/exportar_modelos_lab1.py` — regenera `data/` desde `Base_Migracion_2009-2026jun.xlsx` con los mismos modelos y parámetros del Lab 1.
- `.streamlit/config.toml` — tema de color.

## Convención de color (igual en toda la app)
Verde azulado = dato observado · Naranja = estimación de un modelo · Gris = referencia / pandemia · Azul marino = texto y selección.

---

# Laboratorio 11: pipeline MLOps (avance)

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

## Qué se guarda por ejecución

`runs/<run_id>/`: `controles.csv`, `reporte_controles.md`, `metricas.csv`, `estimaciones.csv`, `backtest_detalle.csv`, `manifest.json` (commit, hashes, dependencias, períodos),
`run.log` y `run_summary.json` (inicio, fin, etapas completadas, advertencias y resultado de la publicación).
Una versión aprobada es una copia inmutable de esos archivos en `published/versions/`.

## Restaurar una versión anterior

```bash
python -m pipeline.run --restaurar v2026.10.29-01
```

## Pendiente para la entrega final

Registro en MLflow, tablero leyendo `published/current.json` (hoy sigue leyendo `data/`), tres verificaciones de monitoreo, Docker/Compose,
prueba de fallo y recuperación documentada, y congelar los umbrales de aceptación (sección 5). Los de `config/pipeline.yaml` son provisionales.
