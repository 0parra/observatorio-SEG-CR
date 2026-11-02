#!/usr/bin/env python3
"""Ingesta conservadora de exportaciones públicas de SUGESE (CSV/XLSX).
No usa endpoints internos Power BI. No publica datos cuya unidad/periodo
sea ambigua. Fuente, periodo, nivel de conciliación y hash trazables.
"""
import csv, hashlib, io, json, re, sys, unicodedata
from datetime import datetime, date, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
INCOMING=ROOT/"incoming"
OUT=ROOT/"data"/"series_sugese.json"
ALLOWED={"mensual","acumulado_anual","12m_movil","trimestral"}
METRICS={
"prima":"primas_emitidas","primas":"primas_emitidas","prima emitida":"primas_emitidas",
"primas emitidas":"primas_emitidas","prima directa":"primas_emitidas",
"ingresos por primas":"primas_emitidas",
"siniestro":"siniestros_pagados","siniestros":"siniestros_pagados",
"siniestros pagados":"siniestros_pagados","siniestros brutos pagados":"siniestros_pagados",
"primas_emitidas":"primas_emitidas","siniestros_pagados":"siniestros_pagados",
}
ALIASES={
"periodo":["periodo","fecha","fecha corte","corte","mes"],
"aseguradora":["aseguradora","entidad","compania","empresa de seguros"],
"ramo":["ramo","ramo de seguro","categoria"],
"indicador":["indicador","variable","concepto","tipo indicador"],
"valor":["valor","monto","importe","valor en millones"],
"unidad":["unidad","unidad de medida"],
"tipo_serie":["tipo serie","tipo de serie","frecuencia acumulacion","acumulacion"],
"fuente_url":["fuente url","url fuente","fuente oficial","fuente"],
}
REQUIRED=("periodo","indicador","valor","unidad","tipo_serie","fuente_url")

def clean(value):
 text=str(value or "").strip().lower()
 return "".join(c for c in unicodedata.normalize("NFD",text) if unicodedata.category(c)!="Mn").replace("_"," ").replace("-"," ")

def mapping(header):
 h=[clean(x) for x in header]
 return {k:next((i for i,name in enumerate(h) if name in vals),None) for k,vals in ALIASES.items()}

def valid_date(value):
 if isinstance(value,(date,datetime)):return value.strftime("%Y-%m")
 text=str(value).strip()
 if re.fullmatch(r"20\d\d-(?:0[1-9]|1[0-2])(?:-\d\d)?",text):return text[:7]
 if re.fullmatch(r"(?:0?[1-9]|1[0-2])/20\d\d",text):
  m,y=text.split("/");return f"{int(y):04d}-{int(m):02d}"
 raise ValueError("Periodo debe ser AAAA-MM, fecha Excel o MM/AAAA: "+repr(text))

def amount(value):
 if isinstance(value,(int,float,Decimal)) and not isinstance(value,bool):return float(value)
 s=str(value or "").strip().replace("₡","").replace(" ","")
 if not s:raise ValueError("Valor vacío")
 if "," in s and "." in s:
  s=s.replace(".","").replace(",",".") if s.rfind(",")>s.rfind(".") else s.replace(",","")
 elif "," in s:
  parts=s.split(",")
  s=s.replace(",",".") if len(parts[-1]) in (1,2) else s.replace(",","")
 try:val=float(Decimal(s))
 except (InvalidOperation,ValueError):raise ValueError("Valor no numérico: "+repr(value))
 if not (-1e16<val<1e16):raise ValueError("Valor fuera de rango")
 return val

def ensure_url(url):
 u=urlparse(str(url or ""))
 if u.scheme!="https" or not (u.hostname in ("sugese.fi.cr","www.sugese.fi.cr","app.powerbi.com")):
  raise ValueError("Se requiere enlace oficial SUGESE o su Power BI público")
 return str(url)

def normalize(row):
 col={k:row.get(k) for k in ALIASES}
 p=valid_date(col["periodo"])
 if not p.startswith("2026-"):raise ValueError("Este pipeline recibe únicamente periodos 2026")
 metric=METRICS.get(clean(col["indicador"]))
 if not metric:raise ValueError("Indicador no reconocido: "+str(col["indicador"]))
 unit=clean(col["unidad"])
 if unit not in ("millones de colones","millones crc","millones de crc","millones colones"):
  raise ValueError("Unidad no compatible. Requiere 'millones CRC'; no se convierten colones sin metadatos")
 kind=clean(col["tipo_serie"])
 kind=kind.replace(" ","_")
 if kind not in ALLOWED:raise ValueError("Tipo de serie ambiguo: "+kind)
 company=str(col.get("aseguradora") or "Mercado").strip()
 branch=str(col.get("ramo") or "Todos").strip()
 if not company or not branch:raise ValueError("Entidad o ramo vacíos")
 return dict(periodo=p,aseguradora=company,ramo=branch,indicador=metric,valor=amount(col["valor"]),unidad="millones CRC",tipo_serie=kind,fuente_url=ensure_url(col["fuente_url"]))

def tabular_rows(table,name):
 it=iter(table)
 for index,head in enumerate(it):
  if index>24:raise ValueError(name+": encabezado reconocible no hallado en primeras 25 filas")
  m=mapping(head)
  if all(m[k] is not None for k in REQUIRED):break
 else:raise ValueError(name+": no hay encabezado con periodo, indicador, valor, unidad, tipo_serie, fuente_url")
 for n,row in enumerate(it,start=index+2):
  if not row or all(v is None or str(v).strip()=="" for v in row):continue
  obj={k:row[i] if i is not None and i<len(row) else None for k,i in m.items()}
  try:yield normalize(obj)
  except ValueError as e:raise ValueError(f"{name}, fila {n}: {e}")

def load(p):
 if p.suffix.lower()==".csv":
  txt=p.read_text(encoding="utf-8-sig")
  delimiter=";" if txt.splitlines()[0].count(";")>txt.splitlines()[0].count(",") else ","
  rows=csv.reader(io.StringIO(txt),delimiter=delimiter)
  return list(tabular_rows(rows,p.name))
 if p.suffix.lower()==".xlsx":
  from openpyxl import load_workbook
  wb=load_workbook(p,read_only=True,data_only=True)
  output=[]
  for ws in wb.worksheets:
   if ws.sheet_state!="visible":continue
   try: output+=list(tabular_rows(ws.iter_rows(values_only=True),p.name+" / "+ws.title))
   except ValueError as e:
    if "encabezado" in str(e):continue
    raise
  wb.close()
  if not output:raise ValueError(p.name+": no se hallaron hojas normalizadas exportables")
  return output
 raise ValueError("Tipo no permitido")

def main():
 files=sorted(p for p in INCOMING.glob("*") if p.suffix.lower() in (".csv",".xlsx") and not p.name.startswith("."))
 if not files:raise SystemExit("No hay exportaciones en incoming/; no se publicó una serie ficticia")
 rows=[]; inputs=[]
 for p in files:
  r=load(p);rows+=r;inputs.append({"archivo":p.name,"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"registros":len(r)})
 if not rows:raise SystemExit("No se identificaron filas")
 by={};duplicates=0
 for row in rows:
  key=tuple(row[k] for k in ("periodo","aseguradora","ramo","indicador","tipo_serie","unidad"))
  if key in by:
   if by[key]["valor"]!=row["valor"]:raise ValueError("Valores contradictorios de una misma clave "+str(key))
   duplicates+=1
  by[key]=row
 validated=list(by.values())
 # Conciliación condicional SOLO cuando existen mercado+entidades de una misma métrica/periodo/ramo.
 checked=[]
 keys={(r["periodo"],r["ramo"],r["indicador"],r["tipo_serie"]) for r in validated}
 for p,branch,metric,kind in sorted(keys):
  part=[r for r in validated if (r["periodo"],r["ramo"],r["indicador"],r["tipo_serie"])==(p,branch,metric,kind)]
  total=[r for r in part if clean(r["aseguradora"]) in ("mercado","total","total mercado")]
  ins=[r for r in part if r not in total]
  if len(total)==1 and len(ins)>=2:
   diff=abs(sum(r["valor"] for r in ins)-total[0]["valor"])
   tol=max(0.05,abs(total[0]["valor"])*0.005)
   if diff>tol:raise ValueError(f"Falla conciliación {p}/{branch}/{metric}: diferencia {diff} superior a tolerancia {tol}")
   checked.append({"periodo":p,"ramo":branch,"indicador":metric,"tipo_serie":kind,"tolerancia":tol,"diferencia":diff})
 meta={
  "origen":"Exportaciones oficiales SUGESE aportadas a incoming/",
  "estado":"conciliado_con_totales" if checked else "validado_estructuralmente_sin_conciliacion_externa",
  "nivel":"No sustituye revisión de metodología de boletín ni valida fecha de publicación",
  "procesado_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),
  "unidad":"millones CRC", "periodo_maximo":max(r["periodo"] for r in validated),
  "archivos":inputs,"conciliaciones":checked,"filas":len(validated),"duplicados_identicos_omitidos":duplicates,
  "nota":"No infiere cambio porcentual entre tipos de serie distintos. Revisar unidades del reporte fuente."
 }
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps({"meta":meta,"series":validated},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(f"Importadas {len(validated)} filas; corte {meta['periodo_maximo']}; validación: {meta['estado']}")
if __name__=="__main__":
 try:main()
 except (ValueError,KeyError) as exc:
  print("ERROR DE CALIDAD DE DATOS:",exc,file=sys.stderr)
  sys.exit(1)
