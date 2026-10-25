"""
verificar_heldout.py — Chequeo de contaminación del set held-out.

Verifica que ningún mensaje de datos/heldout.csv:
  1. contenga una variante coloquial de snomed_con_variantes.csv de más de
     8 caracteres (comparación sin tildes ni mayúsculas, como substring;
     las alternativas con barra, ej. "izquierdo/derecho", se expanden);
  2. coincida con un input de la suite etiquetada (misma normalización).
Además valida que las etiquetas existan en el catálogo y que los ids sean únicos.

Uso:
    python -m modelos.llm.evaluacion.verificar_heldout                 # catálogo v1
    python -m modelos.llm.evaluacion.verificar_heldout --catalogo v2
"""

from __future__ import annotations

import argparse
import itertools
import os
import sys
from collections import Counter

import pandas as pd

from modelos.llm.evaluacion.datos_etiquetados import (
    CLASE_AMBIGUO, CLASE_NULL, cargar_heldout, cargar_suite_etiquetada, normalizar,
)
from modelos.llm.evaluacion.comun import asegurar_dir_resultados
from modelos.llm.extractor import CSV_TERMINOS

CATALOGOS = {"v1": CSV_TERMINOS,
             "v2": CSV_TERMINOS.replace("snomed_con_variantes.csv", "snomed_con_variantes_v2.csv")}

LARGO_MIN_VARIANTE = 8  # se chequean variantes de MÁS de 8 caracteres


def expandir_barras(variante: str) -> list[str]:
    """'rayo de tórax izquierdo/derecho' -> ['rayo de tórax izquierdo', 'rayo de tórax derecho']."""
    opciones = [token.split("/") for token in variante.split()]
    return [" ".join(combo) for combo in itertools.product(*opciones)]


def cargar_variantes(df: pd.DataFrame) -> dict[str, str]:
    """Variante normalizada -> preferred_term de origen (solo las de más de 8 caracteres)."""
    variantes = {}
    for _, fila in df.iterrows():
        if pd.isna(fila["variantes_coloquiales"]):
            continue
        for cruda in str(fila["variantes_coloquiales"]).split(","):
            for v in expandir_barras(cruda.strip()):
                vn = normalizar(v)
                if len(vn) > LARGO_MIN_VARIANTE:
                    variantes.setdefault(vn, fila["preferred_term"])
    return variantes


def main() -> int:
    parser = argparse.ArgumentParser(description="Chequeo de contaminación del held-out.")
    parser.add_argument("--catalogo", choices=list(CATALOGOS), default="v1")
    args = parser.parse_args()
    df = pd.read_csv(CATALOGOS[args.catalogo])
    terminos = set(df["preferred_term"])
    variantes = cargar_variantes(df)
    heldout = cargar_heldout()
    suite = cargar_suite_etiquetada()
    inputs_suite = {normalizar(c["input"]): c["id"] for c in suite}

    lineas = []
    def out(texto=""):
        lineas.append(texto)
        print(texto)

    out("=" * 80)
    out(f"  VERIFICACIÓN DEL SET HELD-OUT — catálogo {args.catalogo}")
    out("=" * 80)
    out(f"  Mensajes: {len(heldout)}  |  por categoría: {dict(Counter(c['grupo'] for c in heldout))}")
    out(f"  Variantes del CSV con más de {LARGO_MIN_VARIANTE} caracteres (tras expandir '/'): {len(variantes)}")
    out(f"  Inputs únicos de la suite (normalizados): {len(inputs_suite)}")

    contaminados = []
    for c in heldout:
        texto = normalizar(c["input"])
        hits = [v for v in variantes if v in texto]
        if hits:
            contaminados.append((c["id"], c["input"], hits))

    repetidos = [(c["id"], inputs_suite[normalizar(c["input"])])
                 for c in heldout if normalizar(c["input"]) in inputs_suite]

    etiquetas_invalidas = [(c["id"], c["esperado"]) for c in heldout
                           if c["esperado"] not in (CLASE_AMBIGUO, CLASE_NULL) and c["esperado"] not in terminos]
    ids_duplicados = [i for i, n in Counter(c["id"] for c in heldout).items() if n > 1]

    out()
    out(f"  [{'OK' if not contaminados else 'FALLA'}] Variantes de >{LARGO_MIN_VARIANTE} caracteres: "
        f"{len(contaminados)} mensajes las contienen")
    for i, txt, hits in contaminados:
        out(f"         {i}: {txt!r} → {hits}")
    out(f"  [{'OK' if not repetidos else 'FALLA'}] Coincidencias con inputs de la suite: {len(repetidos)}")
    for i, s in repetidos:
        out(f"         {i} = {s}")
    out(f"  [{'OK' if not etiquetas_invalidas else 'FALLA'}] Etiquetas fuera del catálogo: {len(etiquetas_invalidas)}")
    for i, e in etiquetas_invalidas:
        out(f"         {i}: {e!r}")
    out(f"  [{'OK' if not ids_duplicados else 'FALLA'}] Ids duplicados: {len(ids_duplicados)}")

    ok = not (contaminados or repetidos or etiquetas_invalidas or ids_duplicados)
    out()
    out(f"  Resultado: {'PASA' if ok else 'NO PASA'}")
    out("=" * 80)

    nombre = "verificacion_heldout.txt" if args.catalogo == "v1" else f"verificacion_heldout_{args.catalogo}.txt"
    ruta = os.path.join(asegurar_dir_resultados(), nombre)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")
    print(f"  Reporte: {os.path.relpath(ruta)}\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
