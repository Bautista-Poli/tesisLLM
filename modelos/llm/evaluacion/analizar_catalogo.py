"""
analizar_catalogo.py — Reportes y propuestas de limpieza del catálogo SNOMED.

Solo LEE CSVs/snomed_con_variantes.csv (no lo modifica) y genera en resultados/:

  1. variantes_compartidas.csv   variantes (sin tildes/minúsculas) presentes en 2+ estudios
  2. propuesta_variantes.csv     acción propuesta por variante compartida:
                                   a = dejarla solo en el estudio por defecto
                                   b = eliminarla de todos (ambigua / sin zona)
                                   c = dudosa (revisar)
                                 revisar_sugerencia = true: (a) hacia un estudio que no tenía la
                                 variante (se agrega); volver a c para no aplicarla
     propuesta_estudios.csv      por estudio: frecuente y pedible_por_turno (propuesta)
  3. estudios_sin_variantes.csv  estudios con variantes_coloquiales vacías
     filas_conceptid.csv         filas sin conceptId y conceptId dañados (notación
                                 científica), con dígito verificador Verhoeff

Todo es PROPUESTA para revisión manual: no se aplica nada.

Uso:
    python -m modelos.llm.evaluacion.analizar_catalogo
"""

from __future__ import annotations

import csv
import os
import re
from collections import defaultdict
from decimal import Decimal

import pandas as pd

from modelos.llm.evaluacion.comun import asegurar_dir_resultados
from modelos.llm.evaluacion.datos_etiquetados import normalizar
from modelos.llm.extractor import CSV_TERMINOS

# ─── Reglas de la propuesta ──────────────────────────────────────────────────

# Palabras sin contenido anatómico: si una variante solo tiene estas, no identifica estudio
GENERICAS = {
    "rayos", "rayo", "rx", "placa", "placas", "radiografia", "radiografias", "simple", "simples",
    "de", "del", "la", "el", "los", "las", "x", "mi", "y", "e", "ap", "lateral", "frente", "perfil",
    "derecha", "derecho", "izquierda", "izquierdo", "abajo", "tejido", "blando",
}
SEGMENTOS_COLUMNA = r"(cervical|dorsal|lumbar|sacra|toracica|lumbosacra)"

# (regex sobre la variante normalizada, acción forzada, motivo) — se evalúan en orden
REGLAS_FIJAS = [
    (r"\bespalda baja\b", None, None),  # no es ambigua: se resuelve por zona canónica
    (r"\bespalda\b", "b", "espalda: cervical, dorsal o lumbar (regla de ambigüedad del sistema)"),
    (r"\bpiernas?\b", "b", "pierna: tibia/peroné, fémur o rodilla (regla de ambigüedad del sistema)"),
    (r"\bbrazos?\b", "b", "brazo: húmero o antebrazo (regla de ambigüedad del sistema)"),
    (rf"\b(columna|espina)\b(?!.*\b{SEGMENTOS_COLUMNA}\b)", "b",
     "columna sin segmento (regla de ambigüedad del sistema)"),
    (r"\bmamas?\b", "b", "mama: la mamografía no está en el catálogo; apunta a espécimen/resecado"),
    (r"\b(huesos|esqueleto)\b", "c", "demasiado general: barrido de esqueleto vs sistema musculoesquelético"),
    (r"\b(ambas caderas|las caderas)\b", None, None),
    (r"\bcadera\b", "c", "cadera sin más: el sistema la trata como AMBIGUO aunque exista 'radiografía simple de cadera' (ver etiquetas revisar)"),
    (r"\b(los hombros)\b", None, None),
    (r"\bhombro\b(?!.*\b(derech|izquierd))", "c", "hombro sin lateralidad: el sistema lo trata como AMBIGUO (ver etiquetas revisar)"),
    (r"\bpie\b(?!.*\b(derech|izquierd))(?!.*\bdedo)", "c", "pie sin lateralidad: el sistema lo trata como AMBIGUO (ver etiquetas revisar)"),
    (r"\bcuello\b", "c", "cuello: columna cervical o partes blandas del cuello"),
    (r"\bnuca\b", "c", "nuca: probablemente columna cervical; revisar"),
    (r"(?<!sin )\bcontraste\b", "c", "estudio contrastado: elegir manualmente"),
]

# (regex, estudio canónico) — zona → estudio por defecto. Primero lo más específico.
CANONICOS = [
    (r"\bcolumna (vertebral )?lumbar y sacra\b", "radiografía simple de columna vertebral lumbar y sacra"),
    (r"\bespalda baja\b", "radiografía simple de columna lumbar"),
    (r"\bcolumna cervical\b", "radiografía simple de columna vertebral cervical"),
    (r"\b(torax|pecho)\b", "radiografía simple de tórax"),
    (r"\babdomen superior\b", "radiografía simple de abdomen superior"),
    (r"\b(abdomen|barriga|panza)\b", "radiografía simple de abdomen"),
    (r"\bantebrazo derecho\b", "radiografía simple de antebrazo derecho"),
    (r"\bantebrazo izquierdo\b", "radiografía simple de antebrazo izquierdo"),
    (r"\bantebrazo\b", "radiografía simple de antebrazo"),
    (r"\bcodo\b", "radiografía simple de codo"),
    (r"\b(craneo|cabeza)\b", "radiografía simple de cráneo"),
    (r"\bambas manos\b", "radiografía simple de ambas manos"),
    (r"\bmano derecha\b", "radiografía simple de mano derecha"),
    (r"\bmano izquierda\b", "radiografía simple de mano izquierda"),
    (r"\bmano\b", "radiografía simple de mano"),
    (r"\bmuneca derecha\b", "radiografía simple de muñeca derecha"),
    (r"\bmuneca izquierda\b", "radiografía simple de muñeca izquierda"),
    (r"\bmuneca\b", "radiografía simple de muñeca"),
    (r"\brodilla\b", "radiografía simple de región de rodilla"),
    (r"\btobillo izquierdo\b", "radiografía simple de tobillo izquierdo"),
    (r"\btobillo derecho\b", "radiografía de tobillo derecho"),
    (r"\btobillo\b", "radiografía simple de región de tobillo"),
    (r"\bpelvis\b", "radiografía simple de pelvis"),
    (r"\bclavicula\b", "radiografía simple de clavícula"),
    (r"\bhumero\b", "radiografía simple de húmero"),
    (r"\bfemur izquierdo\b", "radiografía simple de fémur izquierdo"),
    (r"\bfemur\b", "radiografía de fémur"),
    (r"\bmuslo\b", "radiografía simple de muslo"),
    (r"\btibia y perone\b", "radiografía simple de tibia y peroné"),
    (r"\btibia\b", "radiografía simple de tibia"),
    (r"\bcubito\b", "radiografía de cúbito"),
    (r"\bradio\b", "radiografía simple de radio"),
    (r"\bescafoides\b", "radiografía de escafoides"),
    (r"\bsacro\b", "radiografía simple de hueso de sacro"),
    (r"\bnariz\b", "radiografía simple de nariz"),
    (r"\bcara\b", "radiografía simple de cara"),
    (r"\bhombro derecho\b", "radiografía simple de hombro derecho"),
    (r"\bhombro izquierdo\b", "radiografía simple de hombro izquierdo"),
    (r"\blos hombros\b", "radiografía simple de ambos hombros"),
    (r"\b(ambas caderas|las caderas)\b", "radiografía simple de ambas caderas"),
    (r"\b(ambos pies|pies)\b", "radiografía simple bilateral de pies"),
    (r"\bdedo del pie derecho\b", "radiografía simple de dedo de pie derecho"),
    (r"\bpie derecho\b", "radiografía de pie derecho"),
    (r"\bpie izquierdo\b", "radiografía de pie izquierdo"),
    (r"\bomoplato derecho\b", "radiografía simple de omóplato derecho"),
    (r"\bmaxilar inferior\b", "radiografía simple de maxilar inferior"),
    (r"\brinon\b", "radiografía simple de riñón"),
    (r"\bpene\b", "radiografía simple de pene"),
    (r"\bprostata\b", "radiografía simple de próstata"),
    (r"\boido\b", "radiografía simple de oído"),
    (r"\boclusal\b", "radiografía dental oclusal"),
    (r"\bmiembro superior derecho\b", "radiografía simple de miembro superior derecho"),
]

# Estudios que no se piden por turno ambulatorio
NO_PEDIBLE = [
    (r"intensificador", "con intensificador de imágenes móvil (intraoperatorio / en quirófano)"),
    (r"shunt|derivacion", "control de derivación / shunt (indicación hospitalaria)"),
    (r"cribado", "cribado poblacional, no a pedido"),
    (r"especimen|resecado|muestra de tejido", "radiografía de pieza / espécimen quirúrgico"),
    (r"diente extraido", "pieza dental extraída"),
    (r"drenaje", "control de drenaje con contraste (indicación hospitalaria)"),
    (r"implante coclear", "control de implante (posquirúrgico); revisar"),
]

# Zonas de radiología simple ambulatoria frecuente
ZONAS_FRECUENTES = (r"\b(torax|columna|espinograma|escanometria|rodilla|tobillo|pie|pies|mano|manos|muneca|codo|"
                    r"hombro|cadera|caderas|pelvis|femur|tibia|perone|antebrazo|humero|clavicula|craneo|"
                    r"senos paranasales|abdomen|panoramica|edad osea|nasofaringe|calcaneo|rotula|costilla|"
                    r"escafoides|sacro|sacroiliaca|sacroiliacas|dedo|dedos|cara|nariz)\b")
CALIFICADORES = (r"(tejido blando|partes blandas|proyecci|vista|oblicu|contraste|diafisis|cabeza de|cabeza del|"
                 r"cuello de|apofisis|esfuerzo|estres|flexion|decubito|supina|bipedestacion|lordotica|apical|"
                 r"tunel|sesamoideo|, lateral|en carga|seriada|intensificador|cribado|receptor|hueso de|"
                 r"region posterior|porcion media|union |articulacion atl)")

# Filas sin conceptId: términos relacionados del CSV y pista de búsqueda para el browser
PISTAS_SIN_ID = {
    "cistouretrografía miccional": ("—", "voiding cystourethrography"),
    "radiografía seriada esofagogastroduodenal": (
        "radiografía seriada de tracto gastrointestinal superior con contraste de bario",
        "upper gastrointestinal series / barium meal"),
    "escanometría de miembros inferiores": (
        "radiografía simple de extremidad inferior para medición de longitud de hueso (449616006); "
        "radiografía digital con haz hendido, longitud de pierna (241599006)",
        "scanogram / leg length radiography — posible mismo concepto que 449616006"),
    "radiografía seriada de ambos maxilares": ("—", "maxilla and mandible radiography series"),
    "serie periapical completa": (
        "radiografía simple dental de boca completa, proyección periapical (1290848005)",
        "full mouth periapical series — posible mismo concepto que 1290848005"),
}

# ─── Verhoeff (dígito verificador de los SCTID) ───────────────────────────────

_D = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
      [3, 4, 0, 1, 2, 8, 9, 5, 6, 7], [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
      [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3], [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
      [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]]
_P = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
      [8, 9, 1, 6, 0, 4, 3, 5, 2, 7], [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
      [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]]


def verhoeff_valido(numero: str) -> bool:
    c = 0
    for i, digito in enumerate(reversed(numero)):
        c = _D[c][_P[i % 8][int(digito)]]
    return c == 0


def limpiar_id(crudo: str) -> str:
    """'171229005.0' -> '171229005'; notación científica -> entero (puede haber perdido dígitos)."""
    crudo = crudo.strip()
    if not crudo:
        return ""
    return str(int(Decimal(crudo)))


# ─── Análisis ────────────────────────────────────────────────────────────────

def variantes_por_estudio(df: pd.DataFrame) -> tuple[dict, dict]:
    mapa, formas = defaultdict(list), defaultdict(set)
    for _, r in df.iterrows():
        for v in r.variantes_coloquiales.split(","):
            v = v.strip()
            if not v:
                continue
            vn = normalizar(v)
            if r.preferred_term not in mapa[vn]:
                mapa[vn].append(r.preferred_term)
            formas[vn].add(v)
    return mapa, formas


def proponer_accion(variante: str, estudios: list[str], catalogo: set[str]) -> tuple[str, str, str]:
    """(acción, estudio_por_defecto, motivo)."""
    if set(variante.split()) <= GENERICAS:
        return "b", "", "sin zona anatómica: no identifica un estudio"
    for patron, accion, motivo in REGLAS_FIJAS:
        if re.search(patron, variante):
            if accion is None:
                break
            return accion, "", motivo
    for patron, canonico in CANONICOS:
        if re.search(patron, variante):
            if canonico not in catalogo:
                return "c", "", f"el estudio por defecto propuesto ({canonico}) no está en el catálogo"
            if canonico in estudios:
                otros = len(estudios) - 1
                return "a", canonico, f"zona con estudio por defecto; se quita de {otros} estudio(s) más"
            return "a", canonico, ("sugerido (antes c): el estudio por defecto no tenía esta variante; "
                                   "queda solo en ese estudio (se agrega). Volver a c si no se aprueba")
    return "c", "", "sin estudio por defecto claro entre los candidatos"


def proponer_estudio(termino: str) -> dict:
    t = normalizar(termino)
    for patron, motivo in NO_PEDIBLE:
        if re.search(patron, t):
            return {"frecuente": False, "pedible_por_turno": False, "motivo": motivo}
    frecuente = bool(re.search(ZONAS_FRECUENTES, t)) and not re.search(CALIFICADORES, t)
    motivo = "zona frecuente sin calificadores técnicos" if frecuente else (
        "tiene calificador técnico (proyección, tejido blando, contraste, etc.)" if re.search(ZONAS_FRECUENTES, t)
        else "zona poco frecuente en radiología ambulatoria")
    return {"frecuente": frecuente, "pedible_por_turno": True, "motivo": motivo}


def escribir(ruta: str, filas: list[dict]) -> None:
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    print(f"  {os.path.relpath(ruta)}  ({len(filas)} filas)")


def main() -> None:
    df = pd.read_csv(CSV_TERMINOS, dtype=str, keep_default_na=False)
    catalogo = set(df.preferred_term)
    d = asegurar_dir_resultados()
    mapa, formas = variantes_por_estudio(df)
    ids = dict(zip(df.preferred_term, df.conceptId.map(limpiar_id)))

    # 1. Variantes compartidas
    compartidas = sorted(((v, e) for v, e in mapa.items() if len(e) > 1), key=lambda x: (-len(x[1]), x[0]))
    print(f"\n  Variantes distintas: {len(mapa)} | compartidas por 2+ estudios: {len(compartidas)}")
    escribir(os.path.join(d, "variantes_compartidas.csv"), [
        {"variante_normalizada": v, "n_estudios": len(e), "estudios": " | ".join(e),
         "conceptIds": " | ".join(ids[t] for t in e), "formas_originales": " | ".join(sorted(formas[v]))}
        for v, e in compartidas])

    # 2. Propuestas
    filas_var = []
    for v, e in compartidas:
        accion, defecto, motivo = proponer_accion(v, e, catalogo)
        filas_var.append({"variante_normalizada": v, "n_estudios": len(e), "accion": accion,
                          "estudio_por_defecto": defecto,
                          "revisar_sugerencia": accion == "a" and defecto not in e,
                          "motivo": motivo, "estudios": " | ".join(e),
                          "formas_originales": " | ".join(sorted(formas[v]))})
    conteo = {a: sum(f["accion"] == a for f in filas_var) for a in "abc"}
    print(f"  Propuesta: a (dejar en el estudio por defecto) = {conteo['a']}, "
          f"b (eliminar) = {conteo['b']}, c (dudosa) = {conteo['c']}")
    escribir(os.path.join(d, "propuesta_variantes.csv"), filas_var)

    n_var = {t: len([v for v in r.split(",") if v.strip()]) for t, r in zip(df.preferred_term, df.variantes_coloquiales)}
    filas_est = [{"conceptId": ids[t], "preferred_term": t, "n_variantes": n_var[t], **proponer_estudio(t)}
                 for t in df.preferred_term]
    print(f"  Estudios: frecuente = {sum(f['frecuente'] for f in filas_est)}, "
          f"no pedibles por turno = {sum(not f['pedible_por_turno'] for f in filas_est)}")
    escribir(os.path.join(d, "propuesta_estudios.csv"), filas_est)

    # 3. Estudios sin variantes y conceptId faltantes o dañados
    escribir(os.path.join(d, "estudios_sin_variantes.csv"), [
        {"conceptId": ids[r.preferred_term], "preferred_term": r.preferred_term, "fsn": r.fsn}
        for _, r in df.iterrows() if not r.variantes_coloquiales.strip()])

    filas_id = []
    for _, r in df.iterrows():
        crudo = r.conceptId.strip()
        if not crudo:
            relacionados, pista = PISTAS_SIN_ID.get(r.preferred_term, ("—", ""))
            filas_id.append({"problema": "sin conceptId", "conceptId_actual": "", "conceptId_propuesto": "",
                             "preferred_term": r.preferred_term, "fsn": r.fsn,
                             "nota": f"buscar en el browser de SNOMED (pista: {pista}). "
                                     f"Relacionados en el CSV: {relacionados}"})
        elif "e" in crudo.lower():
            redondeado = int(Decimal(crudo))
            validos = [str(x) for x in (redondeado - 1, redondeado, redondeado + 1) if verhoeff_valido(str(x))]
            filas_id.append({"problema": "notación científica (perdió precisión)", "conceptId_actual": crudo,
                             "conceptId_propuesto": " o ".join(validos) or "",
                             "preferred_term": r.preferred_term, "fsn": r.fsn,
                             "nota": ("único candidato ±1 con dígito verificador Verhoeff válido; confirmar en el browser"
                                      if len(validos) == 1 else "ambiguo o sin candidato válido: buscar en el browser")})
        elif not verhoeff_valido(limpiar_id(crudo)):
            filas_id.append({"problema": "dígito verificador inválido", "conceptId_actual": crudo,
                             "conceptId_propuesto": "", "preferred_term": r.preferred_term, "fsn": r.fsn,
                             "nota": "revisar en el browser de SNOMED"})
    escribir(os.path.join(d, "filas_conceptid.csv"), filas_id)
    print()


if __name__ == "__main__":
    main()
