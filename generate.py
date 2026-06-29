#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera la edición del día de "Geopolitics for Pirates".

Uso:
    python generate.py <salida.html> [<resumen.txt>]

Requisitos:
    - Variable de entorno ANTHROPIC_API_KEY con tu clave de la API de Anthropic.
    - Archivos 'template.html' e 'instructions.md' en la misma carpeta que este script.

El día de la semana decide el tipo de edición:
    - Lunes / Miércoles / Viernes -> edición ordinaria
    - Domingo                     -> edición dominical (más profunda + conclusiones)
    - Otros días                  -> ordinaria (fuera de cadencia)
"""

import os
import re
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("GFP_MODEL", "claude-sonnet-4-6")
MAX_TOKENS = int(os.environ.get("GFP_MAX_TOKENS", "32000"))

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def here(name):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)


def read(name):
    with open(here(name), "r", encoding="utf-8") as f:
        return f.read()


def edition_type(weekday):
    # weekday(): lunes=0 ... domingo=6
    if weekday == 6:
        return "dominical"
    return "ordinaria"


def build_request(template, instructions, now):
    weekday = now.weekday()
    tipo = edition_type(weekday)
    fecha_es = "%s %d de %s de %d" % (DIAS[weekday], now.day, MESES[now.month - 1], now.year)

    preamble = (
        "Hoy es %s. Produce la edición %s de hoy de la revista.\n\n"
        "Reglas de salida CRÍTICAS:\n"
        "- Devuelve ÚNICAMENTE el archivo HTML completo, empezando por <!DOCTYPE html> y terminando en </html>.\n"
        "- Sin texto antes ni después, sin comentarios, sin vallas de código markdown.\n"
        "- Parte de la plantilla que se incluye más abajo y conserva su diseño BYTE A BYTE: no cambies el CSS, las fuentes, el SVG de la calavera ni los scripts.\n"
        "- Cambia SOLO el contenido editorial (las secciones), los sellos de fecha (brief-stamp, estado del mar, footer) y la etiqueta del número.\n"
        "- Antes de escribir, busca en la web las noticias reales de hoy por los frentes indicados y parafrasea con voz propia (cero citas largas).\n"
    ) % (fecha_es, tipo)

    if tipo == "dominical":
        preamble += (
            "\nEsta es la EDICIÓN DOMINICAL: La Carta pasa a 2-3 lecturas largas, El Horizonte gana profundidad, "
            "y AÑADE una sección nueva 'El Cuaderno · Conclusiones de la semana' (id=\"cuaderno\") antes de El Cofre, "
            "con su entrada en el índice y en el menú. La etiqueta del número dice 'Edición Dominical'.\n"
        )

    system = instructions + "\n\n" + preamble
    user = (
        "PLANTILLA (no alteres su diseño, solo su contenido editorial y los sellos de fecha):\n\n"
        "===== INICIO PLANTILLA =====\n" + template + "\n===== FIN PLANTILLA =====\n\n"
        "Genera ahora el HTML completo de la edición de hoy."
    )

    body = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": system,
        "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}],
        "messages": [{"role": "user", "content": user}],
    }
    return body, tipo, fecha_es


def call_api(body):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        sys.exit("ERROR: falta la variable de entorno ANTHROPIC_API_KEY.")
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(API_URL, data=data, method="POST")
    req.add_header("content-type", "application/json")
    req.add_header("x-api-key", key)
    req.add_header("anthropic-version", "2023-06-01")
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        sys.exit("ERROR API %s: %s" % (e.code, e.read().decode("utf-8", "replace")))
    except Exception as e:  # noqa
        sys.exit("ERROR de red: %s" % e)


def extract_html(resp):
    parts = []
    for block in resp.get("content", []):
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
    text = "\n".join(parts)
    start = text.find("<!DOCTYPE")
    end = text.rfind("</html>")
    if start == -1 or end == -1:
        sys.exit("ERROR: la respuesta no contenía un HTML completo.")
    return text[start:end + len("</html>")]


def validate(html):
    needles = ["Geopolitics for Pirates", "<style>", 'id="vigia"', "</html>"]
    missing = [n for n in needles if n not in html]
    if missing:
        sys.exit("ERROR: HTML sin elementos esperados: %s" % ", ".join(missing))


def lead_headline(html):
    m = re.search(r'id="vigia".*?<h3>(.*?)</h3>', html, re.DOTALL)
    if m:
        return re.sub(r"<[^>]+>", "", m.group(1)).strip()
    return ""


def main():
    if len(sys.argv) < 2:
        sys.exit("Uso: python generate.py <salida.html> [<resumen.txt>]")
    out_html = sys.argv[1]
    out_summary = sys.argv[2] if len(sys.argv) > 2 else None

    template = read("template.html")
    instructions = read("instructions.md")
    now = datetime.now()

    body, tipo, fecha_es = build_request(template, instructions, now)
    resp = call_api(body)
    html = extract_html(resp)
    validate(html)

    os.makedirs(os.path.dirname(os.path.abspath(out_html)), exist_ok=True)
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)

    headline = lead_headline(html)
    summary = "Edición %s del %s. %s" % (tipo, fecha_es, ("Titular: " + headline) if headline else "")
    summary = summary.strip()
    print(summary)
    if out_summary:
        with open(out_summary, "w", encoding="utf-8") as f:
            f.write(summary)


if __name__ == "__main__":
    main()
