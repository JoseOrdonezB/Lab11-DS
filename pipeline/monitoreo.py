"""Etapa de monitoreo (ejercicio 7.2): tres verificaciones sobre cada ejecucion.
No deciden si se publica (eso ya lo hace la autorizacion, etapa 9): generan alertas para
revision humana y quedan registradas junto con el candidato. Una variacion alta es una
alerta, no una prueba de perdida de precision (7.3)."""
import numpy as np
import pandas as pd
from pathlib import Path


def _res(verificacion, estado, detalle):
    return {"verificacion": verificacion, "estado": estado, "detalle": detalle}


def v_actualizacion(df, cfg, series):
    """La fuente y la serie Total deben llegar hasta el ultimo mes de la cobertura configurada."""
    cob = cfg["periodos"]["cobertura"]
    esperado = pd.Timestamp(cob["fin"] + "-01")
    ultimo_fuente = df["fecha"].max()
    tot = series.get("Total")
    ultimo_total = tot.dropna().index.max() if tot is not None and tot.notna().any() else pd.NaT
    if pd.isna(ultimo_fuente) or ultimo_fuente < esperado:
        detalle = "sin fechas validas" if pd.isna(ultimo_fuente) else f"{ultimo_fuente:%Y-%m}"
        return _res("Actualizacion", "ALERTA",
                    f"La fuente llega hasta {detalle}, antes del ultimo mes de la cobertura configurada ({esperado:%Y-%m}).")
    if pd.isna(ultimo_total) or ultimo_total < esperado:
        detalle = "sin dato" if pd.isna(ultimo_total) else f"{ultimo_total:%Y-%m}"
        return _res("Actualizacion", "ALERTA",
                    f"La serie Total tiene dato hasta {detalle}, antes del ultimo mes esperado ({esperado:%Y-%m}).")
    return _res("Actualizacion", "OK",
                f"Fuente y serie Total cubren hasta {esperado:%Y-%m}, el ultimo mes de la cobertura configurada.")


def v_calidad(ctrl, ctrl_anterior):
    """Compara faltantes, duplicados y cobertura contra la version vigente publicada."""
    if ctrl_anterior is None:
        return _res("Calidad", "OK", "No hay version publicada previa para comparar; esta corrida queda como linea base.")
    relevantes = ["C2 fechas y cobertura", "C3 unicidad", "C4 valores faltantes"]
    cur = ctrl.set_index("control")["n_afectados"]
    prev = ctrl_anterior.set_index("control")["n_afectados"]
    cambios = []
    for c in relevantes:
        n_cur, n_prev = int(cur.get(c, 0)), int(prev.get(c, 0))
        if n_prev == 0 and n_cur > 0:
            cambios.append(f"{c}: 0 -> {n_cur} afectados")
        elif n_prev and (n_cur - n_prev) / n_prev > 0.5:
            cambios.append(f"{c}: {n_prev} -> {n_cur} afectados ({(n_cur - n_prev) / n_prev:+.0%})")
    if cambios:
        return _res("Calidad", "ALERTA", "Aumentos relevantes respecto a la version vigente: " + "; ".join(cambios) + ".")
    return _res("Calidad", "OK", "Sin cambios relevantes en faltantes, duplicados o cobertura respecto a la version vigente.")


def v_resultados(est, est_anterior, cfg):
    """Detecta negativos/no finitos, o variaciones grandes de pronostico contra la version vigente."""
    problemas = []
    if not np.isfinite(est["valor"]).all():
        problemas.append("hay valores no finitos")
    if (est["valor"] < 0).any():
        problemas.append("hay valores negativos")
    if problemas:
        return _res("Resultados", "ALERTA", "; ".join(problemas) + ".")
    if est_anterior is None:
        return _res("Resultados", "OK", "Sin valores negativos ni no finitos. No hay version previa para comparar variacion.")
    umbral = cfg["umbrales"].get("variacion_pct_alerta", 0.30)
    pron = est[est["conjunto"] == "pronostico"]
    pron_prev = est_anterior[est_anterior["conjunto"] == "pronostico"]
    m = pron.merge(pron_prev, on=["serie", "periodo"], suffixes=("_nuevo", "_prev"))
    if m.empty:
        return _res("Resultados", "OK",
                    "Sin valores negativos ni no finitos. Sin periodos de pronostico en comun con la version vigente para comparar variacion.")
    m["variacion"] = (m["valor_nuevo"] - m["valor_prev"]).abs() / m["valor_prev"].replace(0, np.nan)
    altas = m.dropna(subset=["variacion"]).query("variacion > @umbral")
    if len(altas):
        peor = altas.sort_values("variacion", ascending=False).iloc[0]
        serie_peor, periodo_peor, variacion_peor = peor["serie"], peor["periodo"], peor["variacion"]
        return _res("Resultados", "ALERTA",
                    f"{len(altas)} estimaciones de pronostico varian mas de {umbral:.0%} respecto a la version vigente "
                    f"(mayor: {serie_peor} {periodo_peor}, {variacion_peor:.0%}). Revisar antes de confiar en la nueva version; "
                    "una variacion alta no demuestra por si sola una perdida de precision.")
    return _res("Resultados", "OK",
                f"Sin valores negativos ni no finitos, y ninguna estimacion de pronostico varia mas de {umbral:.0%} respecto a la version vigente.")


def ejecutar(df, cfg, series, ctrl, est, pub_dir, log):
    """Corre las tres verificaciones comparando contra la version vigente en pub_dir (si existe)."""
    from .publicar import leer_puntero
    ctrl_anterior = est_anterior = None
    previo = leer_puntero(pub_dir)
    if previo:
        vdir = Path(pub_dir) / "versions" / previo["version"]
        try:
            ctrl_anterior = pd.read_csv(vdir / "controles.csv")
            est_anterior = pd.read_csv(vdir / "estimaciones.csv")
        except FileNotFoundError:
            pass
    resultados = [v_actualizacion(df, cfg, series), v_calidad(ctrl, ctrl_anterior), v_resultados(est, est_anterior, cfg)]
    for r in resultados:
        log("Monitoreo " + r["verificacion"] + ": " + r["estado"] + " - " + r["detalle"])
    return pd.DataFrame(resultados)
