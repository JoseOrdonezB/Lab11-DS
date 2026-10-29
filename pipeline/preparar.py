"""Lectura de la fuente y construcción de las series mensuales (sin imputar ceros)."""
import pandas as pd


def leer_fuente(ruta):
    ruta = str(ruta)
    if ruta.endswith((".xlsx", ".xls")):
        return pd.read_excel(ruta)
    return pd.read_csv(ruta)          # .csv o .csv.gz


def agregar_fecha(df):
    """Agrega la columna fecha (primer día del mes). Año o mes inválidos quedan como NaT."""
    df = df.copy()
    anio = pd.to_numeric(df["Año"], errors="coerce")
    mes = pd.to_numeric(df["Mes cod"], errors="coerce")
    ok = anio.between(1900, 2100) & mes.between(1, 12)
    df["fecha"] = pd.NaT
    df.loc[ok, "fecha"] = pd.to_datetime(
        {"year": anio[ok].astype(int), "month": mes[ok].astype(int), "day": 1})
    return df


def meses(inicio, fin):
    return pd.date_range(pd.Timestamp(inicio + "-01"), pd.Timestamp(fin + "-01"), freq="MS")


def construir_serie(df, spec, cfg, indice):
    """Suma mensual de Viajero para una serie. Un mes sin filas queda en NaN (faltante), no en 0."""
    d = df
    if spec.get("excluir_tipo", True):
        d = d[d["Tipo de Viajero"] != cfg["fuente"]["tipo_excluido"]]
    if "via" in spec:
        d = d[d["Vía"] == spec["via"]]
    if "region" in spec:
        d = d[d["Región dos"] == spec["region"]]
    m = d.groupby("fecha")["Viajero"].sum()
    s = m.reindex(indice)
    s.index.freq = "MS"
    return s


def construir_series(df, cfg):
    idx = meses(cfg["periodos"]["cobertura"]["inicio"], cfg["periodos"]["cobertura"]["fin"])
    return {nombre: construir_serie(df, spec, cfg, idx) for nombre, spec in cfg["series"].items()}
