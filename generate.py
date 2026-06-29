#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera la edición del día de Geopolitics for Pirates (Claude + streaming)."""

import os, re, sys, json
import urllib.request, urllib.error
from datetime import datetime

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("GFP_MODEL", "claude-opus-4-8")
MAX_TOKENS = int(os.environ.get("GFP_MAX_TOKENS", "32000"))

DIAS = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]
MESES = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto",
         "septiembre","octubre","noviembre","diciembre"]

def here(n): return os.path.join(os.path.dirname(os.path.abspath(__file__)), n)
def read(n):
    with open(here(n), "r", encoding="utf-8") as f: return f.read()

def build_request(template, instructions, now):
    wd = now.weekday()
    tipo = "dominical" if wd == 6 else "ordinaria"
    fecha = "%s %d de %s de %d" % (DIAS[wd], now.day, MESES[now.month-1], now.year)
    pre = (
        "Hoy es %s. Produce la edición %s de hoy de la revista.\n\n"
        "Reglas de salida CRÍTICAS:\n"
        "- Devuelve ÚNICAMENTE el HTML completo, de <!DOCTYPE html> a </html>.\n"
        "- Sin texto antes ni después, sin vallas de código markdown.\n"
        "- Parte de la plantilla de abajo y conserva su diseño BYTE A BYTE: no cambies CSS, fuentes, SVG ni scripts.\n"
        "- Cambia SOLO el contenido editorial, los sellos de fecha y la etiqueta del número.\n"
        "- Antes de escribir, BUSCA EN LA WEB las noticias reales de hoy y parafrasea con voz propia.\n"
    ) % (fecha, tipo)
    if tipo == "dominical":
        pre += ("\nEDICIÓN DOMINICAL: La Carta a 2-3 lecturas largas, El Horizonte más profundo, "
                "y AÑADE 'El Cuaderno · Conclusiones de la semana' (id=\"cuaderno\") antes de El Cofre, "
                "con su entrada en índice y menú. La etiqueta del número dice 'Edición Dominical'.\n")
    system = instructions + "\n\n" + pre
    user = ("PLANTILLA (no alteres su diseño):\n\n===== INICIO =====\n" + template +
            "\n===== FIN =====\n\nGenera ahora el HTML completo de la edición de hoy.")
    body = {
        "model": MODEL, "max_tokens": MAX_TOKENS, "stream": True,
        "system": system,
        "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}],
        "messages": [{"role": "user", "content": user}],
    }
    return body, tipo, fecha

def call_stream(body):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key: sys.exit("ERROR: falta ANTHROPIC_API_KEY.")
    req = urllib.request.Request(API_URL, data=json.dumps(body).encode("utf-8"), method="POST")
    req.add_header("content-type", "application/json")
    req.add_header("x-api-key", key)
    req.add_header("anthropic-version", "2023-06-01")
    parts = []
    try:
        with urllib.request.urlopen(req, timeout=1800) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"): continue
                try: evt = json.loads(line[5:].strip())
                except Exception: continue
                t = evt.get("type")
                if t == "content_block_delta" and evt.get("delta", {}).get("type") == "text_delta":
                    parts.append(evt["delta"].get("text", ""))
                elif t == "message_stop":
                    break
                elif t == "error":
                    sys.exit("ERROR API: %s" % json.dumps(evt.get("error", {})))
    except urllib.error.HTTPError as e:
        sys.exit("ERROR API %s: %s" % (e.code, e.read().decode("utf-8", "replace")))
    except Exception as e:
        sys.exit("ERROR de red: %s" % e)
    return "".join(parts)

def extract_html(text):
    s, e = text.find("<!DOCTYPE"), text.rfind("</html>")
    if s == -1 or e == -1: sys.exit("ERROR: respuesta sin HTML completo.")
    return text[s:e+len("</html>")]

def validate(html):
    miss = [n for n in ["Geopolitics for Pirates","<style>",'id="vigia"',"</html>"] if n not in html]
    if miss: sys.exit("ERROR: faltan elementos: %s" % ", ".join(miss))

def lead(html):
    m = re.search(r'id="vigia".*?<h3>(.*?)</h3>', html, re.DOTALL)
    return re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""

def main():
    if len(sys.argv) < 2: sys.exit("Uso: python generate.py <salida.html> [<resumen.txt>]")
    out, summ = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else None)
    body, tipo, fecha = build_request(read("template.html"), read("instructions.md"), datetime.now())
    html = extract_html(call_stream(body)); validate(html)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f: f.write(html)
    h = lead(html)
    s = ("Edición %s del %s. %s" % (tipo, fecha, ("Titular: " + h) if h else "")).strip()
    print(s)
    if summ:
        with open(summ, "w", encoding="utf-8") as f: f.write(s)

if __name__ == "__main__":
    main()
    
