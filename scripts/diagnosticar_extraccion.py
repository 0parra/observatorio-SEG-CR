#!/usr/bin/env python3
"""Diagnóstico público de extracción SUGESE.

No utiliza credenciales ni API interna de Power BI. Solo descubre enlaces y
prueba la exportación visual pública; nunca inventa cifras.
"""
import json, re, sys, hashlib, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data"/"diagnostico_extraccion.json"
ART=ROOT/"tmp"/"sugese_probe"
ART.mkdir(parents=True, exist_ok=True)
STAT="https://www.sugese.fi.cr/cr/es/estadisticas.html"
PBI="https://app.powerbi.com/view?r=eyJrIjoiNzY4OWNlNjItM2Y5ZC00ZDUxLWI3ODgtMGNmZTE1M2MyNmIwIiwidCI6IjYxOGQwYTQ1LTI1YTYtNDYxOC05ZjgwLThmNzBhNDM1ZWU1MiJ9"
HEADERS={"User-Agent":"Mozilla/5.0 ObservatorioSUGESE/1.0 (+https://github.com/0parra/observatorio-SEG-CR)"}
status={"revisado_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),"tipo":"diagnostico_sin_extraccion_validada","pagina_estadisticas":STAT,"reporte_powerbi":PBI,"sitio":{},"powerbi":{},"archivos":[],"errores":[],"ingesta_validada":False}

def valid_link(url):
 p=urlparse(url)
 return p.scheme=="https" and p.hostname in ("sugese.fi.cr","www.sugese.fi.cr","app.powerbi.com")
try:
 r=requests.get(STAT,headers=HEADERS,timeout=25)
 soup=BeautifulSoup(r.text,"html.parser")
 anchors=[{"texto":a.get_text(" ",strip=True)[:90],"url":urljoin(STAT,a.get("href",""))} for a in soup.find_all("a",href=True)]
 links=[x for x in anchors if valid_link(x["url"]) and any(t in (x["texto"]+" "+x["url"]).lower() for t in ["bolet","excel",".xls","powerbi","primas","siniestro"])]
 status["sitio"]={"http":r.status_code,"bytes":len(r.content),"sha256":hashlib.sha256(r.content).hexdigest(),"enlaces_relevantes":links[:80]}
 print("SUGESE page:",r.status_code,len(r.content),"relevant links",len(links))
except Exception as ex:status["errores"].append("Sitio: "+repr(ex))
for month in ["sep","set","ago","jul","jun"]:
 u="https://www.sugese.fi.cr/seccion-estadistica/Boletines/boletin_"+month+"_2026.pdf"
 try:
  r=requests.get(u,headers=HEADERS,timeout=18,stream=True)
  typ=r.headers.get("content-type","")
  d=next(r.iter_content(32),b"")
  status["archivos"].append({"url":u,"http":r.status_code,"tipo":typ,"firma_pdf":d.startswith(b"%PDF-")})
  r.close()
 except Exception as ex:status["archivos"].append({"url":u,"error":repr(ex)[:150]})
try:
 from playwright.sync_api import sync_playwright,TimeoutError as PTimeout
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True,args=["--no-sandbox","--disable-dev-shm-usage"])
  page=browser.new_page(viewport={"width":1440,"height":900},accept_downloads=True)
  captures=[]
  page.on("download",lambda d:captures.append(d))
  page.on("response",lambda r: None)
  response=page.goto(PBI,wait_until="domcontentloaded",timeout=50000)
  page.wait_for_timeout(18000)
  frames=page.frames
  summary=[]
  for fr in frames:
   try:
    t=fr.locator("body").inner_text(timeout=2500)
    summary.append({"url":fr.url[:180],"texto":t[:1300],"botones_exportar":fr.get_by_text(re.compile("exportar",re.I)).count()})
   except Exception as ex:summary.append({"url":fr.url[:180],"error":str(ex)[:120]})
  status["powerbi"]={"http":response.status if response else None,"iframes":len(frames),"texto_y_controles":summary[:15]}
  print("Power BI",status["powerbi"]["http"],"frames",len(frames))
  try:
   page.screenshot(path=str(ART/"powerbi.png"),full_page=False,timeout=10000)
  except Exception as ex:status["errores"].append("Captura: "+repr(ex))
  # La portada del informe no contiene Exportar; navegar primero a un cuadro
  # público del propio reporte, sin usar APIs internas ni credenciales.
  try:
   nav=page.get_by_text("Por ramo y aseguradora",exact=True)
   status["powerbi"]["boton_entrada_cuadros"]=nav.count()
   if nav.count():
    nav.first.click(timeout=15000)
    page.wait_for_timeout(14000)
    detail=page.locator("body").inner_text(timeout=10000)
    status["powerbi"]["detalle_cuadro"]={"texto":detail[:4000],"controles_exportar":page.get_by_text(re.compile("Exportar",re.I)).count()}
    page.screenshot(path=str(ART/"cuadro_por_ramo_aseguradora.png"),full_page=False,timeout=10000)
    print("Cuadro abierto: Exportar",status["powerbi"]["detalle_cuadro"]["controles_exportar"])
  except Exception as ex:status["errores"].append("Navegación dentro Power BI: "+repr(ex)[:200])
  for frame in frames:
   if captures:break
   try:
    loc=frame.get_by_text(re.compile(r"^Exportar$",re.I))
    if loc.count():
     print("Visible export control in frame",frame.url[:90])
     loc.first.click(timeout=9000)
     page.wait_for_timeout(6000)
   except Exception as ex:status["errores"].append("Control Exportar: "+repr(ex)[:150])
  for d in captures[:3]:
   name=re.sub(r"[^a-zA-Z0-9_.-]","_",d.suggested_filename)[:90]
   dest=ART/name
   d.save_as(str(dest))
   magic=dest.read_bytes()[:8]
   status["archivos"].append({"descarga_powerbi":name,"bytes":dest.stat().st_size,"tipo_detectado":"xlsx" if magic[:2]==b"PK" else "otro","url":d.url[:160]})
  browser.close()
except Exception as ex:
 status["errores"].append("Power BI automatizado: "+repr(ex)[:300])
status["conclusion"]="La detección de descargas requiere validación del archivo y su contenido antes de actualizar indicadores. No se publica ningún KPI directamente desde esta prueba."
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(status,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
print(json.dumps(status,ensure_ascii=False,indent=2)[:15000])
