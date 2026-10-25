"""
verificar_heldout.py — Chequeo de contaminación de los sets held-out.

Verifica que ningún mensaje del held-out:
  1. contenga una variante coloquial del catálogo de más de 8 caracteres
     (comparación sin tildes ni mayúsculas, como substring; las alternativas
     con barra, ej. "izquierdo/derecho", se expanden);
  2. coincida con un input de la suite etiquetada (misma normalización);
  3. (solo held-out 2) coincida con un input del held-out 1.
Además valida que las etiquetas existan en el catálogo, que los ids sean únicos y
que tipo_ambiguedad esté completo y sea válido en los AMBIGUO.

Held-out 2 se chequea contra los catálogos v1 y v2.1 (los dos que se van a
comparar) y además:
  - que no queden filas sin completar (id, input, esperado);
  - que la cantidad por categoría sea la de la plantilla;
  - que las etiquetas cumplan la regla de lateralidad (chequear_lateralidad);
  - inputs casi iguales (similitud ≥ 0.85) a la suite o al held-out 1: solo aviso.

Uso:
    python -m modelos.llm.evaluacion.verificar_heldout                     # held-out 1, catálogo v1
    python -m modelos.llm.evaluacion.verificar_heldout --catalogo v2
    python -m modelos.llm.evaluacion.verificar_heldout --set heldout2      # catálogos v1 y v2.1
"""

from __future__ import annotations

import argparse
import difflib
import itertools
import os
import sys
from collections import Counter

import pandas as pd

from modelos.llm.evaluacion.datos_etiquetados import (
    CLASE_AMBIGUO, CLASE_NULL, cargar_heldout, cargar_heldout2, cargar_suite_etiquetada,
    errores_tipo_ambiguedad, normalizar,
)
from modelos.llm.evaluacion.comun import asegurar_dir_resultados
from modelos.llm.extractor import CSV_TERMINOS

CATALOGOS = {"v1": CSV_TERMINOS,
             "v2": CSV_TERMINOS.replace("snomed_con_variantes.csv", "snomed_con_variantes_v2.csv"),
             "v2.1": CSV_TERMINOS.replace("snomed_con_variantes.csv", "snomed_con_variantes_v2_1.csv")}

LARGO_MIN_VARIANTE = 8  # se chequean variantes de MÁS de 8 caracteres
SIMILITUD_AVISO = 0.85
CATALOGOS_HELDOUT2 = ("v1", "v2.1")
PLANTILLA_HELDOUT2 = {"claro": 12, "ambiguo": 8, "typo": 5, "multislot": 5, "fuera_dominio": 5}


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chequeo de contaminación de los sets held-out.")
    parser.add_argument("--set", choices=["heldout", "heldout2"], default="heldout")
    parser.add_argument("--catalogo", choices=list(CATALOGOS), default="v1",
                        help="solo para el held-out 1 (el 2 se chequea siempre contra v1 y v2.1)")
    args = parser.parse_args(argv)
    es_h2 = args.set == "heldout2"
    catalogos = CATALOGOS_HELDOUT2 if es_h2 else (args.catalogo,)

    heldout = cargar_heldout2() if es_h2 else cargar_heldout()
    suite = cargar_suite_etiquetada()
    referencias = {"suite": {normalizar(c["input"]): c["id"] for c in suite}}
    if es_h2:
        referencias["held-out 1"] = {normalizar(c["input"]): c["id"] for c in cargar_heldout()}

    lineas = []
    def out(texto=""):
        lineas.append(texto)
        print(texto)

    out("=" * 80)
    out(f"  VERIFICACIÓN DEL SET {'HELD-OUT 2' if es_h2 else 'HELD-OUT'} — catálogo {' y '.join(catalogos)}")
    out("=" * 80)
    out(f"  Mensajes: {len(heldout)}  |  por categoría: {dict(Counter(c['grupo'] for c in heldout))}")
    for nombre, ref in referencias.items():
        out(f"  Inputs únicos de {nombre} (normalizados): {len(ref)}")
    out()
    fallas = []

    def chequeo(nombre: str, problemas: list[str]) -> None:
        out(f"  [{'OK' if not problemas else 'FALLA'}] {nombre}: {len(problemas)}")
        for p in problemas:
            out(f"         {p}")
        if problemas:
            fallas.append(nombre)

    if es_h2:
        incompletas = [f"fila {i + 2} ({c['grupo']}): falta {', '.join(k for k in ('id', 'input', 'esperado') if not c[k].strip())}"
                       for i, c in enumerate(heldout) if not all(c[k].strip() for k in ("id", "input", "esperado"))]
        chequeo("Filas sin completar (id, input, esperado)", incompletas)
        conteo = Counter(c["grupo"] for c in heldout)
        chequeo("Cantidad por categoría distinta de la plantilla",
                [f"{cat}: {conteo.get(cat, 0)} (plantilla {n})" for cat, n in PLANTILLA_HELDOUT2.items()
                 if conteo.get(cat, 0) != n]
                + [f"{cat}: categoría fuera de la plantilla" for cat in conteo if cat not in PLANTILLA_HELDOUT2])
        heldout = [c for c in heldout if c["input"].strip()]

    for cat in catalogos:
        df = pd.read_csv(CATALOGOS[cat])
        variantes = cargar_variantes(df)
        terminos = set(df["preferred_term"])
        out(f"  — Catálogo {cat}: {len(variantes)} variantes de más de {LARGO_MIN_VARIANTE} caracteres (tras expandir '/')")
        contaminados = []
        for c in heldout:
            texto = normalizar(c["input"])
            hits = [v for v in variantes if v in texto]
            if hits:
                contaminados.append(f"{c['id']}: {c['input']!r} → {hits}")
        chequeo(f"[{cat}] Mensajes con variantes de >{LARGO_MIN_VARIANTE} caracteres", contaminados)
        chequeo(f"[{cat}] Etiquetas fuera del catálogo",
                [f"{c['id']}: {c['esperado']!r}" for c in heldout
                 if c["esperado"] not in (CLASE_AMBIGUO, CLASE_NULL) and c["esperado"] not in terminos])

    for nombre, ref in referencias.items():
        chequeo(f"Coincidencias con inputs de {nombre}",
                [f"{c['id']} = {ref[normalizar(c['input'])]}" for c in heldout if normalizar(c["input"]) in ref])
    chequeo("Ids duplicados", [i for i, n in Counter(c["id"] for c in heldout).items() if n > 1])
    chequeo("tipo_ambiguedad faltante o inválido", [f"{i}: {p}" for i, p in errores_tipo_ambiguedad(heldout)])

    if es_h2:
        from modelos.llm.evaluacion.chequear_lateralidad import contradiccion  # importa este módulo
        chequeo("Etiquetas que contradicen la regla de lateralidad",
                [f"{c['id']}: {c['input']!r} = {c['esperado']} → {m}" for c in heldout if (m := contradiccion(c))])
        avisos = []
        for c in heldout:
            texto = normalizar(c["input"])
            for nombre, ref in referencias.items():
                for otro, id_otro in ref.items():
                    r = difflib.SequenceMatcher(None, texto, otro).ratio()
                    if SIMILITUD_AVISO <= r < 1:
                        avisos.append(f"{c['id']} ≈ {nombre}/{id_otro} ({r:.2f}): {c['input']!r}")
        out(f"  [AVISO] Inputs casi iguales (similitud ≥ {SIMILITUD_AVISO}) a la suite o al held-out 1: {len(avisos)}")
        for a in avisos:
            out(f"         {a}")

    out()
    out(f"  Resultado: {'PASA' if not fallas else 'NO PASA'}")
    out("=" * 80)

    if es_h2:
        nombre = "verificacion_heldout2.txt"
    else:
        nombre = "verificacion_heldout.txt" if args.catalogo == "v1" else f"verificacion_heldout_{args.catalogo}.txt"
    ruta = os.path.join(asegurar_dir_resultados(), nombre)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")
    print(f"  Reporte: {os.path.relpath(ruta)}\n")
    return 0 if not fallas else 1


if __name__ == "__main__":
    sys.exit(main())
