#!/usr/bin/env python3
"""Validaciones offline de integridad del catálogo y de línea base. No descarga SUGESE."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
m=json.loads((root/"data/mercado_2025.json").read_text(encoding="utf-8"))
c=json.loads((root/"data/catalogo_fuentes.json").read_text(encoding="utf-8"))
assert m["meta"]["fuente"].startswith("https://www.sugese.fi.cr/")
assert {x["anio"] for x in m["anuales"]} == {2024,2025}
assert len(m["resultados_aseguradoras_millones"]) == 12
assert len({x["aseguradora"] for x in m["resultados_aseguradoras_millones"]}) == 12
assert len(c["interactivos"])==14
for year in (2024,2025):
    total=sum(x[f"p{year}"] for x in m["participaciones_mercado_pct"])
    assert abs(total-100)<0.05, (year,total)
    assert all(0<=x[f"p{year}"]<=100 for x in m["participaciones_mercado_pct"])
assert sum(x["grupo"] for x in m["participaciones_mercado_pct"])==1
for r in m["anuales"]:
    assert r["primas"]>0 and r["siniestros_pagados"]>=0
assert abs(sum(x["r2025"] for x in m["resultados_aseguradoras_millones"])-77297.10)<0.05
assert abs(sum(x["r2024"] for x in m["resultados_aseguradoras_millones"])-46666.65)<0.05
print("OK: fuente, periodos, 14 reportes, participaciones, 12 resultados y totales conciliados.")
