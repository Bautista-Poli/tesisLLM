"""
comun.py — Utilidades compartidas por los scripts de evaluación del modelo LLM.

Gold de estudio
---------------
Los casos de test no guardan un preferred_term esperado sino checks (lambdas)
sobre el campo "estudio". Se reutilizan tal cual:
  - un valor es CORRECTO si cumple todos los checks de "estudio" del caso;
  - el caso es POSITIVO si None no los cumple (se espera un estudio),
    NEGATIVO si None los cumple (se espera null: zona ambigua, fuera de dominio),
    y SIN GOLD si no tiene checks de "estudio".
"""

from __future__ import annotations

import os
import re

from modelos.llm.tests.test_suite import TESTS

CASOS = TESTS
DIR_RESULTADOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resultados")

POSITIVO = "positivo"
NEGATIVO = "negativo"

# Calificadores que el modelo no debería agregar si el usuario no los mencionó
CALIFICADORES = {
    "lateralidad": {"derecho", "derecha", "izquierdo", "izquierda", "bilateral"},
    "seriada":     {"seriada", "seriado"},
    "en carga":    {"carga"},
}
# Palabras del usuario que cuentan como haber mencionado cada calificador
MENCIONES = {
    "lateralidad": CALIFICADORES["lateralidad"] | {"ambos", "ambas"},
    "seriada":     CALIFICADORES["seriada"],
    "en carga":    CALIFICADORES["en carga"],
}


def checks_estudio(caso: dict) -> list:
    return [esperado for campo, esperado, _ in caso["checks"] if campo == "estudio"]


def es_correcto(caso: dict, valor) -> bool:
    checks = checks_estudio(caso)
    return bool(checks) and all(
        bool(e(valor)) if callable(e) else valor == e for e in checks
    )


def tipo_gold(caso: dict) -> str | None:
    if not checks_estudio(caso):
        return None
    return NEGATIVO if es_correcto(caso, None) else POSITIVO


def _palabras(texto: str | None) -> set[str]:
    return set(re.findall(r"\w+", (texto or "").lower()))


def calificadores_no_mencionados(estudio: str | None, texto_usuario: str) -> list[str]:
    """Calificadores presentes en el estudio de salida que el usuario no mencionó."""
    if not estudio:
        return []
    salida = _palabras(estudio)
    usuario = _palabras(texto_usuario)
    return [
        nombre for nombre, palabras in CALIFICADORES.items()
        if salida & palabras and not usuario & MENCIONES[nombre]
    ]


def tipo_error(mensaje: str) -> str:
    """'' sin error, 'conexion' si falló Ollama, 'parseo' si la salida del LLM no se pudo leer."""
    if not mensaje:
        return ""
    if any(t in mensaje for t in ("Connection", "timed out", "HTTP", "Max retries")):
        return "conexion"
    return "parseo"


def asegurar_dir_resultados() -> str:
    os.makedirs(DIR_RESULTADOS, exist_ok=True)
    return DIR_RESULTADOS
