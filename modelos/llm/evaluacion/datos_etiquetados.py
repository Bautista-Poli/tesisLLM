"""
datos_etiquetados.py — Carga de los sets con etiqueta exacta de estudio.

  datos/suite_etiquetada.csv : casos de la suite de tests, con su preferred_term esperado
  datos/heldout.csv          : mensajes nuevos, no usados para desarrollar el sistema

La columna `esperado` es un preferred_term exacto del catálogo, "AMBIGUO"
(hay que pedir aclaración) o "null" (no corresponde ningún estudio).
Ambos sets se cargan con el mismo formato: id, grupo, input, ultima_pregunta,
esperado, revisar, nota y los datos necesarios para la métrica laxa.
"""

from __future__ import annotations

import csv
import os
import re
import unicodedata

from modelos.llm.evaluacion.comun import CASOS

DIR_DATOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos")
CSV_SUITE = os.path.join(DIR_DATOS, "suite_etiquetada.csv")
CSV_HELDOUT = os.path.join(DIR_DATOS, "heldout.csv")

CLASE_AMBIGUO = "AMBIGUO"
CLASE_NULL = "null"


def normalizar(texto: str | None) -> str:
    """Minúsculas, sin tildes y con espacios simples (para comparar textos)."""
    sin_tildes = unicodedata.normalize("NFKD", (texto or "").lower())
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sin_tildes).strip()


def _leer(ruta: str) -> list[dict]:
    with open(ruta, newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    for fila in filas:
        fila["revisar"] = fila.get("revisar", "").strip().lower() == "true"
        fila["esperado"] = fila["esperado"].strip()
    return filas


def cargar_suite_etiquetada() -> list[dict]:
    """Casos de la suite con etiqueta exacta. Incluye el caso original (para la métrica laxa)."""
    casos_por_id = {c["id"]: c for c in CASOS}
    filas = _leer(CSV_SUITE)
    for fila in filas:
        fila["set"] = "suite"
        fila["caso_suite"] = casos_por_id[fila["id"]]
    return filas


def cargar_heldout() -> list[dict]:
    filas = _leer(CSV_HELDOUT)
    for fila in filas:
        fila["set"] = "heldout"
        fila["grupo"] = fila.pop("categoria")
        fila["claves_laxas"] = [c.strip() for c in fila.get("clave_laxa", "").split("|") if c.strip()]
    return filas


SETS = {"suite": cargar_suite_etiquetada, "heldout": cargar_heldout}
