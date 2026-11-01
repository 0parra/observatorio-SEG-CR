#!/usr/bin/env python3
"""Monitor diario de publicaciones oficiales SUGESE.

No extrae cifras de Power BI ni infiere valores de los PDF. Mantiene un estado
trazable, validando el dominio y descubriendo boletines enlazados públicamente.
"""
from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "data" / "estado_fuentes.json"
INDEX = "https://www.sugese.fi.cr/cr/es/estadisticas.html"
BULLETIN_2025 = "https://www.sugese.fi.cr/seccion-estadistica/Boletines/boletin_dic_2025.pdf"
SITEMAP = "https://www.sugese.fi.cr/sitemap.xml"
MAX_BYTES = 3_500_000
UA = "Observatorio-SUGESE/1.0 (fuentes publicas; github.com/0parra/observatorio-SEG-CR)"
REPORTS = {
    "Primas y siniestros": "https://app.powerbi.com/view?r=eyJrIjoiNzY4OWNlNjItM2Y5ZC00ZDUxLWI3ODgtMGNmZTE1M2MyNmIwIiwidCI6IjYxOGQwYTQ1LTI1YTYtNDYxOC05ZjgwLThmNzBhNDM1ZWU1MiJ9",
    "Ratio combinado": "https://app.powerbi.com/view?r=eyJrIjoiOGE4OTM2ZDYtZTViOS00ZjIyLTg5MzctNWI5ODRmMGY1ZDBkIiwidCI6IjYxOGQwYTQ1LTI1YTYtNDYxOC05ZjgwLThmNzBhNDM1ZWU1MiJ9",
    "Resultado técnico-financiero": "https://app.powerbi.com/view?r=eyJrIjoiMDk0OGE3NWYtZWYwNy00ZjBjLWIyYTctMDU5OTI4NzY4MjM5IiwidCI6IjYxOGQwYTQ1LTI1YTYtNDYxOC05ZjgwLThmNzBhNDM1ZWU1MiJ9",
    "Suficiencia de capital": "https://app.powerbi.com/view?r=eyJrIjoiZTRjOGNmZmMtOGM0OS00MTEyLWFjMDAtNzllYjU0YWEwNjFkIiwidCI6IjYxOGQwYTQ1LTI1YTYtNDYxOC05ZjgwLThmNzBhNDM1ZWU1MiJ9",
}
class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag in {"a", "iframe"}:
            a = dict(attrs)
            link = a.get("href") or a.get("src")
            if link:
                self.links.append(link)

def safe_public_link(value: str, base: str = INDEX) -> str | None:
    url = urljoin(base, unescape(value).strip())
    p = urlparse(url)
    if p.scheme != "https" or p.hostname not in {"www.sugese.fi.cr", "sugese.fi.cr"}:
        return None
    if not (p.path.lower().endswith(".pdf") and "/boletines/" in p.path.lower()):
        return None
    return p._replace(fragment="", query="").geturl()

def pdf_links(html: str, base: str = INDEX) -> list[str]:
    parser = Links()
    parser.feed(html)
    # Algunas páginas integran los enlaces dentro de cadenas JS/JSON.
    raw = re.findall(r'(?:https://(?:www\.)?sugese\.fi\.cr)?/seccion-estadistica/Boletines/[^"\s<>]+?\.pdf', html, re.I)
    out = {x for value in parser.links + raw if (x := safe_public_link(value, base))}
    return sorted(out)

def get(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": UA, "Accept": "text/html, application/xml, application/pdf;q=0.8"})
    with urlopen(req, timeout=25) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        content = response.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            raise ValueError("La página supera el límite de descarga permitido")
        return content

def run():
    previous = {}
    if TARGET.exists():
        try:
            previous = json.loads(TARGET.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    errors = []
    scans = []
    links = set()
    digest = None
    # Solo fuentes públicas autorizadas. No se consulta API privada de Power BI.
    for name, url, kind in [
        ("Índice de estadísticas", INDEX, "html"),
        ("Mapa público del sitio", SITEMAP, "xml"),
        ("Boletín diciembre 2025", BULLETIN_2025, "pdf"),
    ]:
        try:
            body = get(url)
            sha = hashlib.sha256(body).hexdigest()
            scans.append({"nombre": name, "url": url, "resultado": "accesible", "sha256": sha})
            if name == "Índice de estadísticas":
                digest = sha
                links.update(pdf_links(body.decode("utf-8", errors="replace"), url))
            if kind == "xml":
                text = body.decode("utf-8", errors="replace")
                links.update(pdf_links(text, url))
                # En caso de sitemap XML, extraer locs del boletín sin crear links artificiales
                for v in re.findall(r"<loc>(.*?)</loc>", text, re.I | re.S):
                    if x := safe_public_link(v, url):
                        links.add(x)
        except (HTTPError, URLError, OSError, TimeoutError, ValueError, RuntimeError) as exc:
            msg = f"{name}: {type(exc).__name__}: {str(exc)[:150]}"
            errors.append(msg)
            scans.append({"nombre": name, "url": url, "resultado": "error", "detalle": msg})
    known = set(previous.get("boletines_detectados", []))
    links |= known
    newly = sorted(links - known)
    linked_2026 = [url for url in sorted(links) if re.search(r"2026", url)]
    state = {
        "revision_utc": now,
        "fuente": INDEX,
        "estado": "accesible" if digest else "error_indice",
        "sha256_indice": digest,
        "fuentes_consultadas": scans,
        "reportes_publicos_powerbi": REPORTS,
        "boletines_detectados": sorted(links),
        "nuevos_boletines": newly,
        "boletines_2026_encontrados": linked_2026,
        "errores": errors,
        "actualizacion_indicadores_2026": "pendiente: exportacion validada SUGESE o descarga oficial estructurada",
        "advertencia": "Revisión diaria de disponibilidad. SUGESE publica datos mensuales/trimestrales. Esta tarea NO transforma un cambio HTML ni un PDF nuevo en cifras verificadas.",
    }
    TARGET.parent.mkdir(exist_ok=True, parents=True)
    TARGET.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Revisión: {now} | índice: {state['estado']} | boletines vistos: {len(links)} | errores: {len(errors)}")
    if errors:
        print("\n".join(errors))
    # Fallar si el sitio principal no responde; mostrar error en GitHub Actions.
    if not digest:
        raise SystemExit("ERROR: El índice oficial no fue accesible; no se afirma haber verificado SUGESE.")

if __name__ == "__main__":
    run()
