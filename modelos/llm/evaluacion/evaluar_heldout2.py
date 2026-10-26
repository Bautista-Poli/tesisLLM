"""
evaluar_heldout2.py — Evaluación final, UNA sola vez, sobre el held-out 2.

Compara, con el catálogo v1 y sobre los mismos mensajes de datos/heldout2.csv:
  i) f + few-shot de fuera de dominio, k=5 (la configuración elegida)
  j) i) + regla post-LLM de lateralidad (modelos/llm/lateralidad.py)
j) se deriva de la misma predicción de i) (una sola llamada al LLM por mensaje), así
que la diferencia entre las dos es solo la regla. Reporta:
  - accuracy estricta, con IC 95% bootstrap (percentil, 10 000 remuestreos de
    casos, semilla fija); también el IC de la diferencia j − i (remuestreo pareado);
  - F1 de AMBIGUO total, recall de AMBIGUO por tipo_ambiguedad y F1 de null;
  - McNemar exacto (binomial bilateral sobre los pares discordantes) entre i y j.

Antes de llamar al LLM corre verificar_heldout --set heldout2 y no sigue si falla.
Si ya existe resultados/heldout2_por_caso.csv no vuelve a evaluar (es una
evaluación única): --forzar lo pisa, y queda anotado en el reporte.

Requiere Ollama.

Uso:
    python -m modelos.llm.evaluacion.evaluar_heldout2 --chequear   # solo prerequisitos, sin LLM
    python -m modelos.llm.evaluacion.evaluar_heldout2              # la evaluación
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
import time

import numpy as np
import requests

from modelos.llm.evaluacion import verificar_heldout
from modelos.llm.evaluacion.comparar_configuraciones import CATALOGOS, CONFIGS, predecir_llm
from modelos.llm.evaluacion.comun import asegurar_dir_resultados
from modelos.llm.evaluacion.datos_etiquetados import CLASE_NULL, TIPOS_AMBIGUEDAD, cargar_heldout2
from modelos.llm.evaluacion.metricas import metricas_estrictas, recall_ambiguo_por_tipo
from modelos.llm.extractor import CSV_COBERTURAS
from modelos.llm.lateralidad import aplicar_a_clase
from modelos.llm.ollama_client import MODEL, OLLAMA_URL
from modelos.llm.rag import cargar_coberturas, cargar_terminos

CONFIGS_COMPARADAS = ("i", "j")  # j = i + regla de lateralidad sobre la misma predicción
CATALOGO = "v1"
K = 5
N_BOOTSTRAP = 10_000
SEMILLA = 20261025
CSV_POR_CASO = "heldout2_por_caso.csv"
MD_RESUMEN = "heldout2_resumen.md"


def mcnemar_exacto(a_bien: list[bool], b_bien: list[bool]) -> tuple[int, int, float]:
    """(solo A acierta, solo B acierta, p bilateral) con la binomial exacta sobre los discordantes."""
    solo_a = sum(a and not b for a, b in zip(a_bien, b_bien))
    solo_b = sum(b and not a for a, b in zip(a_bien, b_bien))
    n = solo_a + solo_b
    if n == 0:
        return 0, 0, 1.0
    cola = sum(math.comb(n, i) for i in range(min(solo_a, solo_b) + 1)) / 2 ** n
    return solo_a, solo_b, min(1.0, 2 * cola)


def ic_bootstrap(aciertos: dict[str, np.ndarray], rng: np.random.Generator) -> dict[str, tuple[float, float]]:
    """IC 95% percentil de la accuracy de cada configuración y de la diferencia, con los mismos remuestreos."""
    n = len(next(iter(aciertos.values())))
    idx = rng.integers(0, n, size=(N_BOOTSTRAP, n))
    medias = {c: v[idx].mean(axis=1) for c, v in aciertos.items()}
    a, b = CONFIGS_COMPARADAS
    medias[f"{b} − {a}"] = medias[b] - medias[a]
    return {c: (float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))) for c, m in medias.items()}


def chequear_prerequisitos(ruta_por_caso: str, forzar: bool) -> list[str]:
    problemas = []
    if verificar_heldout.main(["--set", "heldout2"]) != 0:
        problemas.append("verificar_heldout --set heldout2 no pasa (ver el reporte de arriba)")
    if not os.path.exists(CATALOGOS[CATALOGO]):
        problemas.append(f"no existe el catálogo {CATALOGO}: {CATALOGOS[CATALOGO]}")
    if os.path.exists(ruta_por_caso) and not forzar:
        problemas.append(f"ya existe {os.path.relpath(ruta_por_caso)}: el held-out 2 ya se evaluó "
                         "(--forzar para pisarlo)")
    try:
        modelos = [m["name"] for m in requests.get(OLLAMA_URL.replace("/api/chat", "/api/tags"),
                                                   timeout=5).json().get("models", [])]
        if MODEL not in modelos:
            problemas.append(f"Ollama responde pero no tiene el modelo {MODEL}")
    except requests.RequestException as e:
        problemas.append(f"Ollama no responde: {type(e).__name__}")
    return problemas


def evaluar(items: list[dict]) -> list[dict]:
    df_coberturas = cargar_coberturas(CSV_COBERTURAS)
    df_terminos = cargar_terminos(CATALOGOS[CATALOGO])
    filas = []
    for n, item in enumerate(items):
        print(f"  i@{CATALOGO} [{n + 1}/{len(items)}]", end="\r", flush=True)
        t0 = time.perf_counter()
        error = ""
        try:
            pred_i = predecir_llm(item, df_terminos, df_coberturas, CONFIGS["i"], K, CATALOGOS[CATALOGO])
        except Exception as e:  # el caso cuenta como null, igual que en comparar_configuraciones
            pred_i, error = CLASE_NULL, f"{type(e).__name__}: {e}"
        latencia = round(time.perf_counter() - t0, 4)
        pred_j, tipo_j = aplicar_a_clase(pred_i, item["input"])
        for config, pred, tipo in (("i", pred_i, ""), ("j", pred_j, tipo_j)):
            filas.append({"config": config, "catalogo": CATALOGO, "id": item["id"], "grupo": item["grupo"],
                          "input": item["input"], "esperado": item["esperado"],
                          "tipo_ambiguedad": item["tipo_ambiguedad"], "prediccion": pred,
                          "tipo_ambiguedad_pred": tipo, "correcto": pred == item["esperado"],
                          "latencia_s": latencia, "error": error})
    print(" " * 60, end="\r")
    return filas


def reporte(items: list[dict], filas: list[dict], forzado: bool) -> str:
    esperados = [it["esperado"] for it in items]
    por_cfg = {c: [f for f in filas if f["config"] == c] for c in CONFIGS_COMPARADAS}
    aciertos = {c: np.array([f["correcto"] for f in fs], dtype=float) for c, fs in por_cfg.items()}
    ic = ic_bootstrap(aciertos, np.random.default_rng(SEMILLA))
    a, b = CONFIGS_COMPARADAS
    solo_a, solo_b, p = mcnemar_exacto([f["correcto"] for f in por_cfg[a]], [f["correcto"] for f in por_cfg[b]])

    def rec(r: dict) -> str:
        return "—" if r["recall"] is None else f"{r['recall']:.3f} ({r['detectados']}/{r['n']})"

    lineas = [f"# Held-out 2 — {a}) {CONFIGS[a]['nombre']} vs {b}) {CONFIGS[b]['nombre']} (catálogo {CATALOGO}, k={K})",
              "", f"Casos: {len(items)}. Evaluación única" + (" (**repetida con --forzar**)." if forzado else "."), "",
              "| Config | Accuracy | IC 95% bootstrap | F1 AMBIGUO | "
              + " | ".join(f"Recall AMBIGUO {t}" for t in TIPOS_AMBIGUEDAD) + " | F1 null | Errores |",
              "|---|---|---|---|" + "---|" * len(TIPOS_AMBIGUEDAD) + "---|---|"]
    for c, fs in por_cfg.items():
        predichos = [f["prediccion"] for f in fs]
        m = metricas_estrictas(esperados, predichos)
        por_tipo = recall_ambiguo_por_tipo(items, predichos)
        lo, hi = ic[c]
        lineas.append(f"| {c}) {CONFIGS[c]['nombre']} | {m['accuracy']:.3f} | [{lo:.3f}, {hi:.3f}] | "
                      f"{m['ambiguo'][2]:.3f} | " + " | ".join(rec(por_tipo[t]) for t in TIPOS_AMBIGUEDAD)
                      + f" | {m['null'][2]:.3f} | {sum(1 for f in fs if f['error'])} |")
    lo, hi = ic[f"{b} − {a}"]
    diff = aciertos[b].mean() - aciertos[a].mean()
    lineas += ["",
               f"- Diferencia de accuracy {b} − {a}: {diff:+.3f}, IC 95% bootstrap pareado [{lo:+.3f}, {hi:+.3f}]",
               f"- McNemar exacto: solo {a} acierta = {solo_a}, solo {b} acierta = {solo_b}, p = {p:.3f}",
               "", "## Definiciones", "",
               "- Accuracy estricta: predicción == preferred_term esperado; AMBIGUO y null son clases.",
               f"- IC 95%: bootstrap percentil, {N_BOOTSTRAP} remuestreos de casos con reposición, semilla {SEMILLA}; "
               "las dos configuraciones usan los mismos remuestreos.",
               "- Recall AMBIGUO por tipo: casos del tipo predichos como AMBIGUO / casos del tipo.",
               "- j) aplica la regla de lateralidad sobre la misma predicción de i): no hay una segunda llamada al LLM.",
               "- McNemar exacto: binomial bilateral (p = 0.5) sobre los casos en que acierta uno solo.",
               "- Un error del LLM (conexión o parseo) cuenta como predicción null."]
    return "\n".join(lineas) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluación única de i) vs j) (catálogo v1) sobre el held-out 2.")
    parser.add_argument("--chequear", action="store_true", help="solo chequear prerequisitos, sin llamar al LLM")
    parser.add_argument("--forzar", action="store_true", help="evaluar aunque ya exista el resultado")
    args = parser.parse_args()

    d = asegurar_dir_resultados()
    ruta_por_caso = os.path.join(d, CSV_POR_CASO)
    problemas = chequear_prerequisitos(ruta_por_caso, args.forzar)
    if problemas:
        print("\n  No se evalúa:\n" + "\n".join(f"    - {p}" for p in problemas) + "\n")
        return 1
    if args.chequear:
        print("\n  Prerequisitos OK: listo para evaluar (sin --chequear).\n")
        return 0

    items = cargar_heldout2()
    filas = evaluar(items)
    with open(ruta_por_caso, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    md = reporte(items, filas, args.forzar)
    print(md)
    with open(os.path.join(d, MD_RESUMEN), "w", encoding="utf-8") as f:
        f.write(md)
    print(f"  Resultados en {os.path.relpath(d)}/: {CSV_POR_CASO}, {MD_RESUMEN}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
