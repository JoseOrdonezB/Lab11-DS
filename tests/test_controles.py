"""Pruebas de los seis controles de calidad y de la detención del pipeline.
Usan datos sintéticos: no dependen del dato institucional. Correr con:  python -m pytest tests -q"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pipeline import controles, run
from pipeline.preparar import meses
from pipeline.util import cargar_config

RAIZ = Path(__file__).resolve().parent.parent
CFG_PATH = RAIZ / "config" / "pipeline.yaml"


@pytest.fixture(scope="module")
def cfg():
    return cargar_config(CFG_PATH)


@pytest.fixture()
def base(cfg):
    """Una fila por mes, vía y región, con toda la cobertura configurada (todos los controles en OK)."""
    cob = cfg["periodos"]["cobertura"]
    filas = []
    for f in meses(cob["inicio"], cob["fin"]):
        for via in ("Aérea", "Terrestre", "Marítima"):
            for reg in ("América Del Centro", "América Del Norte", "Europa"):
                filas.append({"Año": f.year, "Mes cod": f.month, "Vía": via, "Frontera": f"F-{via}", "País": f"P-{reg}",
                              "Región dos": reg, "Tipo de Viajero": "Turista", "Viajero": 100.0 + f.month})
    return pd.DataFrame(filas)


def estados(df, cfg):
    ctrl, _, _ = controles.ejecutar(df, cfg, lambda m: None)
    return dict(zip(ctrl["control"].str.split().str[0], ctrl["estado"]))


def test_base_limpia_todo_ok(base, cfg):
    assert set(estados(base, cfg).values()) == {"OK"}


# C1
def test_c1_falta_columna_detiene_y_omite_el_resto(base, cfg):
    e = estados(base.drop(columns=["Región dos"]), cfg)
    assert e["C1"] == "FAIL"
    assert all(e[c] == "OMITIDO" for c in ("C2", "C3", "C4", "C5", "C6"))


def test_c1_tipo_incompatible(base, cfg):
    base["Viajero"] = base["Viajero"].astype(str)
    assert estados(base, cfg)["C1"] == "FAIL"


# C2
def test_c2_fecha_invalida(base, cfg):
    base.loc[base.index[:3], "Mes cod"] = 13
    assert estados(base, cfg)["C2"] == "FAIL"


def test_c2_mes_sin_informacion_en_total_detiene(base, cfg):
    sin = base[~((base["Año"] == 2024) & (base["Mes cod"] == 5))]
    assert estados(sin, cfg)["C2"] == "FAIL"


def test_c2_mes_faltante_en_un_segmento_es_advertencia_y_no_se_vuelve_cero(base, cfg):
    sin = base[~((base["Año"] == 2024) & (base["Mes cod"] == 5) & (base["Región dos"] == "Europa"))]
    ctrl, df_ok, series = controles.ejecutar(sin, cfg, lambda m: None)
    assert ctrl.loc[1, "estado"] == "WARN"
    assert np.isnan(series["Europa"][pd.Timestamp("2024-05-01")])     # NaN, no 0


# C3
def test_c3_pocos_duplicados_advierte(base, cfg):
    assert estados(pd.concat([base, base.iloc[[0]]]), cfg)["C3"] == "WARN"


def test_c3_muchos_duplicados_detiene(base, cfg):
    assert estados(pd.concat([base, base.sample(100, random_state=0)]), cfg)["C3"] == "FAIL"


# C4
def test_c4_nulo_permitido_advierte(base, cfg):
    base.loc[base.index[:5], "País"] = None
    assert estados(base, cfg)["C4"] == "WARN"


def test_c4_nulo_que_impide_estimar_detiene(base, cfg):
    base.loc[base.index[:5], "Región dos"] = None
    assert estados(base, cfg)["C4"] == "FAIL"


# C5
def test_c5_negativos_detienen(base, cfg):
    base.loc[base.index[0], "Viajero"] = -1
    assert estados(base, cfg)["C5"] == "FAIL"


def test_c5_no_finitos_detienen(base, cfg):
    base.loc[base.index[0], "Viajero"] = np.inf
    assert estados(base, cfg)["C5"] == "FAIL"


def test_c5_cero_en_backtest_advierte(base, cfg):
    m = (base["Año"] == 2026) & (base["Mes cod"] == 1) & (base["Región dos"] == "Europa")
    base.loc[m, "Viajero"] = 0.0
    assert estados(base, cfg)["C5"] == "WARN"


# C6
def test_c6_columna_diaria_detiene(base, cfg):
    base["Día"] = 1
    assert estados(base, cfg)["C6"] == "FAIL"


def test_c6_tipo_de_viajero_desconocido_detiene(base, cfg):
    base.loc[base.index[:2], "Tipo de Viajero"] = "Desconocido"
    assert estados(base, cfg)["C6"] == "FAIL"


# Pipeline: un control crítico detiene antes de tocar lo publicado
def test_pipeline_se_detiene_y_conserva_lo_publicado(base, tmp_path, monkeypatch):
    pub = tmp_path / "published"
    (pub / "versions" / "v0").mkdir(parents=True)
    actual = pub / "current.json"
    actual.write_text(json.dumps({"version": "v0"}), encoding="utf-8")
    antes = actual.read_text(encoding="utf-8")

    malo = tmp_path / "fuente_mala.csv"
    base.drop(columns=["País"]).to_csv(malo, index=False)          # falta una columna indispensable
    monkeypatch.chdir(tmp_path)

    assert run.main(["--config", str(CFG_PATH), "--fuente", str(malo)]) == 2
    assert actual.read_text(encoding="utf-8") == antes
    assert [p.name for p in (pub / "versions").iterdir()] == ["v0"]

    corrida = next((tmp_path / "runs").iterdir())
    assert (corrida / "controles.csv").exists()
    assert "DETENIDO" in (corrida / "reporte_controles.md").read_text(encoding="utf-8")
    resumen = json.loads((corrida / "run_summary.json").read_text(encoding="utf-8"))
    assert resumen["codigo_salida"] == 2 and "2_validacion" in resumen["etapas_completadas"]
