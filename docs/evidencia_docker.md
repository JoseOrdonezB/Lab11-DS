# Evidencia de Docker y persistencia (sección 8)

Registro de las comprobaciones hechas el 2026-11-01/02 sobre la copia local del repositorio.

## Construcción y arranque

```bash
docker compose build
docker compose up -d mlflow tablero
docker compose ps
curl -fsS http://localhost:5001/health
```

Resultado observado:

- `observatorio-lab11-mlflow-1`: `Up (healthy)`, puerto `0.0.0.0:5001->5000/tcp`.
- `observatorio-lab11-tablero-1`: `Up`, puerto `0.0.0.0:8501->8501/tcp`.
- `GET http://localhost:5001/health` respondió `OK`.
- `GET http://localhost:8501` respondió HTTP 200.

## Corrida del pipeline en el contenedor

```bash
docker compose run --rm pipeline
```

La corrida terminó con código 0 y publicó `v2026.11.02-01`.
El manifiesto de esa versión registra:

- `run_id`: `20261102-020929-bb05af`
- `mlflow_run_id`: `48daaef8440d4e228674c439deabce02`
- `mlflow_tracking_uri`: `http://mlflow:5000`
- `fuente_hash`: `cdaba77918ae…`
- `config_hash`: `7818d835f7ae…`
- Decisión: `aprobado: true`.
- Monitoreo: M1 OK, M2 OK, M3 ALERTA (variación mes a mes de Europa 94.4 % y Vía Marítima 36 %; series de referencia, alerta no bloqueante).

Métricas de Docker frente a la corrida local canónica:

| Serie | Docker MAE | Docker MAE / nivel | Estado |
|---|---:|---:|---|
| Total | 40,387 | 14.7 % | aprobado |
| Vía Aérea | 14,714 | 14.1 % | aprobado |
| Vía Terrestre | 25,376 | 14.8 % | aprobado |
| Vía Marítima | 554 | 93.7 % | referencia |
| América del Centro | 24,862 | 14.6 % | aprobado |
| América del Norte | 14,254 | 19.6 % | aprobado |
| Europa | 3,825 | 25.1 % | referencia |

La diferencia de Europa (3,825 vs. 3,963 en local) se debe a la versión de Python y al punto donde se detiene el optimizador
de ARIMA cuando no converge. Las decisiones de aceptación son las mismas.

## Persistencia tras `docker compose down`

```bash
shasum -a 256 published/current.json     # antes
docker compose down
docker compose ps -a                     # sin contenedores
shasum -a 256 published/current.json     # después: mismo hash
sqlite3 mlflow/mlflow_docker.db "select run_uuid, status from runs order by start_time desc limit 1;"
```

Resultado observado:

- Antes: `c78560c4b0dd26f7accd8c5944d31348c24ac527b5af331296adc83447551c95`.
- Después de `down`: el mismo hash; `mlflow/mlflow_docker.db` (972 KB) siguió en disco.
- El run `48daaef8440d…` seguía en la base con estado `FINISHED`.
- Al recrear con `docker compose up -d mlflow tablero`, el run siguió disponible por la API de MLflow y el tablero respondió
  HTTP 200 con la versión publicada.

## Aislamiento del dato institucional

- `.dockerignore` excluye `data/raw/*`, `runs/`, `mlflow/`, `mlruns/` y `.git/`.
- `docker-compose.yml` monta `./data/raw:/app/data/raw:ro` solo en el servicio `pipeline`.
- El tablero monta `./data` y `./published` en solo lectura.
- La imagen no contiene el `.xlsx`; se verifica con:

```bash
docker run --rm observatorio-lab11:local sh -lc 'ls -la /app/data/raw || true'
```

## Prueba desde una copia limpia

Se clonó el repositorio en un directorio temporal, se copió únicamente el `.xlsx` institucional a `data/raw/` y se ejecutó
Compose desde el clon:

```bash
git clone <repo> /tmp/lab11-clean
cp <repo>/data/raw/Base_Migracion_2009-2026jun.xlsx /tmp/lab11-clean/data/raw/
cd /tmp/lab11-clean
docker compose -p lab11-clean build
docker compose -p lab11-clean up -d mlflow
docker compose -p lab11-clean run --rm pipeline
```

Resultado observado:

- La corrida terminó con código 0 y publicó `v2026.11.02-02`
  (`run_id` `20261102-021301-d6d6d5`, MLflow `ed692d72e66a497796dac56ebc305158`).
- `mlflow/mlflow_docker.db` se creó desde cero en el clon y el run quedó `FINISHED`.
- El clon solo mostró cambios esperados: `published/current.json` modificado y la versión nueva sin seguimiento.
- La imagen no contiene el `.xlsx`: `find /app -name "*.xlsx"` no devolvió archivos y `/app/data/raw/` solo tiene `.gitkeep`.
- No se usaron `runs/`, `mlflow/` ni archivos locales sin versionar de la copia original.

## Nota sobre las dos bases de MLflow

La base local `mlflow/mlflow.db` conserva una ubicación de artefactos específica del host
(`file:///Users/joseordonez/.../mlflow/artifacts`). Para no romper las corridas locales, el servidor de Docker usa
`mlflow/mlflow_docker.db` y artefactos en `/app/mlflow/artifacts`. Ambas bases están bajo `mlflow/`, que no se versiona.
