"""
evaluar_top_k.py — Evaluación del modelo LLM variando TOP_K de la recuperación.

No cambia el default del código (rag.TOP_K); el valor se pasa como parámetro.
Requiere Ollama corriendo.

Métricas por k:
  - recall@k (contexto):  en casos positivos, fracción donde algún candidato que
                          recibe el LLM (top-k tras el filtro de calificadores
                          técnicos de rag.py) es correcto.
  - recall@k (TF-IDF):    lo mismo sobre el top-k crudo, antes del filtro.
  - Precisión / Recall / F1 de estudio (salida del LLM):
        precisión = correctos / salidas con estudio no nulo (casos positivos y negativos)
        recall    = correctos / casos positivos
  - Salidas con calificadores no mencionados (lateralidad, "seriada", "en carga"),
    sobre todos los casos con estudio no nulo.

Uso:
    python -m modelos.llm.evaluacion.evaluar_top_k            # k = 3 y 5
    python -m modelos.llm.evaluacion.evaluar_top_k --k 3 5 7
    python -m modelos.llm.evaluacion.evaluar_top_k --grupo ambiguos
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from collections import Counter

from modelos.llm.evaluacion.comun import (
    CASOS, CALIFICADORES, NEGATIVO, POSITIVO,
    asegurar_dir_resultados, calificadores_no_mencionados, es_correcto, tipo_gold,
)
from modelos.llm.rag import (
    buscar_relevantes, buscar_terminos_relevantes, cargar_coberturas, cargar_terminos,
)
from modelos.llm.tests._runner import CSV_COBERTURAS, CSV_TERMINOS, extraer

_RE_TERMINO = re.compile(r'preferred_term: "(.*?)"')


def evaluar_k(k: int, casos: list, df_terminos, df_coberturas) -> tuple[dict, list]:
    filas = []
    for i, caso in enumerate(casos, 1):
        texto = caso["input"]
        gold = tipo_gold(caso)

        contexto = buscar_terminos_relevantes(texto, df_terminos, k)
        candidatos_ctx = _RE_TERMINO.findall(contexto)
        candidatos_raw = [df_terminos.iloc[j]["preferred_term"]
                          for j in buscar_relevantes(texto, df_terminos, k)]

        error = ""
        try:
            slots = extraer(
                texto,
                ultima_pregunta=caso.get("ultima_pregunta", ""),
                slots_llenos=caso.get("slots_llenos", []),
                df_terminos=df_terminos,
                df_coberturas=df_coberturas,
                top_k=k,
            )
            estudio = slots.get("estudio")
        except Exception as e:  # el caso cuenta como salida nula
            estudio, error = None, str(e)

        filas.append({
            "k": k,
            "id": caso["id"],
            "grupo": caso["grupo"],
            "gold": gold or "",
            "input": texto,
            "candidatos_contexto": " | ".join(candidatos_ctx),
            "hit_contexto": gold == POSITIVO and any(es_correcto(caso, c) for c in candidatos_ctx),
            "hit_tfidf": gold == POSITIVO and any(es_correcto(caso, c) for c in candidatos_raw),
            "estudio_salida": estudio or "",
            "correcto": gold == POSITIVO and estudio is not None and es_correcto(caso, estudio),
            "calificadores_no_mencionados": ",".join(calificadores_no_mencionados(estudio, texto)),
            "error": error,
        })
        print(f"  k={k}  [{i}/{len(casos)}] {caso['id']}", end="\r", flush=True)
    print(" " * 70, end="\r")
    return resumir(filas), filas


def resumir(filas: list) -> dict:
    positivos = [f for f in filas if f["gold"] == POSITIVO]
    con_gold = [f for f in filas if f["gold"] in (POSITIVO, NEGATIVO)]
    predichos = [f for f in con_gold if f["estudio_salida"]]
    correctos = sum(f["correcto"] for f in positivos)

    precision = correctos / len(predichos) if predichos else 0.0
    recall = correctos / len(positivos) if positivos else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    con_estudio = [f for f in filas if f["estudio_salida"]]
    con_calif = [f for f in con_estudio if f["calificadores_no_mencionados"]]
    por_tipo = Counter(c for f in con_calif for c in f["calificadores_no_mencionados"].split(","))

    return {
        "n_casos": len(filas),
        "n_positivos": len(positivos),
        "recall_contexto": sum(f["hit_contexto"] for f in positivos) / len(positivos) if positivos else 0.0,
        "recall_tfidf": sum(f["hit_tfidf"] for f in positivos) / len(positivos) if positivos else 0.0,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "n_con_estudio": len(con_estudio),
        "n_con_calificadores": len(con_calif),
        "calificadores": por_tipo,
        "errores": sum(1 for f in filas if f["error"]),
    }


def imprimir_resumen(resumenes: dict) -> None:
    print("\n" + "=" * 92)
    print("  EVALUACIÓN POR TOP_K — estudio")
    print("=" * 92)
    print(f"  {'k':>3} {'recall@k ctx':>13} {'recall@k tfidf':>15} {'Precisión':>10} {'Recall':>8} {'F1':>6}"
          f"  {'Calif. no mencionados':>22}  {'Errores':>7}")
    print(f"  {'-'*3} {'-'*13} {'-'*15} {'-'*10} {'-'*8} {'-'*6}  {'-'*22}  {'-'*7}")
    for k, r in resumenes.items():
        calif = f"{r['n_con_calificadores']}/{r['n_con_estudio']}"
        print(f"  {k:>3} {r['recall_contexto']:>13.2f} {r['recall_tfidf']:>15.2f} {r['precision']:>10.2f}"
              f" {r['recall']:>8.2f} {r['f1']:>6.2f}  {calif:>22}  {r['errores']:>7}")
    print()
    for k, r in resumenes.items():
        detalle = ", ".join(f"{nombre}: {r['calificadores'].get(nombre, 0)}" for nombre in CALIFICADORES)
        print(f"  k={k}  calificadores no mencionados → {detalle}")
    r0 = next(iter(resumenes.values()))
    print(f"\n  Casos: {r0['n_casos']}  |  positivos (esperan estudio): {r0['n_positivos']}")
    print("=" * 92 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluación del modelo LLM variando TOP_K.")
    parser.add_argument("--k", type=int, nargs="+", default=[3, 5], help="valores de TOP_K (default: 3 5)")
    parser.add_argument("--grupo", help="evaluar solo un grupo de casos (ej: ambiguos)")
    args = parser.parse_args()

    casos = [c for c in CASOS if args.grupo is None or c["grupo"] == args.grupo]
    if not casos:
        print(f"No hay casos para el grupo '{args.grupo}'")
        return

    df_terminos = cargar_terminos(CSV_TERMINOS)
    df_coberturas = cargar_coberturas(CSV_COBERTURAS)

    resumenes, todas = {}, []
    for k in args.k:
        resumenes[k], filas = evaluar_k(k, casos, df_terminos, df_coberturas)
        todas.extend(filas)

    imprimir_resumen(resumenes)

    salida = os.path.join(asegurar_dir_resultados(), "top_k_por_caso.csv")
    with open(salida, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(todas[0].keys()))
        writer.writeheader()
        writer.writerows(todas)
    print(f"  Detalle por caso: {os.path.relpath(salida)}\n")


if __name__ == "__main__":
    main()
