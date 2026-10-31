"""Orquestador. Un comando:  python -m pipeline.run [--config config/pipeline.yaml] [--fuente RUTA]
Restaurar una versión:      python -m pipeline.run --restaurar v2026.10.29-01

Códigos de salida: 0 publicado · 1 error inesperado · 2 detenido por control crítico · 3 candidato rechazado por la regla de aceptación.
Cada ejecución queda registrada como un run de MLflow (FINISHED en 0 y 3, FAILED en 1 y 2).
"""
import argparse, json, sys, traceback, uuid, platform
from datetime import datetime
from importlib import metadata
from pathlib import Path
import numpy as np
import pandas as pd

from . import controles, modelos, publicar as pub, reporte
from .preparar import leer_fuente
from .registro import Registro, slug
from .util import cargar_config, sha256, commit_git

RAIZ = Path(__file__).resolve().parent.parent


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pipeline del Observatorio de Turismo Sostenible")
    ap.add_argument("--config", default=str(RAIZ / "config" / "pipeline.yaml"))
    ap.add_argument("--fuente", help="ruta de la fuente (sustituye a rutas.fuente del config)")
    ap.add_argument("--restaurar", metavar="VERSION", help="apuntar current.json a una versión aprobada anterior")
    a = ap.parse_args(argv)

    cfg_path = Path(a.config)
    cfg = cargar_config(cfg_path)
    base = Path.cwd()
    pub_dir = base / cfg["rutas"]["publicacion"]

    if a.restaurar:
        pub.restaurar(pub_dir, a.restaurar)
        print(f"current.json apunta ahora a {a.restaurar}")
        return 0

    inicio = datetime.now()
    run_id = f"{inicio:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    cand = base / cfg["rutas"]["corridas"] / run_id
    cand.mkdir(parents=True, exist_ok=True)
    logf = open(cand / "run.log", "w", encoding="utf-8")
    etapas, advertencias = [], []
    reg = Registro(cfg, base)
    commit = commit_git(RAIZ)

    def log(msg):
        linea = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
        print(linea, flush=True)
        logf.write(linea + "\n"); logf.flush()
        if msg.startswith("WARN"):
            advertencias.append(msg)

    def cerrar(codigo, resultado, extra=None):
        fin = datetime.now()
        resumen = {"run_id": run_id, "mlflow_run_id": reg.run_id, "inicio": inicio.isoformat(timespec="seconds"),
                   "fin": fin.isoformat(timespec="seconds"), "etapas_completadas": etapas, "advertencias": advertencias,
                   "resultado_publicacion": resultado, "codigo_salida": codigo}
        resumen.update(extra or {})
        (cand / "run_summary.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"FIN run {run_id}: {resultado} (código {codigo})")
        logf.close()
        try:   # el cierre en MLflow nunca debe cambiar el resultado del pipeline
            reg.tags({"resultado": resultado, "codigo_salida": codigo, "fin": resumen["fin"],
                      "etapa_final": etapas[-1] if etapas else "ninguna", "n_advertencias": len(advertencias),
                      **({"causa": extra.get("causa")} if extra and extra.get("causa") else {})})
            for f in ("run.log", "run_summary.json"):
                reg.artefacto(cand / f, "registro")
            reg.terminar(exito=codigo in (0, 3))
        except Exception as e:
            print(f"AVISO: no se pudo cerrar el run en MLflow: {e!r}", flush=True)
        return codigo

    try:
        log(f"INICIO run {run_id}")
        reg.iniciar(run_id, cfg["destino"], {"run_id_local": run_id, "inicio": inicio.isoformat(timespec="seconds"),
                                              "commit_git": commit, "mlflow.source.git.commit": commit.split("+")[0],
                                              "destino": cfg["destino"], "unidad": cfg["unidad"]})
        if reg.run_id:
            log(f"MLflow: run {reg.run_id} en {reg.uri}")
        reg.artefacto(cfg_path, "configuracion")
        reg.artefacto(RAIZ / "requirements-pipeline.txt", "configuracion")

        # ---- Etapa 1: lectura e identificación -------------------------------------------
        fuente = Path(a.fuente or cfg["rutas"]["fuente"])
        if not fuente.is_absolute():
            fuente = base / fuente
        if not fuente.exists():
            log(f"ERROR no existe la fuente {fuente}. Copie el archivo institucional ahí o use --fuente.")
            return cerrar(1, "error: fuente no encontrada", {"causa": f"fuente no encontrada: {fuente.name}"})
        hashes = {"fuente": sha256(fuente), "config": sha256(cfg_path)}
        df = leer_fuente(fuente)
        etapas.append("1_lectura")
        log(f"Etapa 1 lectura: {fuente.name}, {len(df)} filas, sha256 fuente {hashes['fuente'][:12]}, config {hashes['config'][:12]}")
        p = cfg["periodos"]
        reg.params({"fuente_archivo": fuente.name, "fuente_sha256": hashes["fuente"], "fuente_filas": len(df),
                    "config_sha256": hashes["config"],
                    **{f"periodo_{k}": f"{v['inicio']} a {v['fin']}" for k, v in p.items()}})
        reg.tags({"fuente_sha256": hashes["fuente"], "config_sha256": hashes["config"]})

        # ---- Etapa 2: validación -----------------------------------------------------------
        ts = datetime.now().isoformat(timespec="seconds")
        ctrl, df_ok, series = controles.ejecutar(df, cfg, log)
        ctrl["run_id"], ctrl["timestamp"] = run_id, ts
        ctrl.to_csv(cand / "controles.csv", index=False)
        reporte.generar(ctrl, run_id, hashes, cand / "reporte_controles.md")
        etapas.append("2_validacion")
        fallos = ctrl[(ctrl["severidad"] == "critico") & (ctrl["estado"] == "FAIL")]
        for _, r in ctrl[ctrl["estado"] == "WARN"].iterrows():
            advertencias.append(f"{r['control']}: {r['detalle']}")
        conteo = ctrl["estado"].value_counts()
        reg.tags({f"control_{r['control'].split()[0]}": r["estado"] for _, r in ctrl.iterrows()})
        reg.tags({"controles_resultado": "FAIL" if len(fallos) else ("WARN" if conteo.get("WARN", 0) else "OK")})
        reg.metricas({f"controles_{k.lower()}": int(conteo.get(k, 0)) for k in ("OK", "WARN", "FAIL", "OMITIDO")})
        reg.artefacto(cand / "controles.csv", "controles")
        reg.artefacto(cand / "reporte_controles.md", "controles")
        if len(fallos):
            log(f"DETENIDO: control crítico en FAIL -> {list(fallos['control'])}. No se reemplazan los resultados vigentes.")
            causa = "; ".join(f"{r['control']}: {r['detalle']}" for _, r in fallos.iterrows())
            return cerrar(2, "detenido por control crítico; resultados vigentes intactos",
                          {"controles_fallidos": list(fallos["control"]), "causa": causa})

        # ---- Etapa 3: preparación (las series ya se construyeron sin imputar ceros) ------------
        etapas.append("3_preparacion")
        log("Etapa 3 preparación: " + ", ".join(f"{n} ({int(s.notna().sum())} meses con dato)" for n, s in series.items()))
        reg.params({f"meses_con_dato_{slug(n)}": int(s.notna().sum()) for n, s in series.items()})

        # ---- Etapas 4 y 5: ajuste y evaluación temporal --------------------------------------
        m, ac = cfg["modelo"], cfg["aceptacion"]
        reg.params({"modelo": m["nombre"], "referencia": m["referencia"], "semilla": cfg["semilla"],
                    "log_diferencia_cv_min": m["transformacion_log"]["diferencia_cv_min"],
                    "backtest_esquema": "origen expansivo, un paso adelante",
                    "aceptacion_series_obligatorias": ",".join(ac["series_obligatorias"]),
                    "aceptacion_mae_rel_max": ac["mae_rel_max"], "aceptacion_margen_vs_referencia": ac["margen_vs_referencia"],
                    "aceptacion_min_obs": ac["min_obs_evaluacion"],
                    "rango_plausible_max_factor": cfg["umbrales"]["rango_plausible_max_factor"],
                    **{f"arima_{slug(n)}": tuple(s["arima"]) for n, s in cfg["series"].items()}})
        bt, avisos_bt = modelos.backtest(series, cfg, log)
        etapas += ["4_ajuste", "5_evaluacion"]
        met = modelos.tabla_metricas(bt, cfg, run_id)

        # ---- Etapa 6: regla de aceptación ------------------------------------------------------
        met = modelos.regla_aceptacion(met, series, cfg)
        etapas.append("6_regla_aceptacion")
        for _, r in met.iterrows():
            log(f"  {r['serie']}: MAE {r['MAE']:.0f} (ref. {r['baseline_MAE']:.0f}), RMSE {r['RMSE']:.0f}, n={r['n_obs']} -> {'cumple' if r['cumple_regla'] else 'NO cumple'} ({r['motivo']})")
            k = slug(r["serie"])
            reg.metricas({f"{k}_MAE": r["MAE"], f"{k}_RMSE": r["RMSE"], f"{k}_MAPE_pct": r["MAPE_pct"], f"{k}_n_obs": r["n_obs"],
                          f"{k}_ref_MAE": r["baseline_MAE"], f"{k}_ref_RMSE": r["baseline_RMSE"],
                          f"{k}_cumple_regla": int(bool(r["cumple_regla"]))})
        reg.params({f"log_{slug(n)}": bool(g["log"].iloc[-1]) for n, g in bt.groupby("serie", sort=False)})
        met["mlflow_run_id"] = reg.run_id
        met.to_csv(cand / "metricas.csv", index=False)

        # ---- Etapa 7: estimaciones -------------------------------------------------------------
        version = pub.siguiente_version(pub_dir, inicio)
        est_f, parametros = modelos.pronosticar(series, cfg, run_id, ts, version, hashes)
        est_b = pd.DataFrame({
            "destino": cfg["destino"], "serie": bt["serie"], "periodo": bt["periodo"].dt.strftime("%Y-%m-%d"),
            "valor": bt["pred_modelo"], "unidad": cfg["unidad"],
            "modelo": [f"{cfg['modelo']['nombre']}{tuple(cfg['series'][s]['arima'])}" for s in bt["serie"]],
            "conjunto": "evaluacion", "horizonte": 0, "run_id": run_id, "fecha_generacion": ts,
            "version_procedimiento": version, "fuente_hash": hashes["fuente"], "config_hash": hashes["config"]})
        est = pd.concat([est_b, est_f], ignore_index=True)
        cumple = dict(zip(met["serie"], met["cumple_regla"]))
        est["estado"] = ["aprobado" if cumple[s] else "referencia" for s in est["serie"]]
        est["mlflow_run_id"] = reg.run_id
        etapas.append("7_estimaciones")

        # ---- Etapa 8: candidato inmutable --------------------------------------------------------
        est.to_csv(cand / "estimaciones.csv", index=False)
        bt.assign(periodo=bt["periodo"].dt.strftime("%Y-%m-%d")).to_csv(cand / "backtest_detalle.csv", index=False)
        (cand / "parametros_modelo.json").write_text(json.dumps(parametros, ensure_ascii=False, indent=2), encoding="utf-8")
        deps = {p: metadata.version(p) for p in ("pandas", "numpy", "statsmodels", "PyYAML", "mlflow") if _tiene(p)}

        # ---- Etapa 9: autorización -----------------------------------------------------------------
        razones = []
        if not np.isfinite(est["valor"]).all():
            razones.append("hay estimaciones no finitas")
        if (est["valor"] < 0).any():
            razones.append("hay estimaciones negativas")
        tope = {n: cfg["umbrales"]["rango_plausible_max_factor"] * float(s.max()) for n, s in series.items()}
        fuera = est[est["valor"] > est["serie"].map(tope)]
        if len(fuera):
            razones.append(f"{len(fuera)} estimaciones fuera del rango plausible")
        for s in ac["series_obligatorias"]:
            if not cumple.get(s, False):
                razones.append(f"la serie obligatoria {s} no cumple la regla de aceptación")
        aprobado = not razones
        manifest = {"version_procedimiento": version, "run_id": run_id, "mlflow_run_id": reg.run_id,
                    "mlflow_tracking_uri": reg.uri, "commit_git": commit,
                    "fuente": fuente.name, "fuente_hash": hashes["fuente"], "config_hash": hashes["config"],
                    "periodos": cfg["periodos"], "semilla": cfg["semilla"], "python": platform.python_version(), "dependencias": deps,
                    "inicio": inicio.isoformat(timespec="seconds"), "aprobado": aprobado, "motivos_rechazo": razones,
                    "aprobado_en": datetime.now().isoformat(timespec="seconds") if aprobado else None,
                    "resumen_metricas": {r["serie"]: {"MAE": round(r["MAE"], 2), "RMSE": round(r["RMSE"], 2),
                                                      "baseline_MAE": round(r["baseline_MAE"], 2), "cumple_regla": bool(r["cumple_regla"])}
                                         for _, r in met.iterrows()}}
        (cand / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        etapas.append("8_candidato")
        # el candidato queda registrado en MLflow ANTES de decidir si se publica
        for f in ("estimaciones.csv", "metricas.csv", "backtest_detalle.csv", "manifest.json"):
            reg.artefacto(cand / f, "candidato")
        reg.artefacto(cand / "parametros_modelo.json", "modelo")
        reg.params({"version_procedimiento": version, "python": platform.python_version(),
                    **{f"dep_{k}": v for k, v in deps.items()}})
        reg.tags({"aprobado": aprobado, "motivos_rechazo": "; ".join(razones) or "ninguno"})
        if not aprobado:
            log("RECHAZADO: " + "; ".join(razones) + ". Se conserva la versión vigente.")
            return cerrar(3, "candidato rechazado; resultados vigentes intactos", {"motivos_rechazo": razones})
        etapas.append("9_autorizacion")

        # ---- Etapas 10 y 11: versión aprobada y puntero atómico --------------------------------------
        pub.publicar(cand, pub_dir, version, manifest["aprobado_en"])
        etapas += ["10_version_aprobada", "11_puntero"]
        reg.tags({"version_publicada": version})
        log(f"PUBLICADO {version} en {pub_dir / 'versions' / version}")
        return cerrar(0, f"publicado {version}", {"version": version})
    except Exception as e:
        log("ERROR inesperado: " + repr(e))
        log(traceback.format_exc())
        return cerrar(1, "error inesperado; resultados vigentes intactos", {"error": repr(e), "causa": repr(e)[:500]})


def _tiene(p):
    try:
        metadata.version(p); return True
    except metadata.PackageNotFoundError:
        return False


if __name__ == "__main__":
    sys.exit(main())
