"""
chequear_lateralidad.py — Regla de lateralidad para zonas pares.

Regla: si el mensaje menciona una zona par (hombro, pie, cadera, rodilla, mano,
codo, muñeca, tobillo) y no especifica lado (derecho / izquierdo / ambos), la
etiqueta es AMBIGUO (tipo_ambiguedad = falta_lado). Si especifica lado, la
etiqueta es un estudio con ese lado.
En el catálogo: una variante sin lado no puede apuntar a un estudio con lado.

Chequeos (no modifican nada):
  1. Etiquetas de la suite y del held-out 1 que contradicen la regla, junto con
     la propuesta de corrección de resultados/propuesta_lateralidad.csv (escrita
     a mano, pendiente de aprobación). Falla si una contradicción no tiene propuesta.
  2. Variantes del catálogo (v1 y v2.1) con zona par y sin lado que apuntan a un
     estudio con lado, o con un lado que apuntan a un estudio con otro lado.
  3. Por zona par: variantes sin lado que quedan como única variante de un estudio
     sin lado (en v2.1, acción a). La regla no las prohíbe, pero compiten con la
     etiqueta AMBIGUO de los mensajes con esa zona sin lado.

Uso:
    python -m modelos.llm.evaluacion.chequear_lateralidad
"""

from __future__ import annotations

import csv
import os
import re
import sys

from modelos.llm.evaluacion.datos_etiquetados import (
    CLASE_AMBIGUO, CLASE_NULL, cargar_heldout, cargar_suite_etiquetada, normalizar,
)
from modelos.llm.evaluacion.comun import asegurar_dir_resultados
from modelos.llm.evaluacion.verificar_heldout import CATALOGOS, expandir_barras

# Zona par -> patrón (sin tildes; incluye partes de la zona y typos vistos en los sets)
ZONAS_PARES = {
    "hombro":  r"\bhombros?\b",
    "pie":     r"\b(pies?|dedo gordo|primer dedo del pie|talon(es)?|calcaneos?)\b",
    "cadera":  r"\bcaderas?\b",
    "rodilla": r"\b(rodillas?|rodiyas?|rotulas?)\b",
    "mano":    r"\b(manos?|pulgar(es)?|escafoides)\b",
    "codo":    r"\bcodos?\b",
    "muñeca":  r"\b(munecas?)\b",
    "tobillo": r"\btobillos?\b",
}
LADOS = {
    "derecho":   r"\b(derech\w*|dcha|der)\b",
    "izquierdo": r"\b(izquierd|isquierd|izq)\w*",
    "ambos":     r"\b(ambos|ambas|bilateral(es)?|dos)\b",
}
# Zona par en plural sin lado explícito ("rayos de pies", "las rodillas"): se toma como
# ambos, pero se informa aparte porque la regla no lo dice explícitamente.
PLURALES = r"\b(hombros|pies|caderas|rodillas|rodiyas|rotulas|manos|pulgares|codos|munecas|tobillos|calcaneos|talones)\b"
CSV_PROPUESTA = "propuesta_lateralidad.csv"
VIOLACIONES = ("variante sin lado → estudio con lado", "lado distinto")


def zonas_pares(texto: str) -> list[str]:
    t = normalizar(texto)
    return [z for z, p in ZONAS_PARES.items() if re.search(p, t)]


def lados(texto: str, plural_es_ambos: bool = True) -> set[str]:
    """Lados mencionados. 'derecho e izquierdo' y (si plural_es_ambos) la zona en plural cuentan como ambos."""
    t = normalizar(texto)
    encontrados = {l for l, p in LADOS.items() if re.search(p, t)}
    if {"derecho", "izquierdo"} <= encontrados:
        encontrados.add("ambos")
    if not encontrados and plural_es_ambos and solo_plural(t):
        encontrados.add("ambos")
    return encontrados


def solo_plural(texto: str) -> bool:
    """La zona par aparece en plural sin lado explícito."""
    t = normalizar(texto)
    return bool(re.search(PLURALES, t)) and not any(re.search(p, t) for p in LADOS.values())


def contradiccion(caso: dict) -> str:
    """Motivo por el que la etiqueta contradice la regla ('' si no la contradice)."""
    zonas = zonas_pares(caso["input"])
    esperado = caso["esperado"]
    if not zonas or esperado == CLASE_NULL:
        return ""  # sin zona par, o fuera de dominio / sin estudio
    lado_msg, lado_est = lados(caso["input"]), lados(esperado) if esperado != CLASE_AMBIGUO else set()
    zona = ", ".join(zonas)
    if not lado_msg:
        return f"{zona} sin lado en el mensaje, etiqueta no AMBIGUO" if esperado != CLASE_AMBIGUO else ""
    if solo_plural(caso["input"]) and "ambos" not in lado_est:
        return f"{zona} en plural (se toma como ambos), estudio sin lado bilateral"
    if esperado == CLASE_AMBIGUO:
        return f"{zona} con lado ({', '.join(sorted(lado_msg))}), etiqueta AMBIGUO"
    if not lado_est:
        return f"{zona} con lado ({', '.join(sorted(lado_msg))}), estudio sin lado"
    if not lado_est <= lado_msg:
        return f"lado del estudio ({', '.join(sorted(lado_est))}) distinto al del mensaje"
    return ""


def cargar_propuesta(d: str) -> dict[tuple[str, str], dict]:
    ruta = os.path.join(d, CSV_PROPUESTA)
    if not os.path.exists(ruta):
        return {}
    with open(ruta, newline="", encoding="utf-8") as f:
        return {(r["set"], r["id"]): r for r in csv.DictReader(f)}


def chequear_etiquetas(d: str, casos: list[dict]) -> bool:
    propuesta = cargar_propuesta(d)
    filas = []
    for c in casos:
        motivo = contradiccion(c)
        p = propuesta.get((c["set"], c["id"]))
        if not motivo and not c["revisar"] and not p:
            continue
        filas.append({
            "set": c["set"], "id": c["id"], "input": c["input"], "esperado": c["esperado"],
            "revisar": c["revisar"], "contradice_regla": bool(motivo), "motivo": motivo,
            "propuesta_esperado": p["propuesta_esperado"] if p else "",
            "propuesta_tipo_ambiguedad": p["propuesta_tipo_ambiguedad"] if p else "",
            "propuesta_revisar": p["propuesta_revisar"] if p else "",
            "justificacion": p["justificacion"] if p else "",
        })

    sin_propuesta = [f for f in filas if f["contradice_regla"] and not f["propuesta_esperado"]]
    revisar_sin_propuesta = [f for f in filas if f["revisar"] and not f["propuesta_esperado"]]
    print("\n  ── 1. Etiquetas vs regla de lateralidad ──\n")
    print(f"  Contradicen la regla: {sum(f['contradice_regla'] for f in filas)} | "
          f"revisar=True: {sum(f['revisar'] for f in filas)} | "
          f"sin propuesta: {len(sin_propuesta)} contradicciones, {len(revisar_sin_propuesta)} revisar\n")
    for f in filas:
        if not f["contradice_regla"]:
            continue
        print(f"  {f['set']}/{f['id']}: «{f['input'][:50]}» = {f['esperado'][:45]}")
        print(f"      {f['motivo']}  →  propuesta: {f['propuesta_esperado'] or '(FALTA)'}"
              f"{' [' + f['propuesta_tipo_ambiguedad'] + ']' if f['propuesta_tipo_ambiguedad'] else ''}")

    ruta = os.path.join(d, "lateralidad_etiquetas.csv")
    with open(ruta, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    print(f"\n  Detalle (incluye las revisar=True): {os.path.relpath(ruta)}")
    return not sin_propuesta and not revisar_sin_propuesta


def variantes_catalogo(ruta: str) -> list[tuple[str, str]]:
    """(variante normalizada, preferred_term), expandiendo las alternativas con barra."""
    with open(ruta, newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    pares = []
    for r in filas:
        for cruda in r["variantes_coloquiales"].split(","):
            if cruda.strip():
                pares += [(normalizar(v), r["preferred_term"]) for v in expandir_barras(cruda.strip())]
    return pares


def chequear_catalogo(d: str, version: str) -> tuple[int, list[dict]]:
    pares = variantes_catalogo(CATALOGOS[version])
    filas = []
    for v, termino in pares:
        zonas = zonas_pares(v)
        if not zonas:
            continue
        lado_v, lado_t = lados(v), lados(termino)
        if not lado_v and lado_t:
            tipo = "variante sin lado → estudio con lado"
        elif solo_plural(v) and lado_t == {"ambos"}:
            tipo = "plural → estudio bilateral"  # permitido si plural = ambos
        elif lado_v and lado_t and not lado_t <= lado_v:
            tipo = "lado distinto"
        elif not lado_v and not lado_t:
            tipo = "sin lado → sin lado"  # permitido; se usa en el chequeo 3
        else:
            continue
        filas.append({"catalogo": version, "zona": ", ".join(zonas), "tipo": tipo, "variante": v,
                      "estudio": termino})
    violaciones = [f for f in filas if f["tipo"] in VIOLACIONES]
    return len(violaciones), filas


def main() -> int:
    d = asegurar_dir_resultados()
    casos = cargar_suite_etiquetada() + cargar_heldout()
    ok = chequear_etiquetas(d, casos)

    print("\n  ── 2. Catálogo: variantes con zona par vs lado del estudio ──\n")
    todas = []
    for version in ("v1", "v2.1"):
        n, filas = chequear_catalogo(d, version)
        todas += filas
        por_tipo = {}
        for f in filas:
            por_tipo[f["tipo"]] = por_tipo.get(f["tipo"], 0) + 1
        print(f"  {version}: violaciones = {n}  |  {por_tipo}")
        for f in filas:
            if f["tipo"] in VIOLACIONES:
                print(f"      [{f['tipo']}] «{f['variante']}» → {f['estudio']}")

    print("\n  ── 3. Por zona par (v2.1): variantes sin lado → estudio sin lado vs casos AMBIGUO/falta_lado ──\n")
    ambiguos = [c for c in casos if c["esperado"] == CLASE_AMBIGUO and zonas_pares(c["input"])
                and not lados(c["input"])]
    for zona in ZONAS_PARES:
        cs = [c for c in ambiguos if zona in zonas_pares(c["input"])]
        vs = sorted({(f["variante"], f["estudio"]) for f in todas
                     if f["catalogo"] == "v2.1" and f["tipo"] == "sin lado → sin lado" and zona in f["zona"].split(", ")})
        print(f"  {zona.upper()}: {len(cs)} caso(s) AMBIGUO sin lado "
              f"({', '.join(c['set'] + '/' + c['id'] for c in cs) or '—'}); "
              f"{len(vs)} variante(s) sin lado → estudio sin lado")

    ruta = os.path.join(d, "lateralidad_catalogo.csv")
    with open(ruta, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["catalogo", "zona", "tipo", "variante", "estudio"])
        w.writeheader()
        w.writerows(todas)
    print(f"\n  Detalle: {os.path.relpath(ruta)}\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
