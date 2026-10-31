"""Registro de cada ejecución en MLflow Tracking (ejercicio 4).

Una ejecución del pipeline = un run de MLflow dentro del experimento del destino.
Si `mlflow.habilitado` es false, todas las funciones no hacen nada (útil para pruebas rápidas).
La variable de entorno MLFLOW_TRACKING_URI, si existe, tiene prioridad sobre el config (para Docker)."""
import os
import re
import unicodedata
from pathlib import Path

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")


def slug(texto):
    """'Vía Aérea' -> 'via_aerea' (nombres seguros para métricas y parámetros)."""
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")


class Registro:
    def __init__(self, cfg, base):
        self.cfg = cfg.get("mlflow", {}) or {}
        self.activo = bool(self.cfg.get("habilitado", False))
        self.base = Path(base)
        self.run_id = None
        self.uri = None
        self._ml = None

    # ---- inicio y fin ------------------------------------------------------------------
    def iniciar(self, nombre_run, destino, tags):
        if not self.activo:
            return None
        import mlflow
        self._ml = mlflow
        self.uri = os.environ.get("MLFLOW_TRACKING_URI") or self.cfg["tracking_uri"]
        if self.uri.startswith("sqlite:///") and not self.uri.startswith("sqlite:////"):
            (self.base / Path(self.uri[len("sqlite:///"):]).parent).mkdir(parents=True, exist_ok=True)
        mlflow.set_tracking_uri(self.uri)
        nombre_exp = self.cfg.get("experimento", "observatorio-turismo") + f"-{slug(destino)}"
        exp = mlflow.get_experiment_by_name(nombre_exp)
        if exp is None:
            artefactos = (self.base / self.cfg.get("artefactos", "mlflow/artifacts")).resolve()
            artefactos.mkdir(parents=True, exist_ok=True)
            exp_id = mlflow.create_experiment(nombre_exp, artifact_location=artefactos.as_uri(),
                                              tags={"destino": destino, "proyecto": "Observatorio de Turismo Sostenible"})
        else:
            exp_id = exp.experiment_id
        run = mlflow.start_run(experiment_id=exp_id, run_name=nombre_run, tags=tags)
        self.run_id = run.info.run_id
        return self.run_id

    def terminar(self, exito):
        if self.activo and self.run_id:
            self._ml.end_run(status="FINISHED" if exito else "FAILED")

    # ---- registros -----------------------------------------------------------------------
    def tags(self, d):
        if self.activo and self.run_id:
            self._ml.set_tags({k: str(v)[:5000] for k, v in d.items()})

    def params(self, d):
        if self.activo and self.run_id:
            self._ml.log_params({k: str(v)[:6000] for k, v in d.items()})

    def metricas(self, d):
        if self.activo and self.run_id:
            limpio = {k: float(v) for k, v in d.items() if v is not None and v == v}   # sin NaN: no se inventan valores
            if limpio:
                self._ml.log_metrics(limpio)

    def artefacto(self, ruta, carpeta=None):
        if self.activo and self.run_id and Path(ruta).exists():
            self._ml.log_artifact(str(ruta), artifact_path=carpeta)
