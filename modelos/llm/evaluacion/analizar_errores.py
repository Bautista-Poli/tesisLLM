"""
analizar_errores.py — Clasificación de los errores de una configuración sobre un set.

Lee las predicciones de resultados/comparacion_por_caso.csv (no llama al LLM) y
clasifica cada error en una sola categoría, con esta precedencia:

  (f) parseo:                  la salida del LLM no se pudo parsear
  (c) debía ser AMBIGUO:       esperado AMBIGUO, predijo otra cosa
  (a) no estaba en candidatos: esperado un término que no está en el contexto recuperado
  (d) AMBIGUO sin serlo:       predijo AMBIGUO y se esperaba un término o null
  (e) null mal:                predijo null esperando un término, o un término esperando null
  (b) estaba y eligió otro:    el término esperado estaba en los candidatos y eligió otro término

Uso:
    python -m modelos.llm.evaluacion.analizar_errores                  # config d, suite
    python -m modelos.llm.evaluacion.analizar_errores --config f --set suite
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from collections import Counter

from modelos.llm.evaluacion.comun import asegurar_dir_resultados, tipo_error
from modelos.llm.evaluacion.datos_etiquetados import CLASE_AMBIGUO, CLASE_NULL, SETS
from modelos.llm.extractor import CSV_TERMINOS
from modelos.llm.rag import buscar_terminos_relevantes, cargar_terminos

CATEGORIAS = {
    "a": "correcto no estaba en los candidatos",
    "b": "estaba en los candidatos y eligió otro",
    "c": "debía ser AMBIGUO",
    "d": "marcó AMBIGUO sin serlo",
    "e": "null mal",
    "f": "parseo",
}
_RE_TERMINO = re.compile(r'preferred_term: "(.*?)"')
ANALIZADOR_POR_CONFIG = {"c": "palabras", "d": "char", "f": "char", "g": "char", "i": "char"}


def clasificar(esperado: str, pred: str, candidatos: list[str], error: str) -> str:
    if tipo_error(error) == "parseo":
        return "f"
    if esperado == CLASE_AMBIGUO:
        return "c"
    es_termino = esperado not in (CLASE_AMBIGUO, CLASE_NULL)
    if es_termino and esperado not in candidatos:
        return "a"
    if pred == CLASE_AMBIGUO:
        return "d"
    if pred == CLASE_NULL or esperado == CLASE_NULL:
        return "e"
    return "b"


def main() -> None:
    parser = argparse.ArgumentParser(description="Clasificación de errores de una configuración.")
    parser.add_argument("--config", default="d")
    parser.add_argument("--set", default="suite", choices=list(SETS))
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    d = asegurar_dir_resultados()
    with open(os.path.join(d, "comparacion_por_caso.csv"), newline="", encoding="utf-8") as f:
        filas = [r for r in csv.DictReader(f) if r["config"] == args.config and r["set"] == args.set]
    if not filas:
        raise SystemExit(f"No hay predicciones de la config {args.config} en {args.set}")

    df = cargar_terminos(CSV_TERMINOS)
    analizador = ANALIZADOR_POR_CONFIG.get(args.config, "char")
    errores = []
    for r in filas:
        if r["prediccion"] == r["esperado"]:
            continue
        candidatos = _RE_TERMINO.findall(buscar_terminos_relevantes(r["input"], df, args.k, analizador))
        cat = clasificar(r["esperado"], r["prediccion"], candidatos, r["error"])
        errores.append({**{k: r[k] for k in ("id", "grupo", "input", "esperado", "prediccion", "error")},
                        "categoria": cat, "categoria_desc": CATEGORIAS[cat],
                        "esperado_en_candidatos": r["esperado"] in candidatos,
                        "candidatos": " | ".join(candidatos)})

    conteo = Counter(e["categoria"] for e in errores)
    lineas = [f"# Errores de la config {args.config} en {args.set}", "",
              f"{len(errores)} errores en {len(filas)} casos (accuracy {1 - len(errores) / len(filas):.2f}). "
              f"Candidatos: TF-IDF {analizador}, k={args.k}, tras el filtro de rag.py.", "",
              "| Categoría | Cantidad | Ejemplos (input → predicho / esperado) |", "|---|---|---|"]
    for cat, desc in CATEGORIAS.items():
        ej = [e for e in errores if e["categoria"] == cat][:3]
        ejemplos = "<br>".join(f"«{e['input'][:60]}» → {e['prediccion'][:55]} / {e['esperado'][:55]}" for e in ej)
        lineas.append(f"| ({cat}) {desc} | {conteo.get(cat, 0)} | {ejemplos or '—'} |")
    markdown = "\n".join(lineas) + "\n"
    print(markdown)

    base = os.path.join(d, f"errores_{args.config}_{args.set}")
    with open(base + ".md", "w", encoding="utf-8") as f:
        f.write(markdown)
    if errores:
        with open(base + ".csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(errores[0]))
            w.writeheader()
            w.writerows(errores)
    print(f"  Detalle: {os.path.relpath(base)}.csv / .md\n")


if __name__ == "__main__":
    main()
