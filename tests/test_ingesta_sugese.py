"""Pruebas con datos ficticios aislados; nunca se publican en el observatorio."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"ingestar_sugese.py"
spec=importlib.util.spec_from_file_location("ingestar_sugese",SCRIPT)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

URL="https://www.sugese.fi.cr/cr/es/estadisticas.html"
HEADER="periodo,aseguradora,ramo,indicador,valor,unidad,tipo_serie,fuente_url\n"

class Tests(unittest.TestCase):
 def test_campos_minimos(self):
  row={"periodo":"2026-09","aseguradora":"Mercado","ramo":"Todos",
       "indicador":"primas emitidas","valor":"1200","unidad":"millones CRC",
       "tipo_serie":"acumulado_anual","fuente_url":URL}
  self.assertEqual(module.normalize(row)["valor"],1200)
  self.assertEqual(module.normalize(row)["tipo_serie"],"acumulado_anual")
 def test_rechaza_unidad_ambigua(self):
  row={"periodo":"2026-09","aseguradora":"Mercado","ramo":"Todos",
       "indicador":"primas emitidas","valor":"1200","unidad":"colones",
       "tipo_serie":"mensual","fuente_url":URL}
  with self.assertRaises(ValueError):module.normalize(row)
 def test_rechaza_fuente_no_oficial(self):
  with self.assertRaises(ValueError):module.ensure_url("https://ejemplo.com/datos.csv")
 def test_archivo_completo(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)
   incoming=root/"incoming";incoming.mkdir()
   rows=[
    "2026-08,Mercado,Todos,primas emitidas,900,millones CRC,acumulado_anual,"+URL,
    "2026-09,Mercado,Todos,primas emitidas,1000,millones CRC,acumulado_anual,"+URL,
    "2026-09,INS,Todos,primas emitidas,700,millones CRC,acumulado_anual,"+URL,
    "2026-09,ASSA,Todos,primas emitidas,300,millones CRC,acumulado_anual,"+URL,
   ]
   (incoming/"test.csv").write_text(HEADER+"\n".join(rows)+"\n",encoding="utf-8")
   with patch.object(module,"INCOMING",incoming),patch.object(module,"OUT",root/"data"/"series_sugese.json"):
    module.main()
   import json
   data=json.loads((root/"data"/"series_sugese.json").read_text(encoding="utf-8"))
   self.assertEqual(data["meta"]["estado"],"conciliado_con_totales")
   self.assertEqual(len(data["series"]),4)
if __name__=="__main__":unittest.main()
