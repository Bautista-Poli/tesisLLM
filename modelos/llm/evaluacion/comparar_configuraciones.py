"""
comparar_configuraciones.py — Comparación de configuraciones sobre los sets etiquetados.

Todas las configuraciones se corren sobre los MISMOS casos (suite_etiquetada y heldout):
  a)  TF-IDF palabras, top-1                 (sin LLM)
  b)  TF-IDF n-gramas de caracteres, top-1   (char_wb 3-5, sin LLM)
  b2) TF-IDF char 3-5 con umbrales           (sin LLM): si coseno top-1 < umbral_null → null;
                                             si no, si margen top1−top2 < umbral_margen → AMBIGUO;
                                             si no, top-1. Umbrales calibrados SOLO sobre la suite.
  c)  LLM + RAG palabras, k=5
  d)  LLM + RAG n-gramas de caracteres, k=5
  e)  LLM sin contexto RAG                   (tablas de estudios y coberturas vacías)
  f)  d) + salida restringida: `format` de Ollama con JSON schema donde `estudio` es
      enum de los preferred_term recuperados + "AMBIGUO" + null. Sin normalizar_estudio.
  g)  f) + criterio de ambigüedad genérico en el prompt (reemplaza la lista fija de
      zonas) + 4 ejemplos few-shot tomados de la suite.
  i)  f) + 3 ejemplos few-shot de la suite SOLO de fuera de dominio (→ null),
      manteniendo la lista original de zonas ambiguas del prompt.

Catálogo: --catalogo v1 (CSVs/snomed_con_variantes.csv, default), v2 o v2.1
(snomed_con_variantes_v2.csv / _v2_1.csv). Las corridas se guardan como "<config>@v2" o "@v2.1".

Los defaults del sistema no cambian (rag.TOP_K=3, analizador por palabras, prompt y
modelo de prompt.py / ollama_client.py): todo se pasa como parámetro. El pipeline LLM
es el de los tests (prompt + Ollama + parseo [+ normalizar_estudio en c/d/e]), sin historial.

Reporta por configuración y set: recall@k de la recuperación, accuracy estricta,
P/R/F1 macro (AMBIGUO y null siempre como clases), F1 de AMBIGUO y de null, la
métrica laxa anterior, errores de parseo, latencia media y mediana, y la caída
suite → heldout.

Requiere Ollama para las configuraciones c a g.

Uso:
    python -m modelos.llm.evaluacion.comparar_configuraciones
    python -m modelos.llm.evaluacion.comparar_configuraciones --configs a b b2
    python -m modelos.llm.evaluacion.comparar_configuraciones --configs f --sets suite --reusar
    python -m modelos.llm.evaluacion.comparar_configuraciones --configs f i --catalogo v2 --reusar
        (--reusar conserva de comparacion_por_caso.csv las predicciones de los pares
         config/set que no se corren y recalcula todas las métricas con las etiquetas actuales)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import statistics
import time
from functools import lru_cache

from modelos.llm.estudios import normalizar_estudio
from modelos.llm.evaluacion.comun import asegurar_dir_resultados, tipo_error
from modelos.llm.evaluacion.datos_etiquetados import CLASE_AMBIGUO, CLASE_NULL, SETS, TIPOS_AMBIGUEDAD
from modelos.llm.evaluacion.metricas import (
    clase_desde_slots, correcto_laxo, es_termino, f1_ambiguo_por_tipo, gold_laxo, metricas_estrictas,
    metricas_laxas,
)
from modelos.llm.extractor import CSV_COBERTURAS, CSV_TERMINOS
from modelos.llm.ollama_client import extraer_json, llamar_ollama
from modelos.llm.prompt import construir_system_prompt
from modelos.llm.rag import (
    buscar_coberturas_relevantes, buscar_relevantes, buscar_terminos_relevantes,
    cargar_coberturas, cargar_terminos, similitudes_tfidf,
)

CONFIGS = {
    "a":  {"nombre": "TF-IDF palabras top-1",      "llm": False, "analizador": "palabras"},
    "b":  {"nombre": "TF-IDF char 3-5 top-1",      "llm": False, "analizador": "char"},
    "b2": {"nombre": "TF-IDF char 3-5 + umbrales", "llm": False, "analizador": "char", "umbrales": True},
    "c":  {"nombre": "LLM + RAG palabras",         "llm": True,  "analizador": "palabras"},
    "d":  {"nombre": "LLM + RAG char 3-5",         "llm": True,  "analizador": "char"},
    "e":  {"nombre": "LLM sin RAG",                "llm": True,  "analizador": None},
    "f":  {"nombre": "d + salida restringida",     "llm": True,  "analizador": "char", "restringida": True},
    "g":  {"nombre": "f + ambigüedad genérica + few-shot", "llm": True, "analizador": "char",
           "restringida": True, "paso2_generico": True,
           "few_shot": ("torax_especifico", "rodilla_especifica", "pierna_ambigua", "fuera_dominio_resonancia")},
    "i":  {"nombre": "f + few-shot fuera de dominio", "llm": True, "analizador": "char",
           "restringida": True,
           "few_shot": ("fuera_dominio_resonancia", "fuera_dominio_ecografia", "fuera_dominio_laboratorio")},
}

CATALOGOS = {"v1": CSV_TERMINOS,
             "v2": CSV_TERMINOS.replace("snomed_con_variantes.csv", "snomed_con_variantes_v2.csv"),
             "v2.1": CSV_TERMINOS.replace("snomed_con_variantes.csv", "snomed_con_variantes_v2_1.csv")}


def base_config(clave: str) -> str:
    """'f@v2' -> 'f'."""
    return clave.split("@")[0]


def catalogo_de(clave: str) -> str:
    return clave.split("@")[1] if "@" in clave else "v1"


SIN_CONTEXTO = "No disponible."
_RE_TERMINO = re.compile(r'preferred_term: "(.*?)"')
CSV_POR_CASO = "comparacion_por_caso.csv"


PASO2_GENERICO = """PASO 2 — Compará la zona mencionada con los candidatos de la TABLA DE ESTUDIOS.
        Si 2 o más candidatos coinciden con la zona mencionada y el mensaje no permite
        distinguirlos → AMBIGUO (estudio = "AMBIGUO", estudio_ambiguo = true).
        Si un solo candidato corresponde a la zona mencionada, ese es el estudio.

        """


# ─── Prompt y schema de f/g/h ─────────────────────────────────────────────────

def schema_salida(candidatos: list[str]) -> dict:
    """JSON schema de la salida: `estudio` restringido a los candidatos + AMBIGUO + null."""
    texto = {"type": ["string", "null"]}
    return {
        "type": "object",
        "properties": {
            "nombre_completo": texto, "dni": texto,
            "estudio": {"enum": list(dict.fromkeys(candidatos)) + [CLASE_AMBIGUO, None]},
            "estudio_ambiguo": {"type": "boolean"},
            "pregunta_aclaracion": texto, "obra_social": texto, "sede": texto,
            "dias_disponibles": texto, "horario": texto,
        },
        "required": ["nombre_completo", "dni", "estudio", "estudio_ambiguo", "pregunta_aclaracion",
                     "obra_social", "sede", "dias_disponibles", "horario"],
    }


@lru_cache(maxsize=None)
def bloque_few_shot(ids: tuple, k: int, analizador: str, csv_catalogo: str) -> str:
    """Ejemplos few-shot (solo casos de la suite) con sus candidatos recuperados del catálogo dado."""
    df = cargar_terminos(csv_catalogo)
    suite = {c["id"]: c for c in SETS["suite"]()}
    lineas = ["EJEMPLOS (de otros mensajes; cada uno con sus propios candidatos, que NO son los de este mensaje):"]
    for i in ids:
        caso = suite[i]
        candidatos = _RE_TERMINO.findall(buscar_terminos_relevantes(caso["input"], df, k, analizador))
        esperado = caso["esperado"]
        assert esperado in (CLASE_AMBIGUO, CLASE_NULL) or esperado in candidatos, (i, esperado)
        salida = {"estudio": None if esperado == CLASE_NULL else esperado,  # AMBIGUO se escribe tal cual
                  "estudio_ambiguo": esperado == CLASE_AMBIGUO}
        lineas += [f'    Mensaje: "{caso["input"]}"',
                   "    Candidatos: " + " | ".join(candidatos),
                   "    Salida (campos de estudio): " + json.dumps(salida, ensure_ascii=False), ""]
    return "\n".join(lineas)


def reemplazar_paso2(prompt: str) -> str:
    """Reemplaza el PASO 2 (lista fija de zonas) por el criterio genérico de ambigüedad."""
    nuevo, n = re.subn(r"PASO 2 —.*?(?=PASO 3 —)", lambda _: PASO2_GENERICO, prompt, flags=re.DOTALL)
    assert n == 1, "no se encontró el PASO 2 en el prompt"
    return nuevo


def agregar_few_shot(prompt: str, bloque: str) -> str:
    marcador = "TABLA DE ESTUDIOS (relevantes para este mensaje):"
    assert prompt.count(marcador) == 1
    return prompt.replace(marcador, bloque + "\n    " + marcador)


# ─── Predicción por configuración ────────────────────────────────────────────

def predecir_tfidf(item: dict, df_terminos, analizador: str) -> str:
    return df_terminos.iloc[buscar_relevantes(item["input"], df_terminos, 1, analizador)[0]]["preferred_term"]


def puntajes_tfidf(item: dict, df_terminos, analizador: str) -> tuple[str, float, float]:
    """(término top-1, coseno top-1, margen top1−top2)."""
    sims = similitudes_tfidf(item["input"], df_terminos, analizador)
    orden = sims.argsort()[::-1]
    return df_terminos.iloc[orden[0]]["preferred_term"], float(sims[orden[0]]), float(sims[orden[0]] - sims[orden[1]])


def aplicar_umbrales(top1: str, coseno: float, margen: float, umbrales: dict) -> str:
    if coseno < umbrales["umbral_null"]:
        return CLASE_NULL
    if margen < umbrales["umbral_margen"]:
        return CLASE_AMBIGUO
    return top1


def predecir_llm(item: dict, df_terminos, df_coberturas, cfg: dict, k: int, csv_catalogo: str) -> str:
    analizador = cfg["analizador"]
    if analizador is None:
        ctx_estudios = ctx_coberturas = SIN_CONTEXTO
    else:
        ctx_estudios = buscar_terminos_relevantes(item["input"], df_terminos, k, analizador)
        ctx_coberturas = buscar_coberturas_relevantes(item["input"], df_coberturas)
    prompt = construir_system_prompt(ctx_estudios, ctx_coberturas, item["ultima_pregunta"], [])
    if cfg.get("paso2_generico"):
        prompt = reemplazar_paso2(prompt)
    if cfg.get("few_shot"):
        prompt = agregar_few_shot(prompt, bloque_few_shot(cfg["few_shot"], k, analizador, csv_catalogo))

    formato = schema_salida(_RE_TERMINO.findall(ctx_estudios)) if cfg.get("restringida") else None
    raw = llamar_ollama([{"role": "system", "content": prompt},
                         {"role": "user", "content": item["input"]}],
                        formato=formato)
    slots = extraer_json(raw)
    if not cfg.get("restringida") and slots.get("estudio") and not slots.get("estudio_ambiguo"):
        slots["estudio"] = normalizar_estudio(slots["estudio"], df_terminos)
    return clase_desde_slots(slots)


# ─── Calibración de umbrales (b2) ────────────────────────────────────────────

def _candidatos(valores: list[float]) -> list[float]:
    """0 (sin umbral), puntos medios entre valores observados y un valor por encima del máximo."""
    v = sorted(set(valores))
    return [0.0] + [(x + y) / 2 for x, y in zip(v, v[1:])] + [v[-1] + 1e-6]


def calibrar_umbrales(items: list[dict], df_terminos, analizador: str) -> dict:
    """
    Búsqueda en grilla de (umbral_null, umbral_margen) que maximiza la accuracy
    estricta sobre `items` (la suite). Desempate: mayor F1 macro y, si persiste,
    los umbrales más chicos (menos abstención).
    """
    puntajes = [puntajes_tfidf(it, df_terminos, analizador) for it in items]
    esperados = [it["esperado"] for it in items]
    mejor = None
    for u_null in _candidatos([p[1] for p in puntajes]):
        for u_margen in _candidatos([p[2] for p in puntajes]):
            umbrales = {"umbral_null": u_null, "umbral_margen": u_margen}
            pred = [aplicar_umbrales(*p, umbrales) for p in puntajes]
            m = metricas_estrictas(esperados, pred)
            clave = (m["accuracy"], m["macro_f1"], -u_null, -u_margen)
            if mejor is None or clave > mejor[0]:
                mejor = (clave, umbrales, m)
    _, umbrales, m = mejor
    return {**umbrales, "accuracy_calibracion": m["accuracy"], "macro_f1_calibracion": m["macro_f1"],
            "n_calibracion": len(items)}


# ─── Recuperación ────────────────────────────────────────────────────────────

def recuperacion(item: dict, df_terminos, analizador: str, k: int) -> dict:
    """Términos recuperados: top-1 y top-k crudos, y el contexto que recibe el LLM (top-k filtrado)."""
    crudos = [df_terminos.iloc[i]["preferred_term"]
              for i in buscar_relevantes(item["input"], df_terminos, k, analizador)]
    contexto = _RE_TERMINO.findall(buscar_terminos_relevantes(item["input"], df_terminos, k, analizador))
    return {"top1": crudos[:1], "topk": crudos, "contexto": contexto}


def hit(item: dict, terminos: list[str]) -> bool | str:
    """'' si el caso no espera un término (AMBIGUO / null); si no, si el término esperado está."""
    return item["esperado"] in terminos if es_termino(item["esperado"]) else ""


def recall(filas: list[dict], clave: str) -> float | None:
    validas = [f[clave] for f in filas if f[clave] != ""]
    return sum(validas) / len(validas) if validas else None


def calcular_recuperacion(datos: dict, df_terminos, k: int, catalogo: str) -> dict:
    recup = {}
    for s, items in datos.items():
        for analizador in ("palabras", "char"):
            filas = []
            for item in items:
                r = recuperacion(item, df_terminos, analizador, k)
                filas.append({"top1": hit(item, r["top1"]), "topk": hit(item, r["topk"]),
                              "contexto": hit(item, r["contexto"])})
            recup[(catalogo, s, analizador)] = {
                "recall@1": recall(filas, "top1"),
                f"recall@{k} crudo": recall(filas, "topk"),
                f"recall@{k} contexto": recall(filas, "contexto"),
                "por_caso": filas,
            }
    return recup


# ─── Corrida ─────────────────────────────────────────────────────────────────

def _fila(s: str, clave: str, nombre: str, item: dict, pred: str, k_recup, hit_recup,
          latencia: float, error: str) -> dict:
    return {
        "set": s, "config": clave, "config_nombre": nombre,
        "id": item["id"], "grupo": item["grupo"], "input": item["input"],
        "esperado": item["esperado"], "prediccion": pred,
        "correcto_estricto": pred == item["esperado"],
        "gold_laxo": gold_laxo(item) or "",
        "correcto_laxo": correcto_laxo(item, pred) if gold_laxo(item) else "",
        "revisar": item["revisar"],
        "k_recuperacion": k_recup, "hit_recuperacion": hit_recup,
        "latencia_s": round(latencia, 4), "error": error,
        "_item": item,
    }


def correr(configs: dict, datos: dict, k: int, df_terminos, df_coberturas, recup: dict,
           catalogo: str) -> tuple[list[dict], dict | None]:
    umbrales = None
    if "b2" in configs:
        umbrales = calibrar_umbrales(SETS["suite"](), df_terminos, CONFIGS["b2"]["analizador"])

    filas = []
    for clave, cfg in configs.items():
        for s, items in datos.items():
            for i, item in enumerate(items):
                print(f"  {clave}) {cfg['nombre'][:34]:<34} {s:<8} [{i + 1}/{len(items)}]", end="\r", flush=True)
                t0 = time.perf_counter()
                error = ""
                try:
                    if cfg["llm"]:
                        pred = predecir_llm(item, df_terminos, df_coberturas, cfg, k, CATALOGOS[catalogo])
                    elif cfg.get("umbrales"):
                        pred = aplicar_umbrales(*puntajes_tfidf(item, df_terminos, cfg["analizador"]), umbrales)
                    else:
                        pred = predecir_tfidf(item, df_terminos, cfg["analizador"])
                except Exception as e:  # el caso cuenta como null
                    pred, error = CLASE_NULL, f"{type(e).__name__}: {e}"
                latencia = time.perf_counter() - t0

                if cfg["analizador"] is None:
                    k_recup, hit_recup = "", ""
                elif cfg["llm"]:
                    k_recup, hit_recup = k, recup[(catalogo, s, cfg["analizador"])]["por_caso"][i]["contexto"]
                else:
                    k_recup, hit_recup = 1, recup[(catalogo, s, cfg["analizador"])]["por_caso"][i]["top1"]
                filas.append(_fila(s, clave, cfg["nombre"], item, pred, k_recup, hit_recup, latencia, error))
        print(" " * 90, end="\r")
    return filas, umbrales


def cargar_filas_previas(ruta: str, datos: dict, reemplazar: set) -> list[dict]:
    """
    Predicciones guardadas, salvo los pares (config, set) en `reemplazar`.
    Las métricas se recalculan con las etiquetas actuales.
    """
    if not os.path.exists(ruta):
        return []
    items = {(s, it["id"]): it for s, its in datos.items() for it in its}
    filas = []
    with open(ruta, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (r["config"], r["set"]) in reemplazar or r["set"] not in datos:
                continue
            item = items.get((r["set"], r["id"]))
            if item is None or item["input"] != r["input"]:
                raise SystemExit(f"--reusar: el caso {r['set']}/{r['id']} cambió o no existe; volvé a correr {r['config']}")
            hit_r = {"True": True, "False": False}.get(r["hit_recuperacion"], "")
            if hit_r != "" and not es_termino(item["esperado"]):
                hit_r = ""
            k_r = int(r["k_recuperacion"]) if r["k_recuperacion"] else ""
            filas.append(_fila(r["set"], r["config"], r["config_nombre"], item, r["prediccion"], k_r, hit_r,
                               float(r["latencia_s"]), r["error"]))
    return filas


def resumir(filas: list[dict], configs: list[str], sets: list[str]) -> list[dict]:
    resumen = []
    for clave in configs:
        for s in sets:
            fs = [f for f in filas if f["config"] == clave and f["set"] == s]
            if not fs:
                continue
            esperados = [f["esperado"] for f in fs]
            predichos = [f["prediccion"] for f in fs]
            m = metricas_estrictas(esperados, predichos)
            ml = metricas_laxas([f["_item"] for f in fs], predichos)
            por_tipo = f1_ambiguo_por_tipo([f["_item"] for f in fs], predichos)
            latencias = [f["latencia_s"] for f in fs]
            ids_few = CONFIGS[base_config(clave)].get("few_shot", ())
            fuera_few = [f for f in fs if f["id"] not in ids_few]
            resumen.append({
                "config": clave, "config_nombre": fs[0]["config_nombre"], "set": s, "n": m["n"],
                "n_clases": m["n_clases"],
                "k_recuperacion": fs[0]["k_recuperacion"],
                "recall_recuperacion": recall(fs, "hit_recuperacion"),
                "accuracy": m["accuracy"],
                "macro_p": m["macro_p"], "macro_r": m["macro_r"], "macro_f1": m["macro_f1"],
                "f1_ambiguo": m["ambiguo"][2], "f1_null": m["null"][2],
                **{f"f1_ambiguo_{t}": por_tipo[t]["f1"] for t in TIPOS_AMBIGUEDAD},
                **{f"n_ambiguo_{t}": por_tipo[t]["n"] for t in TIPOS_AMBIGUEDAD},
                "laxa_p": ml["p"], "laxa_r": ml["r"], "laxa_f1": ml["f1"],
                "latencia_media_s": statistics.mean(latencias),
                "latencia_mediana_s": statistics.median(latencias),
                "errores": sum(1 for f in fs if f["error"]),
                "errores_parseo": sum(1 for f in fs if tipo_error(f["error"]) == "parseo"),
                "accuracy_sin_few_shot": (sum(f["correcto_estricto"] for f in fuera_few) / len(fuera_few)
                                          if s == "suite" and ids_few else None),
            })
    return resumen


# ─── Salidas ─────────────────────────────────────────────────────────────────

def _f(v, dec=2) -> str:
    return "—" if v is None or v == "" else f"{v:.{dec}f}"


def _lat(s: float) -> str:
    return f"{s * 1000:.0f} ms" if s < 1 else f"{s:.2f} s"


def tabla_markdown(resumen: list[dict], recup: dict, sets: list[str], k: int, umbrales: dict | None) -> str:
    por = {(r["config"], r["set"]): r for r in resumen}
    configs = list(dict.fromkeys(r["config"] for r in resumen))
    nombres = {r["config"]: r["config_nombre"] for r in resumen}

    lineas = ["# Comparación de configuraciones — estudio", ""]
    n_por_set = {r["set"]: (r["n"], r["n_clases"]) for r in resumen}
    lineas.append("Casos por set: " + ", ".join(
        f"{s} = {n_por_set[s][0]} ({n_por_set[s][1]} clases)" for s in sets if s in n_por_set) + ". "
        "Todas las configuraciones se evalúan sobre los mismos casos.")

    lineas += ["", "## Resumen", "",
               "| Config | Acc. suite | Acc. held-out | F1 AMBIGUO (s / h) | F1 null (s / h) "
               "| Errores parseo (s / h) | Latencia mediana (s / h) |",
               "|---|---|---|---|---|---|---|"]
    for c in configs:
        su, he = por.get((c, "suite")), por.get((c, "heldout"))
        def par(campo, fmt=_f):
            return " / ".join(fmt(x[campo]) if x else "—" for x in (su, he))
        lineas.append(f"| {c}) {nombres[c]} | {_f(su['accuracy']) if su else '—'} | {_f(he['accuracy']) if he else '—'} "
                      f"| {par('f1_ambiguo')} | {par('f1_null')} | {par('errores_parseo', str)} "
                      f"| {par('latencia_mediana_s', _lat)} |")

    lineas += ["", "## Métricas por configuración", "",
               "| Config | Set | recall@k recup. | Accuracy | P macro | R macro | F1 macro | F1 AMBIGUO | F1 null "
               "| F1 laxa | Latencia media | Errores |",
               "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in resumen:
        rk = f"{_f(r['recall_recuperacion'])} (k={r['k_recuperacion']})" if r["k_recuperacion"] != "" else "—"
        lineas.append(f"| {r['config']}) {r['config_nombre']} | {r['set']} | {rk} | {_f(r['accuracy'])} "
                      f"| {_f(r['macro_p'])} | {_f(r['macro_r'])} | {_f(r['macro_f1'])} | {_f(r['f1_ambiguo'])} "
                      f"| {_f(r['f1_null'])} | {_f(r['laxa_f1'])} | {_lat(r['latencia_media_s'])} | {r['errores']} |")

    lineas += ["", "## F1 de AMBIGUO por tipo_ambiguedad", "",
               "AMBIGUO vs resto, sin los AMBIGUO de los otros tipos (n = casos AMBIGUO del tipo). "
               "La predicción no trae tipo: los falsos positivos de AMBIGUO cuentan en todos los tipos.", "",
               "| Config | Set | F1 AMBIGUO | " + " | ".join(TIPOS_AMBIGUEDAD) + " |",
               "|---|---|---|" + "---|" * len(TIPOS_AMBIGUEDAD)]
    for r in resumen:
        lineas.append(f"| {r['config']}) {r['config_nombre']} | {r['set']} | {_f(r['f1_ambiguo'])} | "
                      + " | ".join(f"{_f(r[f'f1_ambiguo_{t}'])} (n={r[f'n_ambiguo_{t}']})" for t in TIPOS_AMBIGUEDAD)
                      + " |")

    if "suite" in sets and "heldout" in sets:
        lineas += ["", "## Caída suite → heldout (heldout − suite)", "",
                   "| Config | Δ Accuracy | Δ F1 macro | Δ F1 laxa |", "|---|---|---|---|"]
        for c in configs:
            if (c, "suite") in por and (c, "heldout") in por:
                su, he = por[(c, "suite")], por[(c, "heldout")]
                lineas.append(f"| {c}) {nombres[c]} | {he['accuracy'] - su['accuracy']:+.2f} "
                              f"| {he['macro_f1'] - su['macro_f1']:+.2f} | {he['laxa_f1'] - su['laxa_f1']:+.2f} |")

    few = [c for c in configs if CONFIGS[base_config(c)].get("few_shot")]
    if few:
        lineas += ["", "## Few-shot", "",
                   "Los ejemplos salen de la suite, así que en la suite esos casos están vistos. "
                   "Accuracy en la suite sin esos casos:", ""]
        for c in few:
            if (c, "suite") in por:
                ids = CONFIGS[base_config(c)]["few_shot"]
                lineas.append(f"- {c}) {nombres[c]} — ejemplos: {', '.join(ids)} → "
                              f"{_f(por[(c, 'suite')]['accuracy_sin_few_shot'])} "
                              f"(con ellos: {_f(por[(c, 'suite')]['accuracy'])})")

    if umbrales:
        lineas += ["", "## Calibración de b2 (solo sobre la suite)", "",
                   f"- umbral_null = {umbrales['umbral_null']:.4f} (coseno top-1 por debajo → null)",
                   f"- umbral_margen = {umbrales['umbral_margen']:.4f} (margen top1−top2 por debajo → AMBIGUO)",
                   "- Orden: primero null, después AMBIGUO, si no top-1.",
                   f"- Grilla: puntos medios entre los valores observados en la suite ({umbrales['n_calibracion']} casos), "
                   "más 0 y un valor sobre el máximo. Criterio: máxima accuracy estricta; desempate por F1 macro "
                   "y por umbrales más chicos.",
                   f"- Accuracy en la suite con estos umbrales: {umbrales['accuracy_calibracion']:.2f} "
                   "(dentro de la muestra de calibración: es optimista). La cifra válida es la del held-out."]
        if ("b2", "heldout") in por:
            lineas.append(f"- **Accuracy estricta en held-out: {por[('b2', 'heldout')]['accuracy']:.2f}**")

    lineas += ["", "## Recuperación TF-IDF (solo casos que esperan un término exacto)", "",
               f"| Catálogo | Analizador | Set | recall@1 | recall@{k} crudo | recall@{k} contexto LLM |",
               "|---|---|---|---|---|---|"]
    for (cat, s, analizador), r in recup.items():
        lineas.append(f"| {cat} | {analizador} | {s} | {_f(r['recall@1'])} | {_f(r[f'recall@{k} crudo'])} "
                      f"| {_f(r[f'recall@{k} contexto'])} |")

    lineas += ["", "## Definiciones", "",
               "- **Accuracy**: predicción == preferred_term esperado (texto exacto). AMBIGUO y null son clases.",
               "- **P/R/F1 macro**: promedio sobre las clases del gold más AMBIGUO y null, que se incluyen "
               "siempre aunque no se predigan (una clase sin aciertos aporta 0). Cada clase pesa igual, sin "
               "importar cuántos casos tenga.",
               "- **F1 laxa**: métrica anterior (checks de los tests en la suite; `clave_laxa` en el heldout).",
               f"- **recall@k recup.**: el término esperado está entre los candidatos (k=1 para TF-IDF top-1; "
               f"k={k} sobre el contexto que recibe el LLM, después del filtro de calificadores de rag.py).",
               "- **Errores de parseo**: la salida del LLM no se pudo leer como JSON; el caso cuenta como null.",
               "- Clase predicha por el LLM: AMBIGUO si `estudio_ambiguo` es true o `estudio` es \"AMBIGUO\"; "
               "si no, el estudio o null.",
               "- Los baselines a) y b) siempre devuelven un término: nunca predicen AMBIGUO ni null.",
               "- **Latencia**: tiempo por mensaje (recuperación + LLM cuando corresponde)."]
    return "\n".join(lineas) + "\n"


def escribir_csv(ruta: str, filas: list[dict]) -> None:
    columnas = [c for c in filas[0] if not c.startswith("_")]
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columnas, extrasaction="ignore")
        w.writeheader()
        w.writerows(filas)


ORDEN = ["a", "b", "b2", "c", "d", "e", "f", "g", "i"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Comparación de configuraciones sobre los sets etiquetados.")
    parser.add_argument("--configs", nargs="+", default=ORDEN, choices=ORDEN)
    parser.add_argument("--sets", nargs="+", default=list(SETS), choices=list(SETS))
    parser.add_argument("--k", type=int, default=5, help="candidatos de la recuperación para el LLM (default 5)")
    parser.add_argument("--catalogo", choices=list(CATALOGOS), default="v1",
                        help="catálogo SNOMED (default v1); las corridas con v2 se guardan como <config>@v2")
    parser.add_argument("--reusar", action="store_true",
                        help="conservar de comparacion_por_caso.csv las predicciones de los pares config/set que no se corren")
    args = parser.parse_args()

    df_terminos = cargar_terminos(CATALOGOS[args.catalogo])
    df_coberturas = cargar_coberturas(CSV_COBERTURAS)
    todos = {s: SETS[s]() for s in SETS}
    datos = {s: todos[s] for s in args.sets}
    d = asegurar_dir_resultados()
    sufijo = "" if args.catalogo == "v1" else f"@{args.catalogo}"
    configs = {f"{c}{sufijo}": ({**CONFIGS[c], "nombre": f"{CONFIGS[c]['nombre']} [{args.catalogo}]"} if sufijo
                                else CONFIGS[c]) for c in args.configs}

    recup = {}
    for cat, ruta in CATALOGOS.items():
        if os.path.exists(ruta):
            recup.update(calcular_recuperacion(todos, cargar_terminos(ruta), args.k, cat))
    reemplazar = {(c, s) for c in configs for s in args.sets}
    previas = cargar_filas_previas(os.path.join(d, CSV_POR_CASO), todos, reemplazar) if args.reusar else []
    nuevas, umbrales = correr(configs, datos, args.k, df_terminos, df_coberturas, recup, args.catalogo)
    filas = previas + nuevas

    presentes = {f["config"] for f in filas}
    orden_cfg = sorted(presentes, key=lambda c: (ORDEN.index(base_config(c)), catalogo_de(c)))
    orden_set = [s for s in SETS if any(f["set"] == s for f in filas)]
    filas.sort(key=lambda f: (orden_cfg.index(f["config"]), orden_set.index(f["set"])))
    if umbrales is None and "b2" in orden_cfg:  # b2 reusado: reportar igual sus umbrales (catálogo v1)
        umbrales = calibrar_umbrales(todos["suite"], cargar_terminos(CATALOGOS["v1"]), CONFIGS["b2"]["analizador"])

    resumen = resumir(filas, orden_cfg, orden_set)
    markdown = tabla_markdown(resumen, recup, orden_set, args.k, umbrales)
    print(markdown)

    escribir_csv(os.path.join(d, CSV_POR_CASO), filas)
    escribir_csv(os.path.join(d, "comparacion_resumen.csv"), resumen)
    with open(os.path.join(d, "comparacion_resumen.md"), "w", encoding="utf-8") as f:
        f.write(markdown)
    print(f"  Resultados en {os.path.relpath(d)}/: {CSV_POR_CASO}, comparacion_resumen.csv, "
          f"comparacion_resumen.md\n")


if __name__ == "__main__":
    main()
