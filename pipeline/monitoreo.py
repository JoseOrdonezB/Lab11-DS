"""Etapa 12: monitoreo de la ejecución (ejercicio 7).

Tres verificaciones:
  M1 actualización — la fuente y las estimaciones llegan al último período esperado.
  M2 calidad      — cambios relevantes en faltantes, duplicados o cobertura frente a la
                    versión aprobada anterior.
  M3 resultados   — estimaciones negativas/no finitas y variaciones que superan un umbral.

Una alerta es una señal para revisión, no una prueba de pérdida de precisión: no cambia
por sí sola la decisión de publicación ni inventa errores para meses sin observaciones.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd


def _num(x, decimales=4):
    try:
        return round(float(x), decimales) if np.isfinite(float(x)) else None
    except (TypeError, ValueError):
        return None


def _registro(verificacion, estado, n, detalle, umbral=None):
    return {"verificacion": verificacion, "estado": estado, "n_afectados": int(n),
            "detalle": detalle, "umbral": umbral}


def _version_previa(pub_dir):
    """Lee la versión que apunta current.json antes de publicar la nueva."""
    try:
        pub_dir = Path(pub_dir)
        puntero = json.loads((pub_dir / "current.json").read_text(encoding="utf-8"))
        vdir = pub_dir / (puntero.get("ruta") or f"versions/{puntero['version']}")
        mon = (json.loads((vdir / "monitoreo.json").read_text(encoding="utf-8"))
               if (vdir / "monitoreo.json").exists() else None)
        est = (pd.read_csv(vdir / "estimaciones.csv")
               if (vdir / "estimaciones.csv").exists() else None)
        return puntero.get("version"), mon, est
    except Exception:
        return None, None, None


def _m1_actualizacion(df, est, cfg):
    cob = cfg["periodos"]["cobertura"]
    pr = cfg["periodos"]["pronostico"]
    max_meses = int(cfg.get("monitoreo", {}).get("actualizacion", {}).get("desfase_max_meses", 0))
    esperado = pd.Timestamp(cob["fin"] + "-01")
    fuente_fin = pd.to_datetime(df["fecha"], errors="coerce").max()
    pron = est[est["conjunto"] == "pronostico"]
    pron_fin = pd.to_datetime(pron["periodo"], errors="coerce").max()
    pron_esperado = pd.Timestamp(pr["fin"] + "-01")

    problemas = []
    if pd.isna(fuente_fin):
        problemas.append("la fuente no tiene fechas válidas")
        desfase = None
    else:
        desfase = (esperado.to_period("M") - fuente_fin.to_period("M")).n
        if desfase > max_meses:
            problemas.append(f"la fuente llega a {fuente_fin:%Y-%m}, {desfase} mes(es) antes "
                             f"del fin de cobertura {cob['fin']}")
        elif desfase < 0:
            problemas.append(f"la fuente llega a {fuente_fin:%Y-%m}, después del fin de cobertura "
                             f"{cob['fin']}; revise la configuración")
    if pd.isna(pron_fin):
        problemas.append("no hay estimaciones de pronóstico")
    elif pron_fin != pron_esperado:
        problemas.append(f"las estimaciones llegan a {pron_fin:%Y-%m}, se esperaba {pr['fin']}")

    estado = "ALERTA" if problemas else "OK"
    detalle = ("Fuente y estimaciones al día: último mes de la fuente "
               f"{fuente_fin:%Y-%m} y pronóstico hasta {pron_fin:%Y-%m}."
               if not problemas else "; ".join(problemas) + ".")
    return _registro("M1 actualización", estado, len(problemas), detalle,
                     f"desfase máximo {max_meses} mes(es)")


def _m2_calidad(df, ctrl, series, cfg, mon_previo):
    cols = list(cfg["fuente"]["columnas"])
    faltantes = int(df[cols].isna().sum().sum())
    faltantes_pct = 100 * faltantes / max(1, len(df) * len(cols))
    fila_c3 = ctrl[ctrl["control"].str.startswith("C3")]
    duplicados = int(fila_c3["n_afectados"].iloc[0]) if len(fila_c3) else int(df.duplicated(
        cfg["fuente"]["clave_unicidad"], keep=False).sum())
    duplicados_pct = 100 * duplicados / max(1, len(df))
    cobertura = int(sum(int(s.isna().sum()) for s in series.values()))

    actual = {"faltantes_pct": faltantes_pct, "duplicados_pct": duplicados_pct,
              "cobertura_meses_faltantes": cobertura}
    base = (mon_previo or {}).get("linea_base")
    th = cfg.get("monitoreo", {}).get("calidad", {})
    cambios, alertas = [], []
    if not base:
        detalle = (f"Sin versión anterior con línea base. Se registra la actual: "
                   f"{faltantes_pct:.4f} % de celdas faltantes, {duplicados_pct:.4f} % de filas "
                   f"con clave repetida y {cobertura} meses sin información en alguna serie.")
        return _registro("M2 calidad", "OK", 0, detalle, "línea base inicial"), actual, []

    pares = (("faltantes_pct", "faltantes_pct_delta", "puntos de celdas faltantes"),
             ("duplicados_pct", "duplicados_pct_delta", "puntos de filas duplicadas"),
             ("cobertura_meses_faltantes", "cobertura_meses_delta", "meses sin información"))
    for clave, umbral_clave, etiqueta in pares:
        if clave not in base:
            continue
        delta = actual[clave] - float(base[clave])
        umbral = float(th.get(umbral_clave, 0))
        if delta > umbral + 1e-12:
            alertas.append(f"{etiqueta}: +{delta:.4f} (umbral {umbral})")
        elif abs(delta) > 1e-12:
            cambios.append(f"{etiqueta}: {delta:+.4f} (dentro del umbral {umbral})")
    estado = "ALERTA" if alertas else "OK"
    detalle = ("Sin cambios relevantes frente a la versión anterior: "
               f"{faltantes_pct:.4f} % faltantes, {duplicados_pct:.4f} % duplicados, "
               f"{cobertura} meses sin información."
               if not alertas else "Cambios sobre el umbral: " + "; ".join(alertas) + ".")
    if cambios:
        detalle += " Cambios menores registrados: " + "; ".join(cambios) + "."
    return _registro("M2 calidad", estado, len(alertas), detalle,
                     f"faltantes +{th.get('faltantes_pct_delta')} pp, duplicados +{th.get('duplicados_pct_delta')} pp, "
                     f"cobertura +{th.get('cobertura_meses_delta')} meses"), actual, alertas


def _variacion_max(est, columna="valor"):
    """Máxima variación relativa mes a mes por serie en el pronóstico."""
    out = {}
    for serie, g in est[est["conjunto"] == "pronostico"].sort_values("periodo").groupby("serie"):
        v = pd.to_numeric(g[columna], errors="coerce").to_numpy(dtype=float)
        if len(v) < 2:
            continue
        prev, cur = v[:-1], v[1:]
        ok = np.isfinite(prev) & np.isfinite(cur) & (np.abs(prev) > 0)
        if not ok.any():
            continue
        out[str(serie)] = float(np.max(np.abs(cur[ok] - prev[ok]) / np.abs(prev[ok])))
    return out


def _m3_resultados(est, cfg, est_previa):
    valores = pd.to_numeric(est["valor"], errors="coerce")
    negativas = int((valores < 0).sum())
    no_finitas = int((~np.isfinite(valores)).sum())
    th = cfg.get("monitoreo", {}).get("resultados", {})
    th_mensual = float(th.get("variacion_mensual_max", 0.35))
    th_version = float(th.get("variacion_version_max", 0.25))

    var_mensual = _variacion_max(est)
    altas = {s: v for s, v in var_mensual.items() if v > th_mensual}
    var_version, altas_version = {}, {}
    if est_previa is not None and not est_previa.empty:
        a = est[est["conjunto"] == "pronostico"][["serie", "periodo", "valor"]].copy()
        b = est_previa[est_previa["conjunto"] == "pronostico"][["serie", "periodo", "valor"]].copy()
        m = a.merge(b, on=["serie", "periodo"], suffixes=("", "_previa"))
        m = m[np.isfinite(pd.to_numeric(m["valor"], errors="coerce")) &
              np.isfinite(pd.to_numeric(m["valor_previa"], errors="coerce")) &
              (pd.to_numeric(m["valor_previa"], errors="coerce").abs() > 0)]
        for serie, g in m.groupby("serie"):
            prev = pd.to_numeric(g["valor_previa"], errors="coerce").abs().to_numpy(dtype=float)
            cur = pd.to_numeric(g["valor"], errors="coerce").to_numpy(dtype=float)
            var_version[str(serie)] = float(np.max(np.abs(cur - prev) / prev))
        altas_version = {s: v for s, v in var_version.items() if v > th_version}

    problemas = []
    if negativas:
        problemas.append(f"{negativas} estimaciones negativas")
    if no_finitas:
        problemas.append(f"{no_finitas} estimaciones no finitas")
    if altas:
        problemas.append("variación mes a mes sobre el umbral en " +
                         ", ".join(f"{s} {v:.0%}" for s, v in altas.items()))
    if altas_version:
        problemas.append("variación frente a la versión anterior sobre el umbral en " +
                         ", ".join(f"{s} {v:.0%}" for s, v in altas_version.items()))

    max_mensual = max(var_mensual.values()) if var_mensual else None
    max_version = max(var_version.values()) if var_version else None
    if max_mensual is not None:
        detalle = (f"Sin negativas ni valores no finitos. Variación máxima mes a mes: "
                   f"{max_mensual:.1%}. ")
    else:
        detalle = "Sin negativas ni valores no finitos. "
    if max_version is not None:
        detalle += f"Variación máxima frente a la versión anterior: {max_version:.1%}. "
    else:
        detalle += "No hay versiones anteriores comparables. "
    if problemas:
        detalle += "Alertas: " + "; ".join(problemas) + "."
    detalle += (" Una variación alta es una señal para revisión, no una prueba de pérdida de "
                "precisión; el error predictivo solo se actualiza con observaciones comparables.")
    estado = "ALERTA" if problemas else "OK"
    return _registro("M3 resultados", estado, negativas + no_finitas + len(altas) + len(altas_version),
                     detalle, f"variación mensual ≤ {th_mensual:.0%}, frente a versión ≤ {th_version:.0%}"), \
        {"variacion_mensual_max": var_mensual, "variacion_version_max": var_version}


def ejecutar(df, ctrl, series, est, cfg, pub_dir, log=lambda *_: None):
    """Devuelve (tabla de monitoreo, línea base para la próxima versión, alertas)."""
    version_previa, mon_previo, est_previa = _version_previa(pub_dir)
    filas = []
    filas.append(_m1_actualizacion(df, est, cfg))
    m2, linea_base, alertas_m2 = _m2_calidad(df, ctrl, series, cfg, mon_previo)
    filas.append(m2)
    m3, detalle_m3 = _m3_resultados(est, cfg, est_previa)
    filas.append(m3)
    tabla = pd.DataFrame(filas)
    for _, r in tabla.iterrows():
        log(f"{r['verificacion']}: {r['estado']} - {r['detalle']}")
    alertas = tabla[tabla["estado"] == "ALERTA"].to_dict("records")
    linea_base = {**linea_base,
                  "version_anterior": version_previa,
                  "variaciones": detalle_m3,
                  "estimaciones": {s: {pd.Timestamp(p).strftime("%Y-%m"): _num(v, 2)
                                       for p, v in zip(g["periodo"], g["valor"])}
                                   for s, g in est[est["conjunto"] == "pronostico"].groupby("serie")}}
    return tabla, linea_base, alertas
