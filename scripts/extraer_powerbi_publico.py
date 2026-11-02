#!/usr/bin/env python3
"""Extrae exclusivamente tablas PUBLICAS renderizadas de SUGESE Power BI.
No usa APIs internas de Power BI, credenciales, ni datos no publicados.
Se publica solamente si pasa validaciones estrictas de corte y totales.
"""
import json, re, hashlib, sys
from pathlib import Path
from datetime import datetime,timezone
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data"/"series_powerbi.json"
URL="https://app.powerbi.com/view?r=eyJrIjoiNzY4OWNlNjItM2Y5ZC00ZDUxLWI3ODgtMGNmZTE1M2MyNmIwIiwidCI6IjYxOGQwYTQ1LTI1YTYtNDYxOC05ZjgwLThmNzBhNDM1ZWU1MiJ9"
HEAD=re.compile(r"^(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)-(\d{2})$",re.I)
NUM=re.compile(r"^-?\d{1,3}(?:,\d{3})*\.\d{2}$|^-?\d+\.\d{2}$")
MONTHS={"ene":"01","feb":"02","mar":"03","abr":"04","may":"05","jun":"06","jul":"07","ago":"08","sep":"09","oct":"10","nov":"11","dic":"12"}
def parse_table(text):
 try:
  fragment=text.split("Composición por ramo",1)[1].split("Nota:",1)[0]
 except IndexError:raise ValueError("No se encontró la tabla pública 'Composición por ramo'")
 lines=[x.replace("\u00a0"," ").strip() for x in fragment.splitlines()]
 lines=[x for x in lines if x]
 try:ix=lines.index("Ramo")
 except ValueError:raise ValueError("Tabla sin encabezado Ramo")
 years=[]
 while ix+1<len(lines) and (m:=HEAD.fullmatch(lines[ix+1])):
  ix+=1
  years.append("20"+m.group(2)+"-"+MONTHS[m.group(1).lower()])
 if len(years)<2 or not years[-1].startswith("2026-"):
  raise ValueError("No se encuentra una serie 2026 y periodo anterior comparable")
 raw={}
 label=None
 for value in lines[ix+1:]:
  if NUM.fullmatch(value):
   if label is None:raise ValueError("Dato numérico sin fila")
   raw[label].append(float(value.replace(",","")))
  else:
   label=value
   if label in raw:raise ValueError("Ramo duplicado: "+label)
   raw[label]=[]
 totals=raw.get("Total")
 if not totals or len(totals)!=len(years):
  raise ValueError("La fila Total no incluye todas las columnas")
 if not all(v>0 for v in totals):raise ValueError("Total no positivo")
 obs=[]
 missing=[]
 for label,values in raw.items():
  if label=="Total":continue
  if len(values)!=len(years):
   missing.append({"ramo":label,"encontrados":len(values),"esperados":len(years)})
   # NO se asignan montos a periodos si falta una celda intermedia
   continue
  for period,value in zip(years,values):
   obs.append({"periodo":period,"aseguradora":"Mercado","ramo":label,"indicador":"primas_emitidas","valor":value,"unidad":"millones CRC","tipo_serie":"acumulado_anual","fuente_url":URL})
 for period,total in zip(years,totals):
  obs.append({"periodo":period,"aseguradora":"Mercado","ramo":"Todos","indicador":"primas_emitidas","valor":total,"unidad":"millones CRC","tipo_serie":"acumulado_anual","fuente_url":URL})
 # Para cada año se revisa que la suma de ramos disponibles no supere el total
 # (se admiten <= 0,5% faltantes por filas con celdas vacías).
 controls=[]
 for period,total in zip(years,totals):
  subtotal=sum(r["valor"] for r in obs if r["periodo"]==period and r["ramo"]!="Todos")
  delta=total-subtotal
  if delta<-(total*0.005) or delta>total*0.005:
   raise ValueError(f"Conciliación de ramos falló {period}: total {total}, subtotal {subtotal}, diferencia {delta}")
  controls.append({"periodo":period,"total":total,"suma_ramos_completos":round(subtotal,2),"diferencia":round(delta,2)})
 return {"observaciones":obs,"totales":dict(zip(years,totals)),"controles":controls,"filas_omitidas_sin_posicion_cierta":missing}

def main():
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,args=["--no-sandbox","--disable-dev-shm-usage"])
  page=browser.new_page(viewport={"width":1440,"height":900})
  try:
   response=page.goto(URL,wait_until="domcontentloaded",timeout=60000)
   if not response or response.status!=200:raise ValueError("El reporte público no respondió con HTTP 200")
   page.wait_for_timeout(18000)  # Power BI necesita inicializar el lienzo antes de hacer clic
   buttons=page.get_by_text("Por ramo y aseguradora",exact=True)
   clicked=False
   for i in range(buttons.count()):
    option=buttons.nth(i)
    if option.is_visible():
     option.click(timeout=15000)
     clicked=True
     break
   if not clicked:raise ValueError("No apareció un botón visible de navegación tras cargar Power BI")
   page.get_by_text("Composición por ramo",exact=False).first.wait_for(timeout=30000)
   page.wait_for_timeout(5000)
   text=page.locator("body").inner_text(timeout=15000)
  finally:browser.close()
 parsed=parse_table(text)
 latest=max(parsed["totales"])
 metadata={
  "estado":"conciliado_con_totales",
  "origen":"Tabla pública Cuadro 1 de SUGESE Power BI; lectura del texto DOM accesible",
  "fuente":URL,
  "fecha_extraccion_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),
  "periodo_maximo":latest,
  "tipo_serie":"acumulado_anual",
  "unidad":"millones CRC",
  "control":["Cortes homogéneos para un mismo mes anual","Suma de ramos completos vs total <=0.5%",
             "Filas con celdas vacías omitidas para evitar atribución incorrecta de valores"],
  "conciliaciones":parsed["controles"],
  "filas_omitidas":parsed["filas_omitidas_sin_posicion_cierta"],
  "advertencia":"Datos de primas acumuladas, no de primas individuales del mes. No comprende siniestros ni todas las aseguradoras. Si el reporte cambia su formato, falla sin sobrescribir los datos publicados."
 }
 payload={"meta":metadata,"series":parsed["observaciones"]}
 if OUT.exists():
  try:
   anterior=json.loads(OUT.read_text(encoding="utf-8"))
   if anterior.get("series")==payload["series"]:
    print("Sin cambios de cifras oficiales respecto a la versión publicada; no se modifica el archivo.")
    return
  except (OSError,ValueError):pass
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
 p2025=parsed["totales"].get("2025-"+latest[-2:])
 cur=parsed["totales"][latest]
 print(json.dumps({"periodo":latest,"primas_millones_crc":cur,"primas_anio_prev":p2025,"variacion_yoy_pct":round((cur/p2025-1)*100,2) if p2025 else None,"filas":len(payload["series"]),"omitidas":len(metadata["filas_omitidas"])},ensure_ascii=False))
if __name__=="__main__":
 try:main()
 except Exception as exc:
  print("EXTRACCION FALLIDA (se preservan datos anteriores):",str(exc),file=sys.stderr)
  sys.exit(1)
