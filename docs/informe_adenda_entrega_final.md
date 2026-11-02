# Adenda al informe técnico — entrega final (Laboratorio 11)

Este documento complementa `Lab11.pdf` (que cubre el ejercicio 1: alcance y diagrama, entregado como avance el 29 de
octubre). Incorporar estas secciones al informe antes de exportarlo a PDF.

## 4.2 Reproducibilidad: dos ejecuciones con los mismos datos y configuración

Correr:

```bash
python -m pipeline.run
python -m pipeline.run
python scripts/consultar_mlflow.py comparar
```

`comparar` confirma que ambas ejecuciones comparten el hash de fuente y de configuración, y compara estimaciones y métricas
contra `reproducibilidad.tolerancia_abs` (1e-6 viajeros/mes, ver `config/pipeline.yaml`). En la misma máquina, dos ejecuciones
de ARIMA sobre los mismos datos dan diferencia 0: no hay componentes aleatorios en ARIMA ni en Seasonal Naive (por eso existe
`semilla` en la configuración, por si se agrega alguno). Entre máquinas con otras versiones de las librerías numéricas sí
puede haber diferencias, sobre todo en Europa y Vía Marítima, donde el optimizador de ARIMA no siempre converge y puede
detenerse en un punto distinto según la implementación de BLAS/LAPACK; por eso la comparación de reproducibilidad se hace
dentro del mismo entorno (o del mismo contenedor Docker).

Evidencia real (2026-11-02):

```
A: 20261102-073538-4221f6 (b32f1ef867064119b0029f2e18673096)
B: 20261102-074510-ccc52e (7f7fc204d57342baa52f5126a5f95c3d)

Misma fuente y misma configuración: sí  (fuente cdaba77918ae / cdaba77918ae, config 6f10db06b813 / 6f10db06b813)
Mismo commit: sí

Estimaciones: 126 y 126 filas, 0 sin pareja, diferencia máxima 0.000e+00 viajeros/mes
Métricas: 50 comparadas, diferencia máxima 0.000e+00

Resultado: EQUIVALENTES (tolerancia 1e-06 viajeros/mes)
```

Diferencia 0 en las 126 estimaciones y en las 50 métricas comparadas, exactamente lo esperado: ARIMA y
Seasonal Naive no tienen componentes aleatorios, así que dos corridas con la misma fuente y la misma
configuración producen resultados idénticos bit a bit en la misma máquina.

## 4.3 Ejecuciones fallidas

`docs/mlflow_ejecuciones.csv` (regenerado con `python scripts/consultar_mlflow.py listar`) documenta, entre otras, una
ejecución FAILED por fuente no encontrada (código 1, causa "fuente no encontrada: no_existe.xlsx") y ejecuciones FINISHED
con resultado "candidato rechazado" (código 3): llegaron a la evaluación pero no cumplieron la regla de aceptación, por lo
que published/ no se modificó. Ninguna ejecución detenida antes de la etapa 5 (evaluación) tiene métricas de error
registradas: pipeline/registro.py filtra valores NaN antes de llamar a mlflow.log_metrics, así que no hay forma de que el
pipeline invente una métrica para un run que nunca llegó a calcularla.

**[Insertar aquí 1-2 capturas de la UI de MLflow: la lista de runs del experimento observatorio-turismo-guatemala mostrando
al menos un run FAILED y un run FINISHED, y el detalle de un run con sus tags causa y controles_resultado. Las capturas
complementan docs/mlflow_ejecuciones.csv; no lo sustituyen.]**

## 5. Validación temporal, resultados y regla de aceptación

### 5.1 Validación temporal (sin fuga de información futura)

El backtest (`pipeline/modelos.backtest`) usa origen expansivo y un paso adelante: para cada mes del período jul-2025 a
jun-2026, el modelo se ajusta solo con información anterior a ese mes y estima exactamente ese mes. El pronóstico oficial
(jul-dic 2026) se ajusta con todo el histórico disponible hasta junio de 2026. En ningún punto se usa un valor observado
posterior al mes que se está evaluando.

**Limitación para enero y febrero de 2026:** el corte de la fuente institucional ya incluye esos meses, y el orden ARIMA
de cada serie se fijó en el Laboratorio 1 después de haber visto el histórico hasta junio de 2026. No es posible reconstruir
un contrafactual limpio en el que el equipo "no sabía" el valor de enero-febrero 2026 al momento de elegir el modelo. Se
documenta esta limitación en vez de simular una ignorancia que no existió; el backtest de origen expansivo sigue siendo
válido porque evalúa capacidad predictiva un paso adelante, no la elección del orden ARIMA.

### 5.2 Métrica formal y tratamiento del MAPE

`pipeline/modelos.metricas` calcula MAE y RMSE sobre todos los meses con valor observado y estimado finitos; son las
métricas principales porque no dependen de que el denominador sea distinto de cero. El MAPE se calcula únicamente con
observaciones mayores que cero (filtro `pos = real > 0`); los meses observados en cero quedan excluidos y se cuentan en
`n_excl_mape`, que queda registrado en `metricas.csv`. El control C5 además marca con WARN cualquier mes del backtest con
valor observado igual a cero, documentando la razón de la exclusión en `controles.csv`.

### 5.3 Comparación contra una referencia sencilla

La referencia es Seasonal Naive (repite el mismo mes del año anterior; `pipeline/modelos.seasonal_naive`), evaluada sobre
exactamente los mismos 12 meses del backtest que el modelo ARIMA (`pipeline/modelos.backtest` calcula ambas predicciones en
el mismo corte, a partir del mismo `train`). Si el mes de referencia no tiene dato, la predicción de la referencia queda en
NaN (no se inventa un valor), y esos meses quedan fuera del cálculo de MAE/RMSE de la referencia.

### 5.4 Regla de aceptación (congelada en `config/pipeline.yaml`, sección `aceptacion`)

Una versión candidata se aprueba solo si, para cada serie obligatoria (hoy únicamente `Total`):

1. Los 6 controles de calidad críticos están en OK (si alguno falla, el pipeline ya se detuvo antes de llegar aquí).
2. Todas las estimaciones publicadas son finitas, no negativas y no superan 1.5 veces el máximo mensual observado de su
   serie (`umbrales.rango_plausible_max_factor`): protege contra una extrapolación sin sentido.
3. Hay al menos 6 observaciones comparables en el backtest (`aceptacion.min_obs_evaluacion`); con menos, no se aprueba por
   desempeño, para no decidir con una muestra demasiado chica.
4. El MAE del modelo no supera el 20 % del nivel mensual promedio observado en el backtest (`aceptacion.mae_rel_max`): un
   umbral absoluto, ligado a la escala de la variable (viajeros/mes), no a cuánto le gane o pierda a la referencia.
5. El MAE del modelo no supera 1.25 veces el MAE de Seasonal Naive (`aceptacion.margen_vs_referencia`): el modelo puede ser
   algo peor que la referencia sencilla, pero no sustancialmente peor.

Estos valores se fijaron antes de la ejecución final y no se modifican después de ver sus resultados (ver el comentario en
`config/pipeline.yaml`, sección `aceptacion`).

### 5.5 Resultado observado y qué se hizo con él

Corrida oficial del 2026-11-02 (run_id 20261102-073538-4221f6, fuente_sha256 cdaba77918ae...,
config_sha256 actual de config/pipeline.yaml): **ninguna de las 7 series cumple la regla**, no
solo Total. MAE del modelo vs. MAE de la referencia (Seasonal Naive), ambos en viajeros/mes,
con n=12 observaciones comparables en todas:

| Serie | MAE modelo | MAE referencia | Razón del modelo / referencia | Motivo del rechazo |
|---|---|---|---|---|
| Total | 40 387 | 12 027 | 3.36x | excede margen_vs_referencia (1.25x) |
| Vía Aérea | 14 714 | 9 348 | 1.57x | excede margen_vs_referencia |
| Vía Terrestre | 25 376 | 12 530 | 2.03x | excede margen_vs_referencia |
| Vía Marítima | 554 | 67 | 8.27x | excede mae_rel_max (554 > 20% del nivel, 592) y margen_vs_referencia |
| América del Centro | 24 862 | 12 187 | 2.04x | excede margen_vs_referencia |
| América del Norte | 14 254 | 6 464 | 2.21x | excede margen_vs_referencia |
| Europa | 3 805 | 1 151 | 3.31x | excede mae_rel_max (3 805 > 20% del nivel, 3 048) y margen_vs_referencia |

Como la serie obligatoria `Total` no cumple, el candidato se rechazó completo (código de salida 3);
`published/` no se tocó. El equipo decidió **no modificar el umbral para forzar una aprobación**: el
PDF del laboratorio pide explícitamente aplicar la regla definida sin ajustarla después de ver el
resultado, y es exactamente la situación en la que se encuentra esta corrida.

**Por qué ocurre en las 7 series, no solo en Total:** el backtest (jul-2025 a jun-2026) coincide con
la fase final de la recuperación pos-pandemia del turismo, un fenómeno ya documentado como limitación
en la sección de alcance (`Lab11.pdf`, antes de ejecutar el pipeline por primera vez). Cada ARIMA se
ajustó con el histórico 2009-2021 (antes de la pandemia); ninguno tiene un mecanismo para anticipar un
salto estructural de esa magnitud. Seasonal Naive, en cambio, repite el mismo mes del año anterior, que
ya forma parte de la recuperación, así que queda mucho más cerca del nivel real sin modelar ninguna
tendencia. No es que Seasonal Naive sea mejor en general: en este período específico, copiar el año
anterior es una heurística más robusta que un ARIMA de orden bajo sin componente de tendencia fuerte.
Vía Marítima y Europa, además, tuvieron problemas de convergencia del optimizador de ARIMA en la
mayoría de los cortes del backtest (ver `run.log`), lo que empeora aún más su desempeño relativo.

**No es obligatorio superar a la referencia** (sección 5.5 del enunciado): se documenta el resultado y
se aplica la regla tal como quedó definida. `published/` queda sin ninguna versión aprobada, y el
tablero lo comunica explícitamente con el mensaje "Estimaciones no disponibles" (sección 6.4).

**Nota sobre los ejercicios 6 y 7.5:** como ninguna versión aprueba con la regla oficial, se generó una
versión "aprobada" aparte con `config/pipeline_demo.yaml` (umbrales deliberadamente relajados,
`published_demo/` en vez de `published/`) únicamente para demostrar que el mecanismo de publicación,
el tablero y la restauración funcionan. Esa config está señalada como demo en sus comentarios y no debe
confundirse con la regla real.

## 6. Integración y publicación controlada

El tablero (`app/app.py`, función `cargar_publicado`) lee únicamente `published/current.json` y los archivos de la versión
que ese puntero indica; nunca lee un archivo de `runs/` (candidato). Si `current.json` no existe o no se puede leer, la
función devuelve `None` y la pestaña ④ muestra "Estimaciones no disponibles" en vez de datos inventados o antiguos (ejercicio
6.4).

Cuando sí hay una versión publicada, la pestaña ④ muestra: la versión (`version_procedimiento`), el identificador de
ejecución (`run_id`), la fecha de aprobación, el MAE del modelo y de la referencia, y si la serie fue aprobada o no por la
regla de aceptación, con una nota explicando qué significa el MAE y los períodos evaluados (ejercicio 6.2). Las demás
pestañas (V1, V2↔V3, V5, V6, V7, V8) muestran datos observados o comparaciones exploratorias del Laboratorio 1; no pasan
por el flujo de aprobación porque no son estimaciones publicadas por el pipeline, y el tablero lo aclara en el aviso
superior.

Verificado el 2026-11-02 con la versión de demo publicada (config/pipeline_demo.yaml,
published_demo/, ver nota en 5.5): corriendo PUBLISHED_DIR=published_demo streamlit run app/app.py,
la pestaña ④ mostró correctamente el aviso superior con versión, run_id y fecha, y la sección
"Pronóstico oficial publicado" con el gráfico (observado/ARIMA/Seasonal Naive/pronóstico) y las
tarjetas de MAE del modelo y de la referencia. Confirmado visualmente por el equipo sin errores.

Insertar aquí una captura de pantalla de esa vista, y otra del tablero contra published/ real (sin
PUBLISHED_DIR), que debe mostrar "Estimaciones no disponibles" porque la regla oficial rechazó las 7 series.

## 7. Monitoreo y recuperación

`pipeline/monitoreo.py` corre tres verificaciones en cada ejecución (ver tabla en el README, sección "Monitoreo y
alertas"): actualización (cobertura), calidad (faltantes/duplicados/cobertura vs. la versión vigente) y resultados
(negativos, no finitos y variación de pronóstico vs. la versión vigente). Quedan en `monitoreo.csv` por corrida, se agregan
a las advertencias del run y se registran en MLflow. Una variación alta genera una alerta para revisión manual, no una
conclusión automática de pérdida de precisión (ejercicio 7.3): el error predictivo solo se actualiza cuando existen
observaciones comparables.

**Prueba controlada (7.4):** ver "Prueba de fallo y recuperación" en el README. Resumen esperado: al correr el pipeline
contra una copia de la fuente sin la columna Frontera, el control C1 falla, el pipeline termina con código 2, y
published/current.json queda exactamente igual que antes de la corrida.

Evidencia real (2026-11-02):

```
2026-11-02 08:03:45 Etapa 1 lectura: fuente_con_falla.csv, 161036 filas, sha256 fuente b4eecc712811, config 6f10db06b813
2026-11-02 08:03:45 C1 columnas y tipos: FAIL - Faltan columnas indispensables: ['Frontera']
2026-11-02 08:03:45 DETENIDO: control crítico en FAIL -> ['C1 columnas y tipos']. No se reemplazan los resultados vigentes.
2026-11-02 08:03:45 FIN run 20261102-080344-1cdcb5: detenido por control crítico; resultados vigentes intactos (código 2)

CODIGO DE SALIDA: 2

$ ls published/
ls: published/: No such file or directory
```

`published/` ni siquiera existe: confirma que nunca se publicó una versión real (ver 5.5) y que esta
corrida fallida tampoco la creó ni la tocó. Al corregir (quitar --fuente, usar la fuente real), el
pipeline vuelve a correr con normalidad (ver evidencia de 4.2, corridas del mismo día con la fuente real).

Restauración (7.5): ver la opción --restaurar en el README. La función de restaurar reescribe el puntero de publicación de
forma atómica apuntando a una versión ya aprobada, sin modificar esa versión, y el tablero la consulta de inmediato en la
siguiente recarga porque siempre lee el puntero vigente.

Verificado el 2026-11-02 con published_demo/ (ver nota en 5.5): se corrieron 2 versiones
(v2026.11.02-01 y v2026.11.02-02), luego se restauró la primera:

```bash
python -m pipeline.run --config config/pipeline_demo.yaml --restaurar v2026.11.02-01
# salida: current.json apunta ahora a v2026.11.02-01
```

`published_demo/current.json` después de restaurar:

```json
{
  "version": "v2026.11.02-01",
  "ruta": "versions/v2026.11.02-01",
  "aprobado_en": "2026-11-02T07:47:13",
  "run_id": "20261102-074701-979ba2",
  "version_anterior": "v2026.11.02-02",
  "restaurada_en": "2026-11-02T07:50:29"
}
```

`version_anterior` quedó en v2026.11.02-02 (la que estaba vigente antes de restaurar), confirmando que
el puntero cambió sin modificar el contenido de ninguna versión. Al recargar el tablero
(PUBLISHED_DIR=published_demo streamlit run app/app.py) la pestaña ④ mostró de inmediato la versión
restaurada en el aviso superior, sin reiniciar el servidor ni limpiar caché manualmente.

Insertar aquí captura del tablero mostrando la version restaurada.
