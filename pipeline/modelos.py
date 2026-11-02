"""Etapas 4, 5 y 7: ajuste (ARIMA con los órdenes del Lab 1), referencia Seasonal Naive,
backtest de origen expansivo (un paso adelante) y pronóstico."""
import warnings
import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA


def usar_log(train, cfg):
    """Regla de transformación logarítmica del Lab 1, calculada solo con el tramo de ajuste."""
    obs = train.dropna()
    if obs.empty or not (obs > 0).all():
        return False
    cv = obs.groupby(obs.index.year).apply(lambda x: x.std() / x.mean() if len(x) > 1 and x.mean() else np.nan).dropna()
    if cv.empty:
        return False
    return bool((cv.max() - cv.min()) > cfg["modelo"]["transformacion_log"]["diferencia_cv_min"])


def ajustar_pronosticar(train, orden, pasos, cfg, devolver_ajuste=False):
    """Ajusta ARIMA con la información de `train` (puede tener NaN) y pronostica `pasos` meses.
    Con devolver_ajuste=True también devuelve los coeficientes estimados (para guardarlos en MLflow)."""
    log = usar_log(train, cfg)
    y = np.log(train) if log else train
    with warnings.catch_warnings(record=True) as avisos:
        warnings.simplefilter("always")
        fit = ARIMA(y, order=tuple(orden)).fit()
        p = np.asarray(fit.forecast(pasos), dtype=float)
    p = np.exp(p) if log else p
    convergio = not any("converge" in str(a.message).lower() for a in avisos)
    if devolver_ajuste:
        ajuste = {"coeficientes": {k: float(v) for k, v in fit.params.items()},
                  "aic": float(fit.aic), "bic": float(fit.bic), "n_obs_usadas": int(train.notna().sum()),
                  "ultimo_mes_ajuste": train.index.max().strftime("%Y-%m")}
        return p, log, convergio, ajuste
    return p, log, convergio


def seasonal_naive(serie, fecha):
    """Mismo mes del año anterior. NaN si ese mes no tiene dato (no se inventa)."""
    ref = fecha - pd.DateOffset(years=1)
    return float(serie.get(ref, np.nan))


def metricas(real, pred):
    real, pred = np.asarray(real, float), np.asarray(pred, float)
    ok = np.isfinite(real) & np.isfinite(pred)
    n = int(ok.sum())
    if n == 0:
        return {"n_obs": 0, "MAE": np.nan, "RMSE": np.nan, "MAPE_pct": np.nan, "n_excl_mape": 0}
    e = real[ok] - pred[ok]
    pos = real[ok] > 0
    mape = float(np.mean(np.abs(e[pos] / real[ok][pos])) * 100) if pos.any() else np.nan
    return {"n_obs": n, "MAE": float(np.mean(np.abs(e))), "RMSE": float(np.sqrt(np.mean(e ** 2))),
            "MAPE_pct": mape, "n_excl_mape": int((~pos).sum())}


def backtest(series, cfg, log):
    """Para cada corte c del período de backtest, ajusta solo con meses < c y estima c."""
    bt = cfg["periodos"]["backtest"]
    cortes = pd.date_range(bt["inicio"] + "-01", bt["fin"] + "-01", freq="MS")
    filas, avisos = [], []
    for nombre, s in series.items():
        orden = cfg["series"][nombre]["arima"]
        for c in cortes:
            train = s[s.index < c]
            p, uso_log, conv = ajustar_pronosticar(train, orden, 1, cfg)
            if not conv:
                avisos.append(f"{nombre} {c:%Y-%m}: ARIMA{tuple(orden)} no convergió")
            filas.append({"serie": nombre, "periodo": c, "real": s.get(c, np.nan), "pred_modelo": float(p[0]),
                          "pred_referencia": seasonal_naive(train, c), "log": uso_log})
        log(f"backtest {nombre}: {len(cortes)} cortes")
    por_serie = {}
    for a in avisos:
        por_serie.setdefault(a.split(" 20")[0], []).append(a)
    for n, lst in por_serie.items():
        log(f"WARN {n}: ARIMA no convergió en {len(lst)} de {len(cortes)} cortes (se usó el último ajuste de la optimización)")
    return pd.DataFrame(filas), avisos


def tabla_metricas(bt, cfg, run_id):
    bti, btf = cfg["periodos"]["backtest"]["inicio"] + "-01", cfg["periodos"]["backtest"]["fin"] + "-01"
    filas = []
    for nombre, g in bt.groupby("serie", sort=False):
        m = metricas(g["real"], g["pred_modelo"])
        b = metricas(g["real"], g["pred_referencia"])
        nivel = float(g["real"].mean())
        filas.append({"serie": nombre, "modelo": cfg["modelo"]["nombre"], "periodo_inicio": bti, "periodo_fin": btf,
                      "n_obs": m["n_obs"], "nivel_medio": nivel,
                      "MAE": m["MAE"], "RMSE": m["RMSE"], "MAPE_pct": m["MAPE_pct"],
                      "MAE_pct_nivel": (100 * m["MAE"] / nivel) if np.isfinite(nivel) and nivel > 0 else np.nan,
                      "n_excl_mape": m["n_excl_mape"], "baseline": cfg["modelo"]["referencia"],
                      "baseline_n_obs": b["n_obs"], "baseline_MAE": b["MAE"], "baseline_RMSE": b["RMSE"],
                      "baseline_MAE_pct_nivel": (100 * b["MAE"] / nivel) if np.isfinite(nivel) and nivel > 0 else np.nan,
                      "run_id": run_id})
    return pd.DataFrame(filas)


def regla_aceptacion(met, series, cfg):
    """Aplica la regla congelada de la sección 5.

    Una serie cumple si tiene suficientes observaciones comparables y su MAE no supera
    `mae_rel_max` del nivel medio observado en el backtest. La referencia se reporta,
    pero no es un requisito: el laboratorio no exige superarla (5.5).
    """
    a = cfg["aceptacion"]
    bt = cfg["periodos"]["backtest"]
    idx = pd.date_range(bt["inicio"] + "-01", bt["fin"] + "-01", freq="MS")
    met = met.copy()
    cumple, motivos, ratios, pcts, supera, niveles = [], [], [], [], [], []
    for _, f in met.iterrows():
        nivel = float(f.get("nivel_medio", np.nan))
        if not np.isfinite(nivel) or nivel <= 0:
            nivel = float(series[f["serie"]].reindex(idx).mean())
        niveles.append(nivel)
        pct = (100 * f["MAE"] / nivel) if np.isfinite(nivel) and nivel > 0 else np.nan
        baseline = f.get("baseline_MAE", np.nan)
        ratio = (f["MAE"] / baseline) if np.isfinite(baseline) and baseline > 0 else np.nan
        supera_ref = bool(np.isfinite(ratio) and ratio <= 1.0)

        if f["n_obs"] < a["min_obs_evaluacion"]:
            ok = False
            motivo = (f"solo {f['n_obs']} observaciones comparables "
                      f"(mínimo {a['min_obs_evaluacion']}); no se aprueba por desempeño")
        else:
            ok = bool(np.isfinite(pct) and pct <= 100 * a["mae_rel_max"])
            if ok:
                motivo = "cumple"
                if np.isfinite(ratio) and ratio > 1:
                    motivo += f"; no supera la referencia ({ratio:.2f}x), se reporta sin bloquear"
            else:
                motivo = f"MAE {f['MAE']:.0f} > {a['mae_rel_max']:.0%} del nivel medio ({nivel:.0f})"

        cumple.append(ok); motivos.append(motivo); ratios.append(ratio); pcts.append(pct); supera.append(supera_ref)

    met["nivel_medio"] = niveles
    met["MAE_pct_nivel"] = pcts
    met["ratio_referencia"] = ratios
    met["supera_referencia"] = supera
    met["cumple_regla"] = cumple
    met["motivo"] = motivos
    return met


def pronosticar(series, cfg, run_id, ts, version, hashes, cumple=None):
    """Etapa 7: estima el período publicado.

    Las series que cumplen la regla se publican con ARIMA y estado "aprobado".
    Las que no cumplen se publican con la referencia Seasonal Naive y estado "referencia",
    para no presentar como aprobado un modelo que no pasó la validación.
    """
    pr = cfg["periodos"]["pronostico"]
    fechas = pd.date_range(pr["inicio"] + "-01", pr["fin"] + "-01", freq="MS")
    cumple = cumple or {}
    filas, parametros = [], {}
    for nombre, s in series.items():
        aprobada = bool(cumple.get(nombre, True))
        p, uso_log, conv, ajuste = ajustar_pronosticar(s, cfg["series"][nombre]["arima"], len(fechas), cfg, devolver_ajuste=True)
        modelo_arima = f"{cfg['modelo']['nombre']}{tuple(cfg['series'][nombre]['arima'])}"
        modelo_publicado = modelo_arima if aprobada else cfg["modelo"]["referencia"]
        valores = p if aprobada else np.array([seasonal_naive(s, f) for f in fechas], dtype=float)
        estado = "aprobado" if aprobada else "referencia"
        parametros[nombre] = {"modelo": cfg["modelo"]["nombre"], "orden": list(cfg["series"][nombre]["arima"]),
                              "transformacion_log": uso_log, "convergio": conv,
                              "publicado_como": estado, "modelo_publicado": modelo_publicado, **ajuste}
        for h, (f, v) in enumerate(zip(fechas, valores), start=1):
            filas.append({"destino": cfg["destino"], "serie": nombre, "periodo": f.strftime("%Y-%m-%d"),
                          "valor": float(v) if np.isfinite(v) else np.nan,
                          "unidad": cfg["unidad"], "modelo": modelo_publicado,
                          "conjunto": "pronostico", "horizonte": h, "run_id": run_id, "fecha_generacion": ts,
                          "version_procedimiento": version, "fuente_hash": hashes["fuente"],
                          "config_hash": hashes["config"], "estado": estado})
    return pd.DataFrame(filas), parametros
