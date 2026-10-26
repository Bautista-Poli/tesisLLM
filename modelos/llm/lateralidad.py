"""
lateralidad.py — Regla post-LLM de lateralidad (opcional, apagada por defecto).

Si el estudio predicho es de una zona par (hombro, pie, cadera, rodilla, mano, codo,
muñeca, tobillo, dedos) y el mensaje no dice el lado (derecho / izquierdo / ambos)
ni nombra la zona en plural, el estudio pasa a AMBIGUO con tipo_ambiguedad =
falta_lado. Si el preferred_term del estudio ya tiene lado, la regla no aplica.

Se activa con ExtractorLLM(regla_lateralidad=True) o, en la evaluación, con la
configuración j) de comparar_configuraciones.
"""

from __future__ import annotations

import re
import unicodedata

AMBIGUO = "AMBIGUO"
FALTA_LADO = "falta_lado"

# Zona par -> (patrón singular o plural, patrón plural), sobre texto sin tildes.
# "los dedos" no indica ambos lados (son varios dedos de una mano o pie); "pulgares" sí.
ZONAS_PARES = {
    "hombro":  (r"\bhombros?\b", r"\bhombros\b"),
    "pie":     (r"\bpies?\b", r"\bpies\b"),
    "cadera":  (r"\bcaderas?\b", r"\bcaderas\b"),
    "rodilla": (r"\brodillas?\b", r"\brodillas\b"),
    "mano":    (r"\bmanos?\b", r"\bmanos\b"),
    "codo":    (r"\bcodos?\b", r"\bcodos\b"),
    "muñeca":  (r"\bmunecas?\b", r"\bmunecas\b"),
    "tobillo": (r"\btobillos?\b", r"\btobillos\b"),
    "dedos":   (r"\b(dedos?|pulgar(es)?)\b", r"\bpulgares\b"),
}
LADOS = {
    "derecho":   r"\b(derech\w*|dcha|der)\b",
    "izquierdo": r"\b(izquierd|isquierd|izq)\w*",
    "ambos":     r"\b(ambos|ambas|bilateral(es)?|dos)\b",
}


def normalizar(texto: str | None) -> str:
    """Minúsculas y sin tildes."""
    t = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def zonas_pares(texto: str) -> list[str]:
    t = normalizar(texto)
    return [z for z, (patron, _) in ZONAS_PARES.items() if re.search(patron, t)]


def menciona_lado(texto: str) -> bool:
    t = normalizar(texto)
    return any(re.search(p, t) for p in LADOS.values())


def menciona_plural(texto: str, zonas: list[str]) -> bool:
    t = normalizar(texto)
    return any(re.search(ZONAS_PARES[z][1], t) for z in zonas)


def falta_lado(estudio: str | None, texto: str) -> bool:
    """True si la regla convierte este estudio en AMBIGUO para este mensaje."""
    if not estudio or estudio == AMBIGUO:
        return False
    zonas = zonas_pares(estudio)
    if not zonas or menciona_lado(estudio):
        return False
    return not menciona_lado(texto) and not menciona_plural(texto, zonas)


def aplicar_a_clase(clase: str, texto: str) -> tuple[str, str]:
    """
    Versión para la evaluación, sobre la clase predicha (preferred_term, "AMBIGUO" o "null").
    Devuelve (clase, tipo_ambiguedad), con tipo "" si la regla no aplica.
    """
    if falta_lado(clase, texto):
        return AMBIGUO, FALTA_LADO
    return clase, ""


def aplicar_a_slots(slots: dict, texto: str) -> dict:
    """Versión para el pipeline: modifica y devuelve los slots del extractor."""
    if not slots.get("estudio_ambiguo") and falta_lado(slots.get("estudio"), texto):
        slots["estudio"] = None
        slots["estudio_ambiguo"] = True
        slots["tipo_ambiguedad"] = FALTA_LADO
    return slots
