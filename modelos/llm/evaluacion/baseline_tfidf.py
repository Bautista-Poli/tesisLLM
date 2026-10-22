"""
baseline_tfidf.py — Baseline de recuperación TF-IDF sin LLM, para calibrar el
umbral de aceptación.

Para cada caso con gold de estudio se toma como predicción el top-1 de TF-IDF
y se loguean:
  - coseno top-1
  - margen top-1 − top-2

Después se barre un umbral sobre cada uno de esos puntajes: el baseline acepta
el top-1 si puntaje >= umbral y se abstiene (predice null) si no.
  precisión = top-1 correctos aceptados / casos aceptados
  recall    = top-1 correctos aceptados / casos positivos
Los casos negativos (se espera null) que se aceptan cuentan como falsos positivos,
que es justamente lo que el umbral debería filtrar.

No requiere Ollama.

Uso:
    python -m modelos.llm.evaluacion.baseline_tfidf
"""

from __future__ import annotations

import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from modelos.llm.evaluacion.comun import (
    CASOS, NEGATIVO, POSITIVO, asegurar_dir_resultados, es_correcto, tipo_gold,
)
from modelos.llm.rag import cargar_terminos, similitudes_tfidf
from modelos.llm.tests._runner import CSV_TERMINOS

PUNTAJES = {
    "coseno_top1": "Coseno top-1",
    "margen":      "Margen top-1 − top-2",
}

# Paleta (validada para fondo claro) y tinta de texto
SUPERFICIE = "#fcfcfb"
TEXTO = "#0b0b0b"
TEXTO_SECUNDARIO = "#52514e"
GRILLA = "#e4e3df"
COLORES = {"coseno_top1": "#2a78d6", "margen": "#eb6834"}


def puntuar_casos(df_terminos) -> list[dict]:
    filas = []
    for caso in CASOS:
        gold = tipo_gold(caso)
        if gold is None:
            continue
        sims = similitudes_tfidf(caso["input"], df_terminos)
        orden = sims.argsort()[::-1]
        i1, i2 = orden[0], orden[1]
        top1 = df_terminos.iloc[i1]["preferred_term"]
        filas.append({
            "id": caso["id"],
            "grupo": caso["grupo"],
            "gold": gold,
            "input": caso["input"],
            "top1": top1,
            "coseno_top1": float(sims[i1]),
            "top2": df_terminos.iloc[i2]["preferred_term"],
            "coseno_top2": float(sims[i2]),
            "margen": float(sims[i1] - sims[i2]),
            "top1_correcto": gold == POSITIVO and es_correcto(caso, top1),
        })
    return filas


def barrer_umbral(filas: list[dict], puntaje: str) -> list[dict]:
    n_positivos = sum(f["gold"] == POSITIVO for f in filas)
    curva = []
    for umbral in sorted({f[puntaje] for f in filas}):
        aceptados = [f for f in filas if f[puntaje] >= umbral]
        tp = sum(f["top1_correcto"] for f in aceptados)
        precision = tp / len(aceptados)
        recall = tp / n_positivos if n_positivos else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        curva.append({
            "puntaje": puntaje, "umbral": umbral, "aceptados": len(aceptados),
            "precision": precision, "recall": recall, "f1": f1,
        })
    return curva


def mejor_f1(curva: list[dict]) -> dict:
    return max(curva, key=lambda p: (p["f1"], p["umbral"]))


def graficar(curvas: dict, ruta: str, n_pos: int, n_neg: int) -> None:
    plt.rcParams.update({"font.size": 10, "text.color": TEXTO, "axes.labelcolor": TEXTO_SECUNDARIO,
                         "xtick.color": TEXTO_SECUNDARIO, "ytick.color": TEXTO_SECUNDARIO})
    fig, ax = plt.subplots(figsize=(7.5, 5.2), dpi=150)
    fig.patch.set_facecolor(SUPERFICIE)
    ax.set_facecolor(SUPERFICIE)

    for puntaje, curva in curvas.items():
        puntos = sorted(curva, key=lambda p: -p["umbral"])  # de umbral alto a bajo
        ax.plot([p["recall"] for p in puntos], [p["precision"] for p in puntos],
                color=COLORES[puntaje], linewidth=2, marker="o", markersize=4.5,
                markeredgecolor=SUPERFICIE, markeredgewidth=1, label=PUNTAJES[puntaje], zorder=3)

        mejor = mejor_f1(curva)
        ax.plot(mejor["recall"], mejor["precision"], marker="o", markersize=10,
                color=COLORES[puntaje], markeredgecolor=SUPERFICIE, markeredgewidth=2, zorder=4)
        dy = 14 if puntaje == "coseno_top1" else -20
        ax.annotate(f"umbral {mejor['umbral']:.3f} · F1 {mejor['f1']:.2f}",
                    (mejor["recall"], mejor["precision"]), xytext=(10, dy),
                    textcoords="offset points", fontsize=9, color=TEXTO,
                    arrowprops={"arrowstyle": "-", "color": TEXTO_SECUNDARIO, "linewidth": 0.8})

    ax.set_xlim(0, 1.02)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Recall (top-1 correctos aceptados / casos positivos)")
    ax.set_ylabel("Precisión (top-1 correctos / aceptados)")
    ax.set_title("Baseline TF-IDF: precisión vs recall al variar el umbral de aceptación",
                 loc="left", fontsize=11, color=TEXTO, pad=22)
    ax.text(0, 1.02, f"{n_pos} casos positivos · {n_neg} negativos (se espera null). "
                     "El punto grande marca el umbral de mejor F1.",
            transform=ax.transAxes, fontsize=8.5, color=TEXTO_SECUNDARIO, va="bottom")
    ax.grid(True, color=GRILLA, linewidth=0.8, zorder=0)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(GRILLA)
    ax.tick_params(length=0)
    ax.legend(loc="lower left", frameon=False, labelcolor=TEXTO)

    fig.tight_layout()
    fig.savefig(ruta, facecolor=SUPERFICIE)
    plt.close(fig)


def escribir_csv(ruta: str, filas: list[dict]) -> None:
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        writer.writeheader()
        writer.writerows(filas)


def main() -> None:
    df_terminos = cargar_terminos(CSV_TERMINOS)
    filas = puntuar_casos(df_terminos)
    n_pos = sum(f["gold"] == POSITIVO for f in filas)
    n_neg = sum(f["gold"] == NEGATIVO for f in filas)

    print("\n" + "=" * 110)
    print("  BASELINE TF-IDF — puntajes por caso")
    print("=" * 110)
    print(f"  {'id':<40} {'gold':<9} {'coseno top-1':>12} {'margen':>8} {'ok':>3}  top-1")
    print(f"  {'-'*40} {'-'*9} {'-'*12} {'-'*8} {'-'*3}  {'-'*40}")
    for f in sorted(filas, key=lambda f: -f["coseno_top1"]):
        ok = "✓" if f["top1_correcto"] else ("·" if f["gold"] == NEGATIVO else "✗")
        print(f"  {f['id']:<40} {f['gold']:<9} {f['coseno_top1']:>12.3f} {f['margen']:>8.3f} {ok:>3}  {f['top1'][:60]}")

    curvas = {p: barrer_umbral(filas, p) for p in PUNTAJES}

    print("\n  Umbrales sugeridos")
    for puntaje, curva in curvas.items():
        m = mejor_f1(curva)
        print(f"  {PUNTAJES[puntaje]:<22} mejor F1: umbral {m['umbral']:.3f} → P {m['precision']:.2f}"
              f"  R {m['recall']:.2f}  F1 {m['f1']:.2f}  ({m['aceptados']} aceptados)")
        alta = [p for p in curva if p["precision"] >= 0.9]
        if alta:
            a = max(alta, key=lambda p: (p["recall"], -p["umbral"]))
            print(f"  {'':<22} P ≥ 0.90:  umbral {a['umbral']:.3f} → P {a['precision']:.2f}"
                  f"  R {a['recall']:.2f}  ({a['aceptados']} aceptados)")
        else:
            print(f"  {'':<22} P ≥ 0.90:  ningún umbral la alcanza")
    print(f"\n  Casos con gold: {len(filas)} ({n_pos} positivos, {n_neg} negativos). "
          f"Top-1 correcto sin umbral: {sum(f['top1_correcto'] for f in filas)}/{n_pos}")

    directorio = asegurar_dir_resultados()
    ruta_casos = os.path.join(directorio, "baseline_tfidf_por_caso.csv")
    ruta_curva = os.path.join(directorio, "baseline_tfidf_curva_pr.csv")
    ruta_png = os.path.join(directorio, "baseline_tfidf_pr.png")
    escribir_csv(ruta_casos, filas)
    escribir_csv(ruta_curva, [p for c in curvas.values() for p in c])
    graficar(curvas, ruta_png, n_pos, n_neg)

    print(f"\n  Por caso:  {os.path.relpath(ruta_casos)}")
    print(f"  Curva PR:  {os.path.relpath(ruta_curva)}")
    print(f"  Gráfico:   {os.path.relpath(ruta_png)}")
    print("=" * 110 + "\n")


if __name__ == "__main__":
    main()
