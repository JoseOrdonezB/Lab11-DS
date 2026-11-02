"""Pruebas de la sección 5: regla congelada, referencia informativa y publicación.

La regla no exige superar la referencia (5.5). Una serie que no cumple se publica
como referencia (Seasonal Naive), no como estimación ARIMA aprobada.
"""
import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline import modelos, reporte, run
from pipeline.util import cargar_config

RAIZ = Path(__file__).resolve().parent.parent
CFG_PATH = RAIZ / "config" / "pipeline.yaml"
BACKTEST = {"inicio": "2025-07", "fin": "2026-06"}
CFG_REGLA = {"aceptacion": {"regla_congelada": "test", "series_obligatorias": ["Total"],
                            "mae_rel_max": 0.20, "min_obs_evaluacion": 6},
             "periodos": {"backtest": BACKTEST}}
SERIES = {"Total": pd.Series([1000.0] * 12, index=pd.date_range("2025-07-01", "2026-06-01", freq="MS"))}


def _met(mae, n=12, baseline=1.0):
    return pd.DataFrame([{
        "serie": "Total", "modelo": "ARIMA", "periodo_inicio": "2025-07-01", "periodo_fin": "2026-06-01",
        "n_obs": n, "nivel_medio": 1000.0, "MAE": mae, "RMSE": mae, "MAPE_pct": 10.0,
        "MAE_pct_nivel": 100 * mae / 1000.0, "n_excl_mape": 0, "baseline": "Seasonal Naive",
        "baseline_n_obs": 12, "baseline_MAE": baseline, "baseline_RMSE": baseline,
        "baseline_MAE_pct_nivel": 100 * baseline / 1000.0, "run_id": "run-test"}])


def _cfg_pronostico():
    return {
        "destino": "Guatemala", "unidad": "viajeros/mes",
        "periodos": {"pronostico": {"inicio": "2026-01", "fin": "2026-02"}},
        "modelo": {"nombre": "ARIMA", "referencia": "Seasonal Naive",
                   "transformacion_log": {"diferencia_cv_min": 0.25}},
        "series": {"Total": {"arima": [0, 0, 0]}},
    }


# ---- Regla de aceptación ---------------------------------------------------------
def test_mae_en_escala_aprueba_aunque_no_supere_la_referencia():
    out = modelos.regla_aceptacion(_met(mae=100.0, baseline=1.0), SERIES, CFG_REGLA)
    assert bool(out.loc[0, "cumple_regla"])
    assert not bool(out.loc[0, "supera_referencia"])
    assert out.loc[0, "ratio_referencia"] == 100.0
    assert "no supera la referencia" in out.loc[0, "motivo"]


def test_mae_fuera_del_20_por_ciento_rechaza():
    out = modelos.regla_aceptacion(_met(mae=300.0), SERIES, CFG_REGLA)
    assert not bool(out.loc[0, "cumple_regla"])
    assert "> 20%" in out.loc[0, "motivo"]


def test_pocas_observaciones_rechaza_aunque_el_mae_sea_bajo():
    out = modelos.regla_aceptacion(_met(mae=1.0, n=5), SERIES, CFG_REGLA)
    assert not bool(out.loc[0, "cumple_regla"])
    assert "mínimo 6" in out.loc[0, "motivo"]


def test_referencia_no_disponible_no_bloquea_si_el_mae_cumple():
    out = modelos.regla_aceptacion(_met(mae=100.0, baseline=np.nan), SERIES, CFG_REGLA)
    assert bool(out.loc[0, "cumple_regla"])
    assert not bool(out.loc[0, "supera_referencia"])
    assert np.isnan(out.loc[0, "ratio_referencia"])


# ---- Estimaciones publicadas ------------------------------------------------------
def test_serie_no_aprobada_publica_seasonal_naive():
    idx = pd.date_range("2024-01-01", "2025-12-01", freq="MS")
    serie = pd.Series(100.0 + np.arange(len(idx)), index=idx)
    est, params = modelos.pronosticar({"Total": serie}, _cfg_pronostico(), "run", "2026-11-01T00:00:00",
                                      "vtest", {"fuente": "f", "config": "c"}, {"Total": False})
    assert est["estado"].tolist() == ["referencia", "referencia"]
    assert est["modelo"].tolist() == ["Seasonal Naive", "Seasonal Naive"]
    assert est["valor"].tolist() == [serie.loc["2025-01-01"], serie.loc["2025-02-01"]]
    assert params["Total"]["publicado_como"] == "referencia"
    assert params["Total"]["modelo_publicado"] == "Seasonal Naive"


def test_serie_aprobada_publica_arima():
    idx = pd.date_range("2024-01-01", "2025-12-01", freq="MS")
    serie = pd.Series(100.0 + np.arange(len(idx)), index=idx)
    est, params = modelos.pronosticar({"Total": serie}, _cfg_pronostico(), "run", "2026-11-01T00:00:00",
                                      "vtest", {"fuente": "f", "config": "c"}, {"Total": True})
    assert est["estado"].tolist() == ["aprobado", "aprobado"]
    assert all(m.startswith("ARIMA") for m in est["modelo"])
    assert params["Total"]["publicado_como"] == "aprobado"


# ---- Reporte y flujo completo ------------------------------------------------------
def _bt_ene_feb():
    return pd.DataFrame([
        {"serie": "Total", "periodo": pd.Timestamp("2026-01-01"), "real": 300000.0,
         "pred_modelo": 340000.0, "pred_referencia": 290000.0},
        {"serie": "Total", "periodo": pd.Timestamp("2026-02-01"), "real": 240000.0,
         "pred_modelo": 280000.0, "pred_referencia": 250000.0},
    ])


def test_reporte_validacion_incluye_regla_y_ene_feb(tmp_path):
    met = modelos.regla_aceptacion(_met(mae=100.0), SERIES, CFG_REGLA)
    cfg = {"aceptacion": CFG_REGLA["aceptacion"], "periodos": CFG_REGLA["periodos"],
           "modelo": {"referencia": "Seasonal Naive"}}
    ruta = tmp_path / "reporte_validacion.md"
    reporte.generar_validacion(met, _bt_ene_feb(), cfg, ruta, "run-test",
                               {"fuente": "fuente-hash", "config": "config-hash"}, True, [])
    txt = ruta.read_text(encoding="utf-8")
    assert "Regla congelada" in txt
    assert "2026-01" in txt and "2026-02" in txt
    assert "no es un requisito" in txt
    assert "APROBADO" in txt


def _fuente_sintetica():
    filas = []
    for f in pd.date_range("2020-01-01", "2022-12-01", freq="MS"):
        for via, base in (("Aérea", 100.0), ("Terrestre", 50.0), ("Marítima", 10.0)):
            filas.append({"Año": f.year, "Mes cod": f.month, "Vía": via, "Frontera": f"F-{via}",
                          "País": "P", "Región dos": "América Del Centro", "Tipo de Viajero": "Turista",
                          "Viajero": base + f.month})
    return pd.DataFrame(filas)


def test_flujo_publica_version_con_regla_congelada(tmp_path, monkeypatch):
    fuente = tmp_path / "fuente.csv"
    _fuente_sintetica().to_csv(fuente, index=False)

    cfg = copy.deepcopy(cargar_config(CFG_PATH))
    cfg["rutas"] = {"fuente": "fuente.csv", "corridas": "runs", "publicacion": "published"}
    cfg["mlflow"]["habilitado"] = False
    cfg["periodos"] = {"cobertura": {"inicio": "2020-01", "fin": "2022-12"},
                       "ajuste_base": {"inicio": "2020-01", "fin": "2020-12"},
                       "evaluacion_historica": {"inicio": "2021-01", "fin": "2022-12"},
                       "backtest": {"inicio": "2022-01", "fin": "2022-12"},
                       "pronostico": {"inicio": "2023-01", "fin": "2023-06"}}
    cfg["series"] = {"Total": {"arima": [0, 0, 0]}}
    cfg["aceptacion"] = {"regla_congelada": "test", "series_obligatorias": ["Total"],
                         "mae_rel_max": 10.0, "min_obs_evaluacion": 6}
    cfg_path = tmp_path / "config_test.yaml"
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    assert run.main(["--config", str(cfg_path), "--fuente", str(fuente)]) == 0

    pointer = json.loads((tmp_path / "published" / "current.json").read_text(encoding="utf-8"))
    version = pointer["version"]
    vdir = tmp_path / "published" / "versions" / version
    est = pd.read_csv(vdir / "estimaciones.csv")
    met = pd.read_csv(vdir / "metricas.csv")
    manifest = json.loads((vdir / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["aprobado"] is True
    assert set(est["estado"]) == {"aprobado"}
    assert {"nivel_medio", "MAE_pct_nivel", "ratio_referencia", "supera_referencia"} <= set(met.columns)
    assert (vdir / "reporte_validacion.md").exists()
    assert "Regla congelada" in (vdir / "reporte_validacion.md").read_text(encoding="utf-8")
    assert "reporte_validacion.md" in [p.name for p in vdir.iterdir()]
    assert {"monitoreo.csv", "monitoreo.json", "reporte_monitoreo.md"} <= {p.name for p in vdir.iterdir()}
    mon = json.loads((vdir / "monitoreo.json").read_text(encoding="utf-8"))
    assert {v["verificacion"] for v in mon["verificaciones"]} == {"M1 actualización", "M2 calidad", "M3 resultados"}
    assert manifest["monitoreo"]["resultado"] in {"OK", "ALERTA"}
