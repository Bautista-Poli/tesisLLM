"""
generar_catalogo_v2.py — Genera el catálogo v2 o v2.1 a partir de la propuesta revisada.

No modifica el CSV original. Aplica resultados/propuesta_variantes.csv tal como esté:
  (a) la variante queda SOLO en estudio_por_defecto (se agrega si no la tenía,
      con su forma original más frecuente);
  (b) la variante se elimina de todos los estudios (solo v2; en v2.1 no se toca);
  (c) no se toca.
  v2   → CSVs/snomed_con_variantes_v2.csv   (a + b)
  v2.1 → CSVs/snomed_con_variantes_v2_1.csv (solo a)
Además (sin efecto en recuperación ni prompt, que no usan conceptId):
  - conceptId sin el ".0" final;
  - los conceptId en notación científica se reemplazan por el único candidato ±1
    con dígito verificador Verhoeff válido.

Valida que las demás columnas y el orden de filas no cambien.

Uso:
    python -m modelos.llm.evaluacion.generar_catalogo_v2                  # v2
    python -m modelos.llm.evaluacion.generar_catalogo_v2 --version v2.1
"""

from __future__ import annotations

import argparse
import csv
import io
import os
from collections import Counter, defaultdict
from decimal import Decimal

from modelos.llm.evaluacion.analizar_catalogo import limpiar_id, verhoeff_valido
from modelos.llm.evaluacion.comun import asegurar_dir_resultados
from modelos.llm.evaluacion.datos_etiquetados import normalizar
from modelos.llm.extractor import CSV_TERMINOS

CSV_V2 = CSV_TERMINOS.replace("snomed_con_variantes.csv", "snomed_con_variantes_v2.csv")
CSV_V2_1 = CSV_TERMINOS.replace("snomed_con_variantes.csv", "snomed_con_variantes_v2_1.csv")
VERSIONES = {"v2": (CSV_V2, "abc"), "v2.1": (CSV_V2_1, "ac")}  # versión -> (salida, acciones aplicadas)


def corregir_id(crudo: str) -> tuple[str, str]:
    """(conceptId limpio, nota)."""
    crudo = crudo.strip()
    if not crudo:
        return "", ""
    if "e" in crudo.lower():
        redondeado = int(Decimal(crudo))
        validos = [str(x) for x in (redondeado - 1, redondeado, redondeado + 1) if verhoeff_valido(str(x))]
        if len(validos) == 1:
            return validos[0], f"{crudo} → {validos[0]} (Verhoeff)"
        return limpiar_id(crudo), f"{crudo}: sin candidato único válido, se deja el valor redondeado"
    return limpiar_id(crudo), ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera el catálogo v2 (acciones a y b) o v2.1 (solo a).")
    parser.add_argument("--version", choices=list(VERSIONES), default="v2")
    args = parser.parse_args()
    csv_salida, aplicadas = VERSIONES[args.version]
    d = asegurar_dir_resultados()
    with open(CSV_TERMINOS, newline="", encoding="utf-8") as f:
        original = list(csv.DictReader(f))
        f.seek(0)
        columnas = next(csv.reader(f))
    with open(os.path.join(d, "propuesta_variantes.csv"), newline="", encoding="utf-8") as f:
        propuesta = {r["variante_normalizada"]: r for r in csv.DictReader(f)}
    for p in propuesta.values():  # acciones que esta versión no aplica quedan como (c)
        if p["accion"] not in aplicadas:
            p["accion"] = "c"

    catalogo = {r["preferred_term"] for r in original}
    for v, p in propuesta.items():
        if p["accion"] == "a" and p["estudio_por_defecto"] not in catalogo:
            raise SystemExit(f"La variante «{v}» apunta a un estudio que no existe: {p['estudio_por_defecto']!r}")

    # Forma original más frecuente de cada variante normalizada (para agregarla donde falte)
    formas = defaultdict(Counter)
    for r in original:
        for v in r["variantes_coloquiales"].split(","):
            if v.strip():
                formas[normalizar(v)][v.strip()] += 1

    eliminadas = Counter()
    nuevas, notas_id = [], []
    for r in original:
        conservar, presentes = [], set()
        for v in r["variantes_coloquiales"].split(","):
            v = v.strip()
            if not v:
                continue
            p = propuesta.get(normalizar(v))
            if p and p["accion"] == "b":
                eliminadas["b"] += 1
                continue
            if p and p["accion"] == "a" and r["preferred_term"] != p["estudio_por_defecto"]:
                eliminadas["a"] += 1
                continue
            conservar.append(v)
            presentes.add(normalizar(v))
        nueva = dict(r)
        nueva["_presentes"] = presentes
        nueva["_variantes"] = conservar
        nuevo_id, nota = corregir_id(r["conceptId"])
        nueva["conceptId"] = nuevo_id
        if nota:
            notas_id.append(f"{r['preferred_term']}: {nota}")
        nuevas.append(nueva)

    # (a) hacia un estudio que no tenía la variante: agregarla
    por_termino = {r["preferred_term"]: r for r in nuevas}
    agregadas = []
    for v, p in propuesta.items():
        if p["accion"] != "a":
            continue
        destino = por_termino[p["estudio_por_defecto"]]
        if v not in destino["_presentes"]:
            forma = formas[v].most_common(1)[0][0]
            destino["_variantes"].append(forma)
            destino["_presentes"].add(v)
            agregadas.append(f"«{forma}» → {p['estudio_por_defecto']}")

    for r in nuevas:
        r["variantes_coloquiales"] = ", ".join(r.pop("_variantes"))
        r.pop("_presentes")

    # Validaciones: mismas filas y columnas; solo cambian conceptId y variantes_coloquiales
    assert [r["preferred_term"] for r in nuevas] == [r["preferred_term"] for r in original]
    fijas = [c for c in columnas if c not in ("conceptId", "variantes_coloquiales")]
    assert all(a[c] == b[c] for a, b in zip(original, nuevas) for c in fijas)
    compartidas = Counter()
    for r in nuevas:
        for v in {normalizar(x) for x in r["variantes_coloquiales"].split(",") if x.strip()}:
            compartidas[v] += 1
    for v, p in propuesta.items():
        if p["accion"] == "a":
            assert compartidas[v] == 1, f"«{v}» quedó en {compartidas[v]} estudios"
        if p["accion"] == "b":
            assert compartidas[v] == 0, f"«{v}» sigue en {compartidas[v]} estudios"

    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=columnas, lineterminator="\n")
    w.writeheader()
    w.writerows(nuevas)
    with open(csv_salida, "w", newline="", encoding="utf-8") as f:
        f.write(out.getvalue())

    def n_var(filas):
        return sum(len([v for v in r["variantes_coloquiales"].split(",") if v.strip()]) for r in filas)
    sin_var = lambda filas: sum(1 for r in filas if not r["variantes_coloquiales"].strip())
    cambiadas = sum(a["variantes_coloquiales"] != b["variantes_coloquiales"] for a, b in zip(original, nuevas))
    acciones = Counter(p["accion"] for p in propuesta.values())
    v = args.version

    lineas = [
        f"Catálogo {v}: {os.path.relpath(csv_salida)}",
        f"Propuesta aplicada: a = {acciones['a']}, b = {acciones['b']}, c (sin tocar) = {acciones['c']}"
        + (" (las b de la propuesta se dejan como c)" if "b" not in aplicadas else ""),
        f"Ocurrencias de variantes: v1 = {n_var(original)} → {v} = {n_var(nuevas)}",
        f"  eliminadas por (a) de estudios no por defecto: {eliminadas['a']}",
        f"  eliminadas por (b): {eliminadas['b']}",
        f"  agregadas al estudio por defecto: {len(agregadas)}",
        f"Estudios con variantes modificadas: {cambiadas} de {len(nuevas)}",
        f"Estudios sin variantes: v1 = {sin_var(original)} → {v} = {sin_var(nuevas)}",
        f"Variantes que siguen compartidas (solo las de acción c): {sum(1 for c in compartidas.values() if c > 1)}",
        "conceptId: sin '.0'; corregidos por notación científica:",
        *[f"  {n}" for n in notas_id],
        "Validado: mismas filas, mismo orden; solo cambian conceptId y variantes_coloquiales.",
        "", "Variantes agregadas:", *[f"  {a}" for a in agregadas],
    ]
    print("\n" + "\n".join(lineas) + "\n")
    nombre = "generacion_catalogo_v2.txt" if v == "v2" else "generacion_catalogo_v2_1.txt"
    with open(os.path.join(d, nombre), "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")


if __name__ == "__main__":
    main()
