"""Reportes legibles de la corrida: controles de calidad (3.2) y validación temporal (5)."""
import numpy as np
import pandas as pd


CATALOGO = {
    "C1": ("Columnas y tipos",
           "Que existan las columnas indispensables del config y que su tipo sea compatible (entero, numérico, texto).",
           "Nunca.",
           "Falta una columna indispensable o tiene un tipo incompatible. Si falla, no se evalúan los demás controles."),
    "C2": ("Fechas y cobertura",
           "Que Año y Mes cod formen fechas válidas y que cada mes de la cobertura configurada tenga información.",
           "Hay filas fuera de la cobertura, o meses sin filas en alguna serie distinta de Total (quedan como faltantes, nunca como cero).",
           "Hay fechas inválidas, o un mes de la cobertura sin información en la serie Total."),
    "C3": ("Unicidad",
           "Que no haya filas con la misma clave (año, mes, vía, frontera, país, región, tipo de viajero).",
           "Hay claves repetidas pero su porcentaje no supera duplicados_pct_fallo (se suman como registros parciales, no se borran).",
           "El porcentaje de filas con clave repetida supera duplicados_pct_fallo del config."),
    "C4": ("Valores faltantes",
           "Nulos en las columnas utilizadas, distinguiendo ausencias permitidas (columnas_nulos_permitidos) de las que impiden estimar.",
           "Hay nulos solo en columnas permitidas (Frontera, País).",
           "Hay nulos en cualquier otra columna utilizada."),
    "C5": ("Valores y denominadores",
           "Conteos negativos, valores no finitos (inf o no numéricos) en Viajero y meses con valor observado cero en el backtest (denominador del MAPE).",
           "Hay meses observados iguales a cero en el backtest (se excluyen del MAPE).",
           "Hay algún conteo negativo o algún valor no finito."),
    "C6": ("Regla metodológica",
           "Que la serie mensual provenga de la fuente mensual (sin columnas diarias), que los tipos de viajero sean los conocidos y que Total sin el tipo excluido sea la suma de las vías.",
           "Nunca.",
           "La fuente trae columnas diarias, hay tipos de viajero desconocidos o Total no coincide con la suma de las vías."),
}


def _clave(nombre):
    return nombre.split()[0]


def generar(ctrl, run_id, hashes, ruta):
    """ctrl: DataFrame de controles (con columnas control, estado, n_afectados, detalle). Escribe el .md en ruta."""
    conteo = ctrl["estado"].value_counts().to_dict()
    fallos = ctrl[ctrl["estado"] == "FAIL"]
    decision = ("DETENIDO: un control crítico falló; no se reemplazan los resultados vigentes del tablero."
                if len(fallos) else "APROBADO por controles: la ejecución continúa a preparación y modelado.")
    L = [f"# Reporte de controles de calidad — corrida {run_id}", "",
         f"- Fuente (SHA-256): `{hashes.get('fuente', 'n/d')}`",
         f"- Config (SHA-256): `{hashes.get('config', 'n/d')}`",
         "- Resumen: " + ", ".join(f"{k} {conteo.get(k, 0)}" for k in ("OK", "WARN", "FAIL", "OMITIDO")),
         f"- Decisión: {decision}", "",
         "| Control | Estado | Afectados | Resultado |", "|---|---|---|---|"]
    for _, r in ctrl.iterrows():
        L.append(f"| {r['control']} | {r['estado']} | {r['n_afectados']} | {str(r['detalle']).replace('|', '/')} |")
    L += ["", "## Qué verifica cada control", ""]
    for k, (nombre, verifica, warn, fail) in CATALOGO.items():
        L += [f"**{k} {nombre}**", f"- Verifica: {verifica}", f"- Advertencia (WARN): {warn}", f"- Detiene (FAIL): {fail}", ""]
    L += ["Los controles son críticos: un FAIL detiene el pipeline antes de preparar datos o tocar `published/`.",
          "Los meses sin cobertura nunca se convierten en cero."]
    ruta.write_text("\n".join(L) + "\n", encoding="utf-8")


def _num(x, decimales=0):
    try:
        return f"{float(x):,.{decimales}f}" if np.isfinite(float(x)) else "n/d"
    except (TypeError, ValueError):
        return "n/d"


def generar_validacion(met, bt, cfg, ruta, run_id, hashes, aprobado, razones):
    """Reporte de la sección 5: regla congelada, métricas, referencia y ene-feb 2026.

    Se escribe reporte_validacion.md y se publica junto con la versión aprobada.
    """
    a = cfg["aceptacion"]
    m = cfg["modelo"]
    p = cfg["periodos"]
    obligatorias = ", ".join(a["series_obligatorias"])
    decision = "APROBADO" if aprobado else "RECHAZADO"
    L = [f"# Reporte de validación temporal — corrida {run_id}", "",
         f"- Regla congelada: **{a.get('regla_congelada', 'n/d')}**",
         f"- Criterio de desempeño: MAE ≤ {a['mae_rel_max']:.0%} del nivel medio mensual observado en el backtest.",
         f"- Observaciones mínimas: {a['min_obs_evaluacion']} por serie.",
         f"- Series obligatorias: {obligatorias}.",
         f"- Referencia: {m['referencia']} (se calcula y se reporta; **no es un requisito** superarla).",
         f"- Período de backtest: {p['backtest']['inicio']} a {p['backtest']['fin']} "
         f"(origen expansivo, un paso hacia adelante).",
         f"- Decisión de la corrida: **{decision}**.",
         f"- Fuente (SHA-256): `{hashes.get('fuente', 'n/d')}`",
         f"- Config (SHA-256): `{hashes.get('config', 'n/d')}`", "",
         "## Resultados por serie", "",
         "| Serie | n | Nivel medio | MAE | MAE / nivel | RMSE | MAPE | Excl. MAPE | Ref. MAE | MAE / ref. | ¿Supera ref.? | Estado | Motivo |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|"]
    for _, r in met.iterrows():
        estado = "aprobado" if r["cumple_regla"] else "referencia"
        supera = "sí" if r["supera_referencia"] else "no"
        L.append("| {serie} | {n} | {nivel} | {mae} | {pct} | {rmse} | {mape} | {excl} | {ref} | {ratio} | {supera} | {estado} | {motivo} |".format(
            serie=r["serie"], n=int(r["n_obs"]), nivel=_num(r["nivel_medio"]), mae=_num(r["MAE"]),
            pct=_num(r["MAE_pct_nivel"], 1) + "%", rmse=_num(r["RMSE"]),
            mape=(_num(r["MAPE_pct"], 1) + "%") if np.isfinite(r["MAPE_pct"]) else "n/d",
            excl=int(r["n_excl_mape"]), ref=_num(r["baseline_MAE"]),
            ratio=_num(r["ratio_referencia"], 2), supera=supera, estado=estado,
            motivo=str(r["motivo"]).replace("|", "/")))

    L += ["", "El nivel medio es el promedio mensual observado de la serie en los 12 meses del backtest. "
          "El MAPE excluye observaciones iguales a cero; la columna «Excl. MAPE» indica cuántas se excluyeron. "
          "La referencia se evalúa sobre los mismos meses que el modelo.", "",
          "## Enero y febrero de 2026", "",
          "El backtest de origen expansivo estima cada mes usando solo información anterior al mes evaluado. "
          "Para enero de 2026 el ajuste termina en diciembre de 2025; para febrero, en enero de 2026. "
          "No se usa el valor observado del mes que se está estimando.", "",
          "| Serie | Mes | Observado | ARIMA | Referencia | Error ARIMA | APE ARIMA | Error ref. | APE ref. |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    sel = bt[bt["periodo"].isin(pd.to_datetime(["2026-01-01", "2026-02-01"]))].copy()
    for _, r in sel.iterrows():
        real = float(r["real"])
        e_mod = float(r["pred_modelo"]) - real
        e_ref = float(r["pred_referencia"]) - real
        ape_mod = 100 * abs(e_mod) / real if real else np.nan
        ape_ref = 100 * abs(e_ref) / real if real else np.nan
        L.append("| {serie} | {mes} | {real} | {mod} | {ref} | {emod} | {apemod} | {eref} | {aperef} |".format(
            serie=r["serie"], mes=r["periodo"].strftime("%Y-%m"), real=_num(real),
            mod=_num(r["pred_modelo"]), ref=_num(r["pred_referencia"]),
            emod=_num(e_mod), apemod=_num(ape_mod, 2) + "%",
            eref=_num(e_ref), aperef=_num(ape_ref, 2) + "%"))

    L += ["", "## Decisión y justificación", ""]
    if aprobado:
        L.append(f"La versión se **aprueba** porque la serie obligatoria ({obligatorias}) cumple la regla y "
                 "las salidas son finitas, no negativas y están dentro del rango plausible.")
    else:
        L.append(f"La versión se **rechaza**. Motivos: {'; '.join(razones)}.")
    L += ["", "El umbral del 20 % se fija sobre la escala de la variable: el nivel mensual del Total en el backtest "
          "es del orden de cientos de miles de viajeros, por lo que un error promedio de una quinta parte del nivel "
          "es una tolerancia explícita para planificación, no una promesa de precisión puntual. "
          "La comparación con Seasonal Naive se reporta para transparencia; el laboratorio no exige superar la "
          "referencia (5.5). Cuando el modelo no la supera, se explica y se aplica la regla sin cambiarla para aprobar.",
          "", "Las series que no cumplen se publican como **referencia** (Seasonal Naive), no como estimaciones "
          "ARIMA aprobadas; el tablero debe distinguir ese estado.", "",
          "## Limitaciones", "",
          "- El backtest tiene 12 cortes; es una muestra corta para evaluar error predictivo.",
          "- El código y la regla se especificaron después de observar los datos; el backtest es retrospectivo, "
          "no un experimento pre-registrado.",
          "- Enero y febrero de 2026 se estiman sin fuga de información, pero la pandemia, la recuperación y el "
          "cambio metodológico 2022–2023 impiden un contrafactual limpio.",
          "- 2026 solo tiene observaciones hasta junio; jul–dic 2026 no se puede validar todavía.",
          "- En Vía Marítima y Europa ARIMA no converge en varios cortes; sus resultados se reportan y, si no "
          "cumplen la regla, se publican como referencia.",
          "- Las estimaciones suponen continuidad del patrón histórico; no anticipan pandemias, shocks ni "
          "revisiones de la fuente."]
    ruta.write_text("\n".join(L) + "\n", encoding="utf-8")


def generar_monitoreo(mon, meta, ruta):
    """Reporte legible de las tres verificaciones de monitoreo (sección 7)."""
    alertas = mon[mon["estado"] == "ALERTA"]
    decision = ("CON ALERTAS PARA REVISIÓN; la publicación no se bloquea por una variación alta"
                if len(alertas) else "SIN ALERTAS")
    L = [f"# Reporte de monitoreo — ejecución {meta.get('run_id', 'n/d')}", "",
         f"- Versión generada: **{meta.get('version', 'n/d')}**",
         f"- Inicio: {meta.get('inicio', 'n/d')} · Fin: {meta.get('fin', 'n/d')}",
         f"- Resultado: **{decision}**.",
         f"- Fuente (SHA-256): `{meta.get('fuente_hash', 'n/d')}`",
         f"- Config (SHA-256): `{meta.get('config_hash', 'n/d')}`", "",
         "| Verificación | Estado | Afectados | Umbral | Resultado |",
         "|---|---|---:|---|---|"]
    for _, r in mon.iterrows():
        L.append(f"| {r['verificacion']} | {r['estado']} | {r['n_afectados']} | "
                 f"{str(r.get('umbral', 'n/d')).replace('|', '/')} | {str(r['detalle']).replace('|', '/')} |")
    L += ["", "## Qué comprueba cada verificación", "",
          "- **M1 actualización:** que la fuente llegue al último mes de la cobertura configurada y que las "
          "estimaciones cubran el período de pronóstico esperado. Si falta un mes, se alerta para revisar la "
          "carga de datos; no se convierte en cero.",
          "- **M2 calidad:** compara faltantes, duplicados y meses sin información contra la línea base de la "
          "versión aprobada anterior. Los umbrales están en `config/pipeline.yaml`; un aumento mayor al umbral "
          "genera alerta.",
          "- **M3 resultados:** detecta estimaciones negativas, no finitas y variaciones mes a mes o frente a "
          "la versión anterior que superen los umbrales justificados.", "",
          "Una alerta es una señal para revisión: **no demuestra por sí sola pérdida de precisión** ni cambia "
          "automáticamente la versión publicada. El error predictivo (MAE/RMSE) solo se calcula con "
          "observaciones comparables del backtest; no se inventan errores para meses futuros.", "",
          "## Línea base para la próxima ejecución", ""]
    lb = meta.get("linea_base") or {}
    L += [f"- Faltantes: {lb.get('faltantes_pct', 'n/d')} %",
          f"- Duplicados: {lb.get('duplicados_pct', 'n/d')} %",
          f"- Meses sin información: {lb.get('cobertura_meses_faltantes', 'n/d')}",
          f"- Versión anterior: {lb.get('version_anterior') or 'ninguna'}"]
    ruta.write_text("\n".join(L) + "\n", encoding="utf-8")
