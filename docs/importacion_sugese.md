# Incorporar datos oficiales de 2026 al observatorio

## Estado real
SUGESE publica estadísticas desde 2015 hasta la actualidad mediante Power BI y ofrece exportación histórica a Excel. No hemos demostrado aún una API pública estable para las tablas subyacentes; por tanto, **la revisión diaria de la página NO actualiza por sí sola las cifras**.

## Ruta funcional sin costos adicionales

1. Abrir [SUGESE — Estadísticas](https://www.sugese.fi.cr/cr/es/estadisticas.html).
2. Entrar a **Primas y siniestros** y usar el botón **Exportar** descrito en la [guía oficial](https://www.sugese.fi.cr/seccion-estadistica/Ayudas/Guia_Reportes_Estadisticos.pdf).
3. Revisar el archivo exportado y convertirlo al esquema documentado abajo. **No asumir que cualquier Excel de Power BI tiene estas columnas**: los diseños pueden variar; si la exportación no coincide hay que inspeccionarla antes de mapearla.
4. Guardar el CSV UTF-8 o Excel `.xlsx` normalizado en `incoming/` del repositorio. GitHub Actions ejecuta `scripts/ingestar_sugese.py`, valida y publica `data/series_sugese.json` si pasa las verificaciones.
5. Verificar el workflow **Publicar datos oficiales SUGESE 2026** en Actions y que los indicadores del sitio indiquen el corte, tipo de serie y fuente.

## Columnas obligatorias
- `periodo`: AAAA-MM (ej. 2026-09).
- `aseguradora`: Mercado (agregado) o entidad.
- `ramo`: Todos (agregado) o ramo específico.
- `indicador`: primas emitidas o siniestros pagados.
- `valor`: numérico sin símbolos, en **millones CRC** (no unidades de colones).
- `unidad`: **millones CRC**.
- `tipo_serie`: mensual, acumulado_anual, 12m_movil o trimestral.
- `fuente_url`: URL oficial SUGESE o el Power BI publicado por SUGESE.

Plantilla de encabezados: [plantilla CSV](plantilla_series_2026.csv). Está vacía porque no se deben introducir cifras ficticias.

## Validaciones
- Acepta solo 2026 y métricas compatibles.
- Unidad explícita obligatoria, sin inferencias.
- Rechaza valores contradictorios con la misma clave y formatos ambiguos.
- Cuando se incluyen un total de mercado y dos o más compañías, verifica que sumen dentro de una tolerancia del 0,5%.
- Si solo hay datos desagregados, los marca como validados estructuralmente, **no** conciliados externamente.
- No altera el último conjunto publicado si una importación falla.
- Nunca equipara un acumulado anual o 12 meses móviles con un único mes.

## Automatización
- GitHub Actions publica los archivos ya exportados y normalizados.
- `Vigilar actualizaciones de SUGESE` comprueba fuentes diariamente, pero **no es extracción de series**.
- `Diagnóstico de extracción SUGESE` intenta comprobar si Power BI ofrece descargas públicas. Una ejecución exitosa del workflow no demuestra que haya encontrado datos estructurados.
- Si se encuentra un archivo de descarga directa permitido, podrá conectarse después al parser y eliminar la carga manual.

## Calidad, cumplimiento y privacidad
Solo utilizar archivos estadísticos públicos. No publicar datos de clientes, claves, credenciales ni información interna de Davivienda.
