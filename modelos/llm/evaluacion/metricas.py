"""
metricas.py — Métricas de estudio sobre los sets etiquetados.

Predicción como clase
---------------------
Cada configuración produce una clase por mensaje:
  - un preferred_term (texto exacto),
  - "AMBIGUO" si el sistema marca estudio_ambiguo,
  - "null" si no extrae estudio.

Métrica estricta
----------------
  - accuracy top-1: predicción == esperado (texto exacto).
  - P/R/F1 macro sobre las clases del gold más AMBIGUO y null, que se incluyen
    siempre (aunque no se predigan ni aparezcan en el gold; una clase sin
    aciertos aporta 0).
  - P/R/F1 de las clases AMBIGUO y null por separado.

Métrica laxa (la anterior, para comparar)
-----------------------------------------
  - suite:   el estudio cumple los checks de "estudio" del caso de test.
  - heldout: el estudio contiene alguna de las claves de `clave_laxa`;
             si se espera AMBIGUO o null, el estudio debe ser nulo.
  precisión = correctos / salidas con estudio (en casos con gold)
  recall    = correctos / casos que esperan un estudio
"""

from __future__ import annotations

from collections import defaultdict

from modelos.llm.evaluacion.comun import NEGATIVO, POSITIVO, es_correcto, tipo_gold
from modelos.llm.evaluacion.datos_etiquetados import CLASE_AMBIGUO, CLASE_NULL


def clase_desde_slots(slots: dict) -> str:
    if slots.get("estudio_ambiguo"):
        return CLASE_AMBIGUO
    return slots.get("estudio") or CLASE_NULL


def es_termino(clase: str) -> bool:
    return clase not in (CLASE_AMBIGUO, CLASE_NULL)


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def metricas_estrictas(esperados: list[str], predichos: list[str]) -> dict:
    conteo = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    for e, p in zip(esperados, predichos):
        if e == p:
            conteo[e]["tp"] += 1
        else:
            conteo[p]["fp"] += 1
            conteo[e]["fn"] += 1

    clases = sorted(set(esperados) | {CLASE_AMBIGUO, CLASE_NULL})
    por_clase = {c: _prf(**conteo[c]) for c in clases}
    n = len(esperados)
    return {
        "n": n,
        "n_clases": len(clases),
        "accuracy": sum(e == p for e, p in zip(esperados, predichos)) / n if n else 0.0,
        "macro_p": sum(v[0] for v in por_clase.values()) / len(por_clase) if por_clase else 0.0,
        "macro_r": sum(v[1] for v in por_clase.values()) / len(por_clase) if por_clase else 0.0,
        "macro_f1": sum(v[2] for v in por_clase.values()) / len(por_clase) if por_clase else 0.0,
        "ambiguo": _prf(**conteo[CLASE_AMBIGUO]),
        "null": _prf(**conteo[CLASE_NULL]),
    }


def gold_laxo(item: dict) -> str | None:
    if item["set"] == "suite":
        return tipo_gold(item["caso_suite"])
    return POSITIVO if es_termino(item["esperado"]) else NEGATIVO


def correcto_laxo(item: dict, prediccion: str) -> bool:
    estudio = prediccion if es_termino(prediccion) else None
    if item["set"] == "suite":
        return es_correcto(item["caso_suite"], estudio)
    if not es_termino(item["esperado"]):
        return estudio is None
    return estudio is not None and any(c in estudio.lower() for c in item["claves_laxas"])


def metricas_laxas(items: list[dict], predichos: list[str]) -> dict:
    positivos = predichos_con_estudio = correctos = 0
    for item, pred in zip(items, predichos):
        gold = gold_laxo(item)
        if gold is None:
            continue
        if gold == POSITIVO:
            positivos += 1
            correctos += correcto_laxo(item, pred) and es_termino(pred)
        if es_termino(pred):
            predichos_con_estudio += 1
    p = correctos / predichos_con_estudio if predichos_con_estudio else 0.0
    r = correctos / positivos if positivos else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"p": p, "r": r, "f1": f}
