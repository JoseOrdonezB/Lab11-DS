"""Pruebas del registro en MLflow (ejercicio 4.3): una ejecución detenida queda como FAILED,
con su causa y sin métricas de evaluación inventadas. Datos sintéticos."""
from pathlib import Path

import mlflow

from pipeline import run
from tests.test_controles import base, cfg  # noqa: F401  (fixtures)

CFG_PATH = Path(__file__).resolve().parent.parent / "config" / "pipeline.yaml"


def test_ejecucion_detenida_queda_failed_con_causa_y_sin_metricas(base, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.chdir(tmp_path)
    # URI absoluta y propia de esta prueba: MLflow reutiliza la conexión por URI dentro del mismo proceso
    uri = "sqlite:///" + (tmp_path / "mlflow.db").as_posix()
    monkeypatch.setenv("MLFLOW_TRACKING_URI", uri)
    malo = tmp_path / "fuente_mala.csv"
    base.drop(columns=["Frontera"]).to_csv(malo, index=False)

    assert run.main(["--config", str(CFG_PATH), "--fuente", str(malo)]) == 2

    mlflow.set_tracking_uri(uri)
    r = mlflow.search_runs(experiment_names=["observatorio-turismo-guatemala"])
    assert len(r) == 1
    fila = r.iloc[0]
    assert fila["status"] == "FAILED"
    assert fila["tags.control_C1"] == "FAIL"
    assert "Frontera" in fila["tags.causa"]
    assert not any(c.startswith("metrics.") and c.endswith("_MAE") for c in r.columns)   # no se inventan métricas
    assert fila["params.fuente_sha256"]                                                    # la fuente queda identificada
