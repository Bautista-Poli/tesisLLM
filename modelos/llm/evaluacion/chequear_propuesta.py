"""
chequear_propuesta.py — Consistencia entre la propuesta de variantes y las etiquetas.

Lee resultados/propuesta_variantes.csv TAL COMO ESTÉ (con las ediciones manuales) y
busca la frase de cada variante en los inputs de la suite y del held-out
(sin tildes/minúsculas, por palabra completa):

  - (a) hacia un estudio X: conflicto si algún caso con esa frase está etiquetado AMBIGUO.
        También se informa (no es conflicto) si el caso tiene otra etiqueta distinta de X.
  - (b) eliminar:           conflicto si algún caso con esa frase está etiquetado con un
                            término exacto (debería ser AMBIGUO o null).

Coincidencia "parcial": la frase aparece pero el mensaje sigue con más zona o
lateralidad, aunque sea con typo (ej. "rayos de columna" dentro de "rayos de columna
lumbar" o "lumbal"); es un conflicto más débil que la coincidencia completa.

Las variantes (b) sin zona anatómica ("placa", "rayos", "rx"...) se informan como
"no aplica": se eliminan por no identificar un estudio, no por ser ambiguas, así que
aparecer en un mensaje con estudio claro no contradice la etiqueta.

Uso:
    python -m modelos.llm.evaluacion.chequear_propuesta
"""

from __future__ import annotations

import csv
import difflib
import os
import re

from modelos.llm.evaluacion.analizar_catalogo import GENERICAS
from modelos.llm.evaluacion.comun import asegurar_dir_resultados
from modelos.llm.evaluacion.datos_etiquetados import (
    CLASE_AMBIGUO, CLASE_NULL, cargar_heldout, cargar_suite_etiquetada, normalizar,
)

CONTINUACIONES = {
    "cervical", "dorsal", "lumbar", "sacra", "toracica", "lumbosacra", "baja", "derecho", "derecha",
    "izquierdo", "izquierda", "superior", "inferior", "completa", "y",
}


def buscar(variante: str, texto: str) -> str | None:
    """'completa' / 'parcial: sigue con X' si la frase está en el texto; None si no está."""
    m = re.search(rf"(?<!\w){re.escape(variante)}(?!\w)", texto)
    if not m:
        return None
    resto = texto[m.end():].split()
    if resto:
        siguiente = resto[0].strip(",.")
        if siguiente in CONTINUACIONES:
            return f"parcial: sigue con '{siguiente}'"
        parecida = difflib.get_close_matches(siguiente, CONTINUACIONES, n=1, cutoff=0.75)
        if parecida:
            return f"parcial: sigue con '{siguiente}' (≈{parecida[0]})"
    return "completa"


def main() -> None:
    d = asegurar_dir_resultados()
    with open(os.path.join(d, "propuesta_variantes.csv"), newline="", encoding="utf-8") as f:
        propuesta = [r for r in csv.DictReader(f) if r["accion"] in ("a", "b")]
    casos = cargar_suite_etiquetada() + cargar_heldout()
    textos = [(c, normalizar(c["input"])) for c in casos]

    filas = []
    for p in propuesta:
        v = p["variante_normalizada"]
        for caso, texto in textos:
            tipo = buscar(v, texto)
            if tipo is None:
                continue
            esperado = caso["esperado"]
            if p["accion"] == "b" and set(v.split()) <= GENERICAS:
                if esperado in (CLASE_AMBIGUO, CLASE_NULL):
                    continue
                gravedad = "no aplica"
                detalle = "variante sin zona anatómica: se elimina por no identificar un estudio, no por ambigua"
            elif p["accion"] == "a" and esperado == CLASE_AMBIGUO:
                gravedad = "conflicto"
                detalle = f"(a) hacia '{p['estudio_por_defecto']}' pero el caso está etiquetado AMBIGUO"
            elif p["accion"] == "b" and esperado not in (CLASE_AMBIGUO, CLASE_NULL):
                gravedad = "conflicto"
                detalle = f"(b) eliminar, pero el caso está etiquetado con un término exacto"
            elif p["accion"] == "a" and esperado != p["estudio_por_defecto"]:
                gravedad = "info"
                detalle = f"(a) hacia '{p['estudio_por_defecto']}', el caso tiene otra etiqueta"
            else:
                continue
            filas.append({"gravedad": gravedad, "coincidencia": tipo, "variante": v, "accion": p["accion"],
                          "estudio_por_defecto": p["estudio_por_defecto"], "set": caso["set"], "id": caso["id"],
                          "input": caso["input"], "esperado": esperado, "detalle": detalle})

    orden = {"conflicto": 0, "info": 1, "no aplica": 2}
    filas.sort(key=lambda r: (orden[r["gravedad"]], r["coincidencia"] != "completa", r["variante"]))
    conflictos = [r for r in filas if r["gravedad"] == "conflicto"]
    print(f"\n  Variantes (a)/(b) chequeadas: {len(propuesta)} | casos: {len(casos)}")
    print(f"  Conflictos: {len(conflictos)} "
          f"({sum(r['coincidencia'] == 'completa' for r in conflictos)} con coincidencia completa) | "
          f"informativos: {sum(r['gravedad'] == 'info' for r in filas)} | "
          f"no aplica (variantes sin zona: placa, rayos, rx...): {sum(r['gravedad'] == 'no aplica' for r in filas)}\n")
    for r in filas:
        if r["gravedad"] == "no aplica":
            continue
        print(f"  [{r['gravedad']:<9}] [{r['coincidencia'][:30]:<30}] ({r['accion']}) «{r['variante']}» "
              f"→ {r['set']}/{r['id']}: «{r['input'][:55]}» = {r['esperado'][:50]}")

    ruta = os.path.join(d, "conflictos_etiquetas.csv")
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["gravedad", "coincidencia", "variante", "accion", "estudio_por_defecto",
                                          "set", "id", "input", "esperado", "detalle"])
        w.writeheader()
        w.writerows(filas)
    print(f"\n  Detalle: {os.path.relpath(ruta)}\n")

    chequear_por_zona(d, casos)


# ─── Chequeo por zona anatómica ──────────────────────────────────────────────

# Zonas que aparecen en los casos AMBIGUO (palabra completa, sin tildes)
ZONAS = {
    "pierna": r"\bpiernas?\b",
    "hombro": r"\bhombros?\b",
    "cadera": r"\bcaderas?\b",
    "pie": r"\bpies?\b",
    "columna": r"\b(columna|espina)\b",
    "espalda": r"\bespalda\b",
    "brazo": r"\bbrazos?\b",
    "huesos largos": r"\bhuesos largos\b",
    "cuerpo": r"\bcuerpo\b",
}


def chequear_por_zona(d: str, casos: list[dict]) -> None:
    """
    Para cada caso AMBIGUO, la zona que menciona; para cada zona, las variantes en (a)
    que la contienen y apuntan a un estudio específico.
    """
    with open(os.path.join(d, "propuesta_variantes.csv"), newline="", encoding="utf-8") as f:
        en_a = [r for r in csv.DictReader(f) if r["accion"] == "a"]

    casos_por_zona: dict[str, list[dict]] = {}
    sin_zona = []
    for c in casos:
        if c["esperado"] != CLASE_AMBIGUO:
            continue
        texto = normalizar(c["input"])
        zonas = [z for z, patron in ZONAS.items() if re.search(patron, texto)]
        if not zonas:
            sin_zona.append(c)
        for z in zonas:
            casos_por_zona.setdefault(z, []).append(c)

    filas = []
    print("  ── Por zona anatómica: casos AMBIGUO vs variantes en (a) con esa zona ──\n")
    for zona, cs in casos_por_zona.items():
        variantes = [r for r in en_a if re.search(ZONAS[zona], r["variante_normalizada"])]
        print(f"  {zona.upper()} — {len(cs)} caso(s) AMBIGUO: "
              + ", ".join(f"{c['set']}/{c['id']}" for c in cs))
        if not variantes:
            print("      (ninguna variante en (a) con esta zona)")
        for r in variantes:
            sug = "  [sugerida]" if r["revisar_sugerencia"] == "True" else ""
            print(f"      «{r['variante_normalizada']}» → {r['estudio_por_defecto']}{sug}")
            filas.append({"zona": zona, "casos_ambiguos": " | ".join(f"{c['set']}/{c['id']}" for c in cs),
                          "variante": r["variante_normalizada"], "estudio_por_defecto": r["estudio_por_defecto"],
                          "revisar_sugerencia": r["revisar_sugerencia"]})
        print()
    print(f"  Casos AMBIGUO sin zona anatómica (no aplica): "
          + ", ".join(f"{c['set']}/{c['id']}" for c in sin_zona) + "\n")

    ruta = os.path.join(d, "conflictos_por_zona.csv")
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["zona", "casos_ambiguos", "variante", "estudio_por_defecto",
                                          "revisar_sugerencia"])
        w.writeheader()
        w.writerows(filas)
    print(f"  Detalle: {os.path.relpath(ruta)}\n")


if __name__ == "__main__":
    main()
