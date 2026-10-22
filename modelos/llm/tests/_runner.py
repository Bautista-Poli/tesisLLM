"""
_runner.py — Infraestructura compartida para todos los tests NLU.
No correr directamente; importar desde los módulos de tests.
"""
import os
import json

MODEL          = "qwen2.5:7b"
CSV_TERMINOS   = "CSVs/snomed_con_variantes.csv"
CSV_COBERTURAS = "CSVs/coberturas_medicas.csv"

from modelos.llm.rag import TOP_K, cargar_terminos, cargar_coberturas, buscar_terminos_relevantes, buscar_coberturas_relevantes
from modelos.llm.estudios import normalizar_estudio
from modelos.llm.validators import validar_dni
from modelos.llm.prompt import construir_system_prompt
from modelos.llm.ollama_client import llamar_ollama, extraer_json

# ─── COLORES ──────────────────────────────────────────────────────────────────
DEBUG_NLU = os.getenv("DEBUG_NLU", "0") == "1"

def debug(*args, **kwargs):
    if DEBUG_NLU:
        print(*args, **kwargs)

VERDE    = "\033[92m"
ROJO     = "\033[91m"
AMARILLO = "\033[93m"
RESET    = "\033[0m"

def ok(msg):   print(f"  {VERDE}✅ PASS{RESET} {msg}")
def fail(msg): print(f"  {ROJO}❌ FAIL{RESET} {msg}")

# ─── INFRAESTRUCTURA ──────────────────────────────────────────────────────────

def extraer(texto, ultima_pregunta="", slots_llenos=None, df_terminos=None, df_coberturas=None,
            top_k=TOP_K):
    slots_llenos = slots_llenos or []
    ctx_est = buscar_terminos_relevantes(texto, df_terminos, top_k)
    ctx_cob = buscar_coberturas_relevantes(texto, df_coberturas) if df_coberturas is not None else ""

    debug("\n" + "─" * 60)
    debug(f"  QUERY:          {texto!r}")
    debug(f"  ÚLTIMA PREGUNTA:{ultima_pregunta!r}")
    debug(f"  SLOTS LLENOS:   {slots_llenos}")
    debug(f"  CONTEXTO ESTUDIOS:\n{ctx_est}")
    debug("─" * 60)

    prompt = construir_system_prompt(ctx_est, ctx_cob, ultima_pregunta, slots_llenos)
    msgs   = [{"role": "system", "content": prompt}, {"role": "user", "content": texto}]
    raw    = llamar_ollama(msgs)

    debug(f"  RAW LLM: {raw}")
    debug("─" * 60 + "\n")

    slots = extraer_json(raw)
    slots["dni"] = validar_dni(slots.get("dni"))

    if slots.get("estudio") and not slots.get("estudio_ambiguo"):
        slots["estudio"] = normalizar_estudio(slots["estudio"], df_terminos)

    return slots

def correr_check(campo, esperado, slots):
    valor = slots.get(campo)
    passed = esperado(valor) if callable(esperado) else valor == esperado
    return passed, valor

# ─── RUNNER ───────────────────────────────────────────────────────────────────

def correr_tests(tests, titulo="NLU EXTRACCIÓN", filtro=None):
    print("\n" + "=" * 65)
    print(f"  TEST SUITE — {titulo}")
    print("=" * 65)

    df_terminos   = cargar_terminos(CSV_TERMINOS)
    df_coberturas = cargar_coberturas(CSV_COBERTURAS)

    tests_a_correr = [t for t in tests if filtro is None or
                      t["grupo"] == filtro or t["id"] == filtro]

    if not tests_a_correr:
        print(f"  No se encontraron tests con filtro '{filtro}'")
        return

    grupos_vistos = set()
    total = passed_count = 0
    slot_stats = {}  # slot -> {"tp": 0, "fp": 0, "fn": 0}

    for test in tests_a_correr:
        grupo = test["grupo"]
        if grupo not in grupos_vistos:
            print(f"\n── {grupo.upper()} ──────────────────────────────────────")
            grupos_vistos.add(grupo)

        print(f"\n  [{test['id']}] {test['descripcion']}")
        print(f"  Input: \"{test['input']}\"")

        try:
            slots = extraer(
                test["input"],
                ultima_pregunta=test.get("ultima_pregunta", ""),
                slots_llenos=test.get("slots_llenos", []),
                df_terminos=df_terminos,
                df_coberturas=df_coberturas,
            )
            debug = {k: v for k, v in slots.items()
                     if v and k not in ("estudio_ambiguo", "pregunta_aclaracion")}
            if slots.get("estudio_ambiguo"):
                debug["estudio_ambiguo"] = True
            print(f"  Extraído: {json.dumps(debug, ensure_ascii=False)}")

            for campo, esperado, descripcion in test["checks"]:
                passed_check, valor = correr_check(campo, esperado, slots)
                total += 1

                # Acumular stats para F1 (solo slots de datos, no flags)
                if campo in ("nombre_completo", "dni", "estudio", "obra_social", "sede",
                             "dias_disponibles", "horario"):
                    if campo not in slot_stats:
                        slot_stats[campo] = {"tp": 0, "fp": 0, "fn": 0}
                    if passed_check:
                        if esperado is not None:
                            slot_stats[campo]["tp"] += 1
                    else:
                        if valor is not None:
                            slot_stats[campo]["fp"] += 1
                        else:
                            slot_stats[campo]["fn"] += 1

                if passed_check:
                    passed_count += 1
                    ok(f"{campo}: {descripcion}")
                else:
                    fail(f"{campo}: {descripcion} (obtenido: {repr(valor)})")

        except Exception as e:
            total += 1
            fail(f"ERROR al procesar: {e}")

    # ── Resumen general ───────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    color = VERDE if passed_count == total else ROJO
    print(f"  {color}Resultado: {passed_count}/{total} checks pasaron{RESET}")

    # ── F1 por slot ───────────────────────────────────────────────────────────
    if slot_stats:
        print(f"\n  {'Slot':<20} {'Precision':>10} {'Recall':>10} {'F1':>10}")
        print(f"  {'-'*20} {'-'*10} {'-'*10} {'-'*10}")
        for slot, s in sorted(slot_stats.items()):
            tp, fp, fn = s["tp"], s["fp"], s["fn"]
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
            bar = VERDE if f1 >= 0.8 else (AMARILLO if f1 >= 0.6 else ROJO)
            print(f"  {slot:<20} {precision:>10.2f} {recall:>10.2f} {bar}{f1:>10.2f}{RESET}")

    print("=" * 65 + "\n")
