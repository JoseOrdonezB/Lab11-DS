# Reporte de monitoreo — ejecución 20261101-195824-43e3ea

- Versión generada: **v2026.11.01-04**
- Inicio: 2026-11-01T19:58:24 · Fin: 2026-11-01T19:58:42
- Resultado: **CON ALERTAS PARA REVISIÓN; la publicación no se bloquea por una variación alta**.
- Fuente (SHA-256): `cdaba77918ae889c847ba8459503f9cce2441efac41b3d3aa0f05ac9ab283846`
- Config (SHA-256): `7818d835f7ae2c52133fb8bf9f0b3e8c3119b9be63b47253f598833a5e0f0718`

| Verificación | Estado | Afectados | Umbral | Resultado |
|---|---|---:|---|---|
| M1 actualización | OK | 0 | desfase máximo 0 mes(es) | Fuente y estimaciones al día: último mes de la fuente 2026-06 y pronóstico hasta 2026-12. |
| M2 calidad | OK | 0 | faltantes +0.5 pp, duplicados +0.1 pp, cobertura +0 meses | Sin cambios relevantes frente a la versión anterior: 0.0000 % faltantes, 0.0261 % duplicados, 37 meses sin información. |
| M3 resultados | ALERTA | 2 | variación mensual ≤ 35%, frente a versión ≤ 25% | Sin negativas ni valores no finitos. Variación máxima mes a mes: 94.4%. Variación máxima frente a la versión anterior: 0.0%. Alertas: variación mes a mes sobre el umbral en Europa 94%, Vía Marítima 36%. Una variación alta es una señal para revisión, no una prueba de pérdida de precisión; el error predictivo solo se actualiza con observaciones comparables. |

## Qué comprueba cada verificación

- **M1 actualización:** que la fuente llegue al último mes de la cobertura configurada y que las estimaciones cubran el período de pronóstico esperado. Si falta un mes, se alerta para revisar la carga de datos; no se convierte en cero.
- **M2 calidad:** compara faltantes, duplicados y meses sin información contra la línea base de la versión aprobada anterior. Los umbrales están en `config/pipeline.yaml`; un aumento mayor al umbral genera alerta.
- **M3 resultados:** detecta estimaciones negativas, no finitas y variaciones mes a mes o frente a la versión anterior que superen los umbrales justificados.

Una alerta es una señal para revisión: **no demuestra por sí sola pérdida de precisión** ni cambia automáticamente la versión publicada. El error predictivo (MAE/RMSE) solo se calcula con observaciones comparables del backtest; no se inventan errores para meses futuros.

## Línea base para la próxima ejecución

- Faltantes: 0.0 %
- Duplicados: 0.026081124717454482 %
- Meses sin información: 37
- Versión anterior: v2026.11.01-03
