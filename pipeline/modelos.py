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
        filas.append({"serie": nombre, "modelo": cfg["modelo"]["nombre"], "periodo_inicio": bti, "periodo_fin": btf,
                      "n_obs": m["n_obs"], "MAE": m["MAE"], "RMSE": m["RMSE"], "MAPE_pct": m["MAPE_pct"],
                      "n_excl_mape": m["n_excl_mape"], "baseline": cfg["modelo"]["referencia"],
                      "baseline_n_obs": b["n_obs"], "baseline_MAE": b["MAE"], "baseline_RMSE": b["RMSE"], "run_id": run_id})
    return pd.DataFrame(filas)


def regla_aceptacion(met, series, cfg):
    """Marca cumple_regla por serie. Sin observaciones comparables no se aprueba por desempeño."""
    a = cfg["aceptacion"]
    bt = cfg["periodos"]["backtest"]
    idx = pd.date_range(bt["inicio"] + "-01", bt["fin"] + "-01", freq="MS")
    cumple, motivos = [], []
    for _, f in met.iterrows():
        nivel = series[f["serie"]].reindex(idx).mean()
        if f["n_obs"] < a["min_obs_evaluacion"]:
            cumple.append(False); motivos.append(f"solo {f['n_obs']} observaciones comparables (mínimo {a['min_obs_evaluacion']}); no se aprueba por desempeño")
            continue
        c1 = f["MAE"] <= a["mae_rel_max"] * nivel
        c2 = (not np.isfinite(f["baseline_MAE"])) or f["MAE"] <= a["margen_vs_referencia"] * f["baseline_MAE"]
        cumple.append(bool(c1 and c2))
        motivos.append("cumple" if (c1 and c2) else
                       "; ".join(x for x in (
                           (f"MAE {f['MAE']:.0f} > {a['mae_rel_max']:.0%} del nivel medio ({nivel:.0f})" if not c1 else ""),
                           (f"MAE {f['MAE']:.0f} > {a['margen_vs_referencia']} x MAE de la referencia ({f['baseline_MAE']:.0f})" if not c2 else "")) if x))
    met = met.copy()
    met["cumple_regla"] = cumple
    met["motivo"] = motivos
    return met


def pronosticar(series, cfg, run_id, ts, version, hashes):
    """Etapa 7: ajusta con todo el histórico hasta el corte y estima el período publicado."""
    pr = cfg["periodos"]["pronostico"]
    fechas = pd.date_range(pr["inicio"] + "-01", pr["fin"] + "-01", freq="MS")
    filas, parametros = [], {}
    for nombre, s in series.items():
        p, uso_log, conv, ajuste = ajustar_pronosticar(s, cfg["series"][nombre]["arima"], len(fechas), cfg, devolver_ajuste=True)
        parametros[nombre] = {"modelo": cfg["modelo"]["nombre"], "orden": list(cfg["series"][nombre]["arima"]),
                              "transformacion_log": uso_log, "convergio": conv, **ajuste}
        for h, (f, v) in enumerate(zip(fechas, p), start=1):
            filas.append({"destino": cfg["destino"], "serie": nombre, "periodo": f.strftime("%Y-%m-%d"), "valor": float(v),
                          "unidad": cfg["unidad"], "modelo": f"{cfg['modelo']['nombre']}{tuple(cfg['series'][nombre]['arima'])}",
                          "conjunto": "pronostico", "horizonte": h, "run_id": run_id, "fecha_generacion": ts,
                          "version_procedimiento": version, "fuente_hash": hashes["fuente"], "config_hash": hashes["config"]})
    return pd.DataFrame(filas), parametros
