# Observatorio del mercado asegurador costarricense

## Qué contiene
Aplicación web estática sin servicios de pago, creada para visualizar una **línea base de 2024 y 2025** a partir del boletín SUGESE de diciembre 2025. La versión inicial NO incluye datos mensuales 2026 ni extracción automática.

**Abrir:** `index.html` servido desde GitHub Pages (requiere activarlo en Settings > Pages > Deploy from a branch > main / root).

## Fuentes y trazabilidad
- Estadísticas: https://www.sugese.fi.cr/cr/es/estadisticas.html
- Boletín cierre diciembre 2025: https://www.sugese.fi.cr/seccion-estadistica/Boletines/boletin_dic_2025.pdf
- Datos: `data/mercado_2025.json`; catálogo: `data/catalogo_fuentes.json`

### Advertencias
- Las cifras monetarias anuales están redondeadas: las tasas oficiales de crecimiento se muestran de forma independiente.
- No confundir siniestros pagados/primas emitidas con índice técnico de siniestralidad.
- La cuota «Otros» es agregada, no una aseguradora; no se puede calcular HHI por entidad con este agregado.
- SUGESE revisó datos de diciembre 2024 a agosto 2025 en octubre 2025.
- No actualizar el corte cambiando solamente el año o fecha del JSON. Primero reconciliar con la fuente oficial y revisar metodología.
- No subir información de clientes, credenciales ni datos internos de bancos o aseguradoras.

## Funcionamiento
`index.html` utiliza `fetch` para consultar los JSON locales del repositorio y ofrece un dashboard responsive con indicadores, rankings, resultados contables y enlaces a 14 reportes oficiales; CSV de resultados descargable. **GitHub Pages** aloja un sitio estático; no es una base de datos ni ejecuta ingestión.

## Próximos hitos
1. Exportar Primas y siniestros, Ratio combinado, Resultado técnico-financiero e Índice de suficiencia de capital desde Power BI de SUGESE.
2. Normalizar dimensiones (fecha, compañía, ramo, indicador, moneda, unidad, tipo mensual/acumulado).
3. Agregar validación de totales, revisiones y series entre 2015 y 2026.
4. Investigar una vía estable, pública y permitida de descarga; solo entonces automatizar con GitHub Actions.
