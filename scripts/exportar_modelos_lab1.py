"""
Exporta los resultados del Laboratorio 1 (series de tiempo) a archivos que consume el tablero.
NO se construyen modelos nuevos: se re-ejecutan los modelos ya seleccionados en el Lab 1
(mismo corte 70/30, mismos órdenes ARIMA, Seasonal Naive, Prophet, Holt-Winters y Suav. Exp. Simple)
para guardar sus predicciones sobre el conjunto de prueba (abr-2021 a jun-2026).

Uso:  python scripts/exportar_modelos_lab1.py  <ruta Base_Migracion_2009-2026jun.xlsx>
"""
import sys, logging, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.holtwinters import ExponentialSmoothing, SimpleExpSmoothing
from prophet import Prophet
from sklearn.metrics import mean_absolute_error, mean_squared_error

SRC = sys.argv[1] if len(sys.argv) > 1 else "Base_Migracion_2009-2026jun.xlsx"
SPLIT_DATE = pd.Timestamp("2021-04-01")
# Orden ARIMA elegido por AIC/BIC en el Lab 1 para cada serie
ORDENES = {"total": (1, 0, 1), "aerea": (1, 0, 1), "terrestre": (2, 1, 0), "maritima": (2, 0, 3),
           "centro": (1, 0, 0), "norte": (3, 0, 0), "europa": (4, 1, 2)}
NOMBRES = {"total": "Total", "aerea": "Vía Aérea", "terrestre": "Vía Terrestre", "maritima": "Vía Marítima",
           "centro": "América del Centro", "norte": "América del Norte", "europa": "Europa"}

df = pd.read_excel(SRC)
df["Región dos"] = df["Región dos"].replace({"Cruceros": "Cruceristas", "0": "Sin Clasificar"})

# ---- Base compacta para exploración (sin perder ninguna fila) ----
cols = ["Año", "Mes cod", "Vía", "Frontera", "País", "Región dos", "Tipo de Viajero", "Viajero"]
df[cols].to_csv("data/base_viajeros.csv.gz", index=False, compression="gzip")

# ---- Series mensuales (misma construcción que el Lab 1) ----
df_s = df[df["Tipo de Viajero"] != "Viajero"]


def mensual(d):
    m = d.groupby(["Año", "Mes cod"])["Viajero"].sum().reset_index()
    idx = pd.to_datetime(dict(year=m["Año"], month=m["Mes cod"], day=1))
    s = pd.Series(m["Viajero"].values, index=pd.DatetimeIndex(idx))
    s = s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="MS"), fill_value=0)
    s.index.freq = "MS"
    return s


series = {
    "total": mensual(df_s), "aerea": mensual(df_s[df_s["Vía"] == "Aérea"]),
    "terrestre": mensual(df_s[df_s["Vía"] == "Terrestre"]),
    "maritima": mensual(df[df["Vía"] == "Marítima"]),   # excepción documentada en el Lab 1
    "centro": mensual(df_s[df_s["Región dos"] == "América Del Centro"]),
    "norte": mensual(df_s[df_s["Región dos"] == "América Del Norte"]),
    "europa": mensual(df_s[df_s["Región dos"] == "Europa"]),
}

preds, mets, reales = [], [], []
for slug, ts in series.items():
    # criterio de transformación logarítmica del Lab 1
    tmp = ts.to_frame("v")
    tmp["a"] = tmp.index.year
    cv = tmp.groupby("a")["v"].apply(lambda x: x.std() / x.mean() if x.mean() else np.nan).dropna()
    need_log = (cv.max() - cv.min()) > 0.25 and (ts > 0).all()
    tr_o, te_o = ts[ts.index < SPLIT_DATE], ts[ts.index >= SPLIT_DATE]
    tr = np.log(tr_o) if need_log else tr_o
    fit = ARIMA(tr, order=ORDENES[slug]).fit()
    p_ar = np.asarray(fit.forecast(len(te_o)))
    p_ar = np.exp(p_ar) if need_log else p_ar
    p_hw = ExponentialSmoothing(tr_o, trend="add", seasonal="add", seasonal_periods=12).fit().forecast(len(te_o)).values
    p_se = SimpleExpSmoothing(tr_o, initialization_method="estimated").fit().forecast(len(te_o)).values
    p_sn = np.array([ts.loc[d - pd.DateOffset(years=1)] if (d - pd.DateOffset(years=1)) in ts.index
                     else tr_o.iloc[-1] for d in te_o.index])
    pdf = tr_o.reset_index()
    pdf.columns = ["ds", "y"]
    pm = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False).fit(pdf)
    p_pr = pm.predict(pd.DataFrame({"ds": te_o.index}))["yhat"].values
    modelos = {f"ARIMA{ORDENES[slug]}": p_ar, "Seasonal Naive": p_sn, "Prophet": p_pr,
               "Holt-Winters": p_hw, "Suav. Exp. Simple": p_se}
    for nombre, p in modelos.items():
        real = te_o.values
        mets.append({"serie": NOMBRES[slug], "modelo": nombre,
                     "MAE": mean_absolute_error(real, p),
                     "RMSE": float(np.sqrt(mean_squared_error(real, p))),
                     "MAPE_%": float(np.nanmean(np.abs((real - p) / np.where(real == 0, np.nan, real))) * 100)})
        for f, v in zip(te_o.index, p):
            preds.append({"serie": NOMBRES[slug], "modelo": nombre, "fecha": f, "prediccion": float(v)})
    for f, v in ts.items():
        reales.append({"serie": NOMBRES[slug], "fecha": f, "real": float(v),
                       "conjunto": "prueba" if f >= SPLIT_DATE else "entrenamiento"})
    print("ok", slug, "(log)" if need_log else "")

pd.DataFrame(reales).to_csv("data/series_mensuales.csv", index=False)
pd.DataFrame(preds).to_csv("data/predicciones_lab1.csv", index=False)
pd.DataFrame(mets).round(2).to_csv("data/metricas_lab1.csv", index=False)
print("Exportado: series_mensuales.csv, predicciones_lab1.csv, metricas_lab1.csv, base_viajeros.csv.gz")
