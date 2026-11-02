"""Pruebas de la lectura de la versión publicada por el tablero (ejercicio 6).

El tablero no debe fallar ni inventar valores: si no hay versión aprobada devuelve None y
la interfaz muestra «estimaciones no disponibles». La restauración cambia solo el puntero.
"""
import json
import sys
from pathlib import Path

import pandas as pd

from pipeline import publicar

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
from publicacion import cargar_publicacion, estado_por_serie, series_publicadas  # noqa: E402


def _version(pub, version, aprobado=True, valor=100.0):
    vdir = pub / "versions" / version
    vdir.mkdir(parents=True)
    (vdir / "manifest.json").write_text(json.dumps({
        "version_procedimiento": version, "run_id": f"run-{version}", "mlflow_run_id": "mlf-1",
        "aprobado": aprobado, "aprobado_en": "2026-11-01T10:00:00",
        "fuente_hash": "a" * 64, "config_hash": "b" * 64,
    }), encoding="utf-8")
    pd.DataFrame([{
        "serie": "Total", "n_obs": 12, "MAE": 10.0, "MAE_pct_nivel": 10.0, "baseline_MAE": 12.0,
        "ratio_referencia": 0.83, "cumple_regla": True, "periodo_inicio": "2025-07-01",
        "periodo_fin": "2026-06-01",
    }, {
        "serie": "Vía Marítima", "n_obs": 12, "MAE": 30.0, "MAE_pct_nivel": 90.0, "baseline_MAE": 5.0,
        "ratio_referencia": 6.0, "cumple_regla": False, "periodo_inicio": "2025-07-01",
        "periodo_fin": "2026-06-01",
    }]).to_csv(vdir / "metricas.csv", index=False)
    pd.DataFrame([
        {"destino": "Guatemala", "serie": "Total", "periodo": "2026-07-01", "valor": valor,
         "unidad": "viajeros/mes", "modelo": "ARIMA(1, 0, 1)", "conjunto": "pronostico", "estado": "aprobado"},
        {"destino": "Guatemala", "serie": "Vía Marítima", "periodo": "2026-07-01", "valor": 5.0,
         "unidad": "viajeros/mes", "modelo": "Seasonal Naive", "conjunto": "pronostico", "estado": "referencia"},
    ]).to_csv(vdir / "estimaciones.csv", index=False)
    (vdir / "reporte_validacion.md").write_text("# Reporte\n", encoding="utf-8")
    return vdir


def _puntero(pub, version, anterior=None):
    (pub / "current.json").write_text(json.dumps({
        "version": version, "ruta": f"versions/{version}", "aprobado_en": "2026-11-01T10:00:00",
        "run_id": f"run-{version}", "version_anterior": anterior,
    }), encoding="utf-8")


def test_sin_version_publicada_devuelve_no_disponible(tmp_path):
    pub, error = cargar_publicacion(tmp_path)
    assert pub is None
    assert "current.json" in error


def test_version_incompleta_o_no_aprobada_no_se_muestra(tmp_path):
    _version(tmp_path, "v1", aprobado=False)
    _puntero(tmp_path, "v1")
    pub, error = cargar_publicacion(tmp_path)
    assert pub is None and "no está aprobada" in error

    (tmp_path / "versions" / "v2").mkdir()
    _puntero(tmp_path, "v2")
    pub, error = cargar_publicacion(tmp_path)
    assert pub is None and "incompleta" in error


def test_lee_version_aprobada_y_estados_por_serie(tmp_path):
    _version(tmp_path, "v1")
    _puntero(tmp_path, "v1")
    pub, error = cargar_publicacion(tmp_path)
    assert error is None
    assert pub.version == "v1"
    assert pub.actualizado_en == "2026-11-01T10:00:00"
    assert pub.run_id == "run-v1"
    assert pub.fuente_hash == "a" * 12
    assert series_publicadas(pub) == ["Total", "Vía Marítima"]
    assert estado_por_serie(pub) == {"Total": "aprobado", "Vía Marítima": "referencia"}


def test_restaurar_cambia_el_puntero_y_el_tablero_lee_la_version_anterior(tmp_path):
    _version(tmp_path, "v1", valor=100.0)
    _version(tmp_path, "v2", valor=200.0)
    _puntero(tmp_path, "v2", anterior="v1")
    assert cargar_publicacion(tmp_path)[0].estimaciones["valor"].iloc[0] == 200.0

    publicar.restaurar(tmp_path, "v1")
    pub, error = cargar_publicacion(tmp_path)
    assert error is None and pub.version == "v1"
    assert pub.puntero["restaurada_en"]
    assert pub.estimaciones["valor"].iloc[0] == 100.0


def test_current_corrupto_devuelve_no_disponible(tmp_path):
    (tmp_path / "current.json").write_text("{no es json", encoding="utf-8")
    pub, error = cargar_publicacion(tmp_path)
    assert pub is None and "no se pudo leer" in error
