"""Pruebas de las tres verificaciones de monitoreo (ejercicio 7).

Usan datos sintéticos: no dependen del dato institucional.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline import monitoreo, reporte

CFG = {
    "fuente": {
        "columnas": {"Año": "entero", "Mes cod": "entero", "Vía": "texto", "Frontera": "texto",
                     "País": "texto", "Región dos": "texto", "Tipo de Viajero": "texto", "Viajero": "numerico"},
        "clave_unicidad": ["Año", "Mes cod", "Vía", "Frontera", "País", "Región dos", "Tipo de Viajero"],
    },
    "periodos": {"cobertura": {"inicio": "2025-01", "fin": "2025-06"},
                 "pronostico": {"inicio": "2025-07", "fin": "2025-12"}},
    "monitoreo": {"actualizacion": {"desfase_max_meses": 0},
                  "calidad": {"faltantes_pct_delta": 0.5, "duplicados_pct_delta": 0.1,
                              "cobertura_meses_delta": 0},
                  "resultados": {"variacion_mensual_max": 0.35, "variacion_version_max": 0.25}},
}


def _fuente(hasta="2025-06", nulos=0):
    filas = []
    for f in pd.date_range("2025-01-01", pd.Timestamp(hasta + "-01"), freq="MS"):
        for _ in range(3):
            filas.append({"Año": f.year, "Mes cod": f.month, "fecha": f, "Vía": "Aérea", "Frontera": "F",
                          "País": "P", "Región dos": "R", "Tipo de Viajero": "Turista", "Viajero": 100.0})
    df = pd.DataFrame(filas)
    if nulos:
        df.loc[df.index[:nulos], "País"] = None
    return df


def _series():
    idx = pd.date_range("2025-01-01", "2025-06-01", freq="MS")
    return {"Total": pd.Series(100.0, index=idx)}


def _est(valores=(100.0, 101.0, 102.0, 103.0, 104.0, 105.0)):
    return pd.DataFrame([{"serie": "Total", "periodo": f"2025-{m:02d}-01", "valor": v,
                          "conjunto": "pronostico"} for m, v in zip(range(7, 13), valores)])


def _ctrl(n=0):
    return pd.DataFrame([{"control": "C3 unicidad", "severidad": "critico", "estado": "OK",
                          "n_afectados": n, "detalle": ""}])


def _pub_con_linea_base(tmp_path, **linea):
    base = {"faltantes_pct": 0.0, "duplicados_pct": 0.0, "cobertura_meses_faltantes": 0}
    base.update(linea)
    (tmp_path / "versions" / "v0").mkdir(parents=True)
    (tmp_path / "versions" / "v0" / "monitoreo.json").write_text(
        json.dumps({"linea_base": base}), encoding="utf-8")
    (tmp_path / "current.json").write_text(json.dumps({"version": "v0", "ruta": "versions/v0"}),
                                           encoding="utf-8")


def _fila(tabla, prefijo):
    return tabla[tabla["verificacion"].str.startswith(prefijo)].iloc[0]


def test_m1_ok_cuando_fuente_y_pronostico_estan_al_dia():
    tabla, _, _ = monitoreo.ejecutar(_fuente(), _ctrl(), _series(), _est(), CFG, "/no/existe")
    assert _fila(tabla, "M1")["estado"] == "OK"


def test_m1_alerta_si_la_fuente_no_llega_al_ultimo_mes():
    tabla, _, alertas = monitoreo.ejecutar(_fuente("2025-05"), _ctrl(), _series(), _est(), CFG, "/no/existe")
    assert _fila(tabla, "M1")["estado"] == "ALERTA"
    assert any("M1" in a["verificacion"] for a in alertas)


def test_m1_alerta_si_el_pronostico_no_cubre_el_periodo_configurado():
    est = _est().iloc[:-1]                      # pierde diciembre
    tabla, _, _ = monitoreo.ejecutar(_fuente(), _ctrl(), _series(), est, CFG, "/no/existe")
    assert _fila(tabla, "M1")["estado"] == "ALERTA"
    assert "2025-12" in _fila(tabla, "M1")["detalle"]


def test_m2_sin_version_previa_crea_linea_base_sin_alerta():
    tabla, linea, _ = monitoreo.ejecutar(_fuente(), _ctrl(), _series(), _est(), CFG, "/no/existe")
    assert _fila(tabla, "M2")["estado"] == "OK"
    assert linea["faltantes_pct"] == 0.0
    assert linea["estimaciones"]["Total"]["2025-07"] == 100.0


def test_m2_alerta_por_aumento_de_faltantes(tmp_path):
    _pub_con_linea_base(tmp_path, faltantes_pct=0.0)
    tabla, _, _ = monitoreo.ejecutar(_fuente(nulos=5), _ctrl(), _series(), _est(), CFG, tmp_path)
    assert _fila(tabla, "M2")["estado"] == "ALERTA"
    assert "faltantes" in _fila(tabla, "M2")["detalle"]


def test_m2_alerta_por_aumento_de_duplicados(tmp_path):
    _pub_con_linea_base(tmp_path, duplicados_pct=0.0)
    tabla, _, _ = monitoreo.ejecutar(_fuente(), _ctrl(n=4), _series(), _est(), CFG, tmp_path)
    assert _fila(tabla, "M2")["estado"] == "ALERTA"
    assert "duplicadas" in _fila(tabla, "M2")["detalle"]


def test_m3_ok_con_estimaciones_estables():
    tabla, detalle, _ = monitoreo.ejecutar(_fuente(), _ctrl(), _series(), _est(), CFG, "/no/existe")
    assert _fila(tabla, "M3")["estado"] == "OK"
    assert detalle["variaciones"]["variacion_mensual_max"]["Total"] < 0.35


def test_m3_alerta_por_estimacion_negativa():
    tabla, _, _ = monitoreo.ejecutar(_fuente(), _ctrl(), _series(), _est((100, 100, -1, 100, 100, 100)),
                                     CFG, "/no/existe")
    assert _fila(tabla, "M3")["estado"] == "ALERTA"
    assert "negativas" in _fila(tabla, "M3")["detalle"]


def test_m3_alerta_por_estimacion_no_finita():
    tabla, _, _ = monitoreo.ejecutar(_fuente(), _ctrl(), _series(), _est((100, 100, np.nan, 100, 100, 100)),
                                     CFG, "/no/existe")
    assert _fila(tabla, "M3")["estado"] == "ALERTA"
    assert "no finitas" in _fila(tabla, "M3")["detalle"]


def test_m3_alerta_por_variacion_mensual_sobre_umbral():
    tabla, detalle, _ = monitoreo.ejecutar(_fuente(), _ctrl(), _series(), _est((100, 200, 100, 200, 100, 200)),
                                           CFG, "/no/existe")
    assert _fila(tabla, "M3")["estado"] == "ALERTA"
    assert detalle["variaciones"]["variacion_mensual_max"]["Total"] > 0.35
    assert "mes a mes" in _fila(tabla, "M3")["detalle"]


def test_reporte_monitoreo_explica_alertas_y_limites(tmp_path):
    tabla, linea, _ = monitoreo.ejecutar(_fuente(), _ctrl(), _series(), _est(), CFG, "/no/existe")
    ruta = tmp_path / "reporte_monitoreo.md"
    reporte.generar_monitoreo(tabla, {"run_id": "run-test", "version": "vtest", "linea_base": linea}, ruta)
    txt = ruta.read_text(encoding="utf-8")
    assert "M1 actualización" in txt
    assert "M2 calidad" in txt
    assert "M3 resultados" in txt
    assert "no demuestra" in txt
