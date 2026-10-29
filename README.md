# Observatorio de Turismo Sostenible · Guatemala — Laboratorio 10 (CC3066)

Tablero interactivo en **Streamlit + Plotly** sobre las llegadas internacionales de viajeros (INGUAT/Migración, 2009–jun 2026).
Reutiliza los modelos del Laboratorio 1 (ARIMA, Seasonal Naive, Prophet); **no se entrenan modelos nuevos**.

## Ejecutar
```bash
pip install -r requirements.txt
streamlit run app/app.py
```

## Estructura
- `app/app.py` — tablero (avance: V1 serie con nivel de detalle, V2↔V3 región→país enlazadas, V4 pronóstico vs observado).
- `data/` — archivos ya exportados que lee el tablero (`base_viajeros.csv.gz`, `series_mensuales.csv`, `predicciones_lab1.csv`, `metricas_lab1.csv`).
- `scripts/exportar_modelos_lab1.py` — regenera `data/` desde `Base_Migracion_2009-2026jun.xlsx` con los mismos modelos y parámetros del Lab 1.
- `.streamlit/config.toml` — tema de color.

## Convención de color (igual en toda la app)
Verde azulado = dato observado · Naranja = estimación de un modelo · Gris = referencia / pandemia · Azul marino = texto y selección.
