"""
datos_etiquetados.py — Carga de los sets con etiqueta exacta de estudio.

  datos/suite_etiquetada.csv : casos de la suite de tests, con su preferred_term esperado
  datos/heldout.csv          : held-out 1, mensajes nuevos (ya usado para elegir la
                               configuración: no se evalúa más contra él)
  datos/heldout2.csv         : held-out 2, para una única evaluación final. No está en
                               SETS: solo lo cargan verificar_heldout y evaluar_heldout2.

La columna `esperado` es un preferred_term exacto del catálogo, "AMBIGUO"
(hay que pedir aclaración) o "null" (no corresponde ningún estudio).
`tipo_ambiguedad` (solo en los AMBIGUO):
  falta_lado     zona par sin lado (hombro, pie, cadera, rodilla, mano, codo, muñeca, tobillo)
  falta_segmento columna o espalda sin segmento (cervical, dorsal, lumbar)
  zona_amplia    zona mencionada pero amplia (pierna, brazo, huesos largos)
  falta_zona     sin zona ("rx", "necesito una radiografía", "todo el cuerpo")
No cambia la accuracy; sirve para el diálogo y para el F1 de AMBIGUO por tipo.
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
CSV_HELDOUT2 = os.path.join(DIR_DATOS, "heldout2.csv")

CLASE_AMBIGUO = "AMBIGUO"
CLASE_NULL = "null"
TIPOS_AMBIGUEDAD = ("falta_lado", "falta_segmento", "zona_amplia", "falta_zona")


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
        fila["tipo_ambiguedad"] = fila.get("tipo_ambiguedad", "").strip()
    return filas


def errores_tipo_ambiguedad(filas: list[dict]) -> list[tuple[str, str]]:
    """(id, problema) de las filas con tipo_ambiguedad faltante, inválido o en un caso no AMBIGUO."""
    errores = []
    for f in filas:
        t = f["tipo_ambiguedad"]
        if f["esperado"] == CLASE_AMBIGUO and t not in TIPOS_AMBIGUEDAD:
            errores.append((f["id"], f"AMBIGUO con tipo_ambiguedad {t!r}"))
        elif f["esperado"] != CLASE_AMBIGUO and t:
            errores.append((f["id"], f"tipo_ambiguedad {t!r} en un caso que no es AMBIGUO"))
    return errores


def cargar_suite_etiquetada() -> list[dict]:
    """Casos de la suite con etiqueta exacta. Incluye el caso original (para la métrica laxa)."""
    casos_por_id = {c["id"]: c for c in CASOS}
    filas = _leer(CSV_SUITE)
    for fila in filas:
        fila["set"] = "suite"
        fila["caso_suite"] = casos_por_id[fila["id"]]
    return filas


def cargar_heldout(ruta: str = CSV_HELDOUT, nombre_set: str = "heldout") -> list[dict]:
    filas = _leer(ruta)
    for fila in filas:
        fila["set"] = nombre_set
        fila["grupo"] = fila.pop("categoria")
        fila["claves_laxas"] = [c.strip() for c in fila.get("clave_laxa", "").split("|") if c.strip()]
    return filas


def cargar_heldout2() -> list[dict]:
    return cargar_heldout(CSV_HELDOUT2, "heldout2")


SETS = {"suite": cargar_suite_etiquetada, "heldout": cargar_heldout}
