"""
playground_llm.py — Mock de conversación con slot filling usando Ollama + RAG
Correr con: python -m modelos.llm.playground_llm
Requiere: pip install -r modelos/llm/requirements.txt y Ollama corriendo
"""

import json
import time

from modelos.llm.extractor import ExtractorLLM
from modelos.llm.estudios import obtener_preparacion
from modelos.llm.ollama_client import MODEL
from modelos.llm.slots import SLOTS_VACIOS, SLOTS_OBLIGATORIOS, slots_faltantes, fusionar_slots
from modelos.llm.prompt import generar_pregunta_agrupada, formatear_resumen


# ─── LOOP PRINCIPAL ───────────────────────────────────────────────────────────

def correr_mock():
    print("=" * 60)
    print("  MOCK DE CHATBOT DE TURNOS — RADIOLOGÍA")
    print("  Modelo:", MODEL)
    print("  Escribí 'salir' para terminar")
    print("=" * 60)

    try:
        extractor = ExtractorLLM()
    except FileNotFoundError as e:
        print(f"  ERROR: No se encontró '{e.filename}'. Corré desde la raíz del proyecto.")
        return

    print(f"  CSV estudios:       {len(extractor.df_terminos)} entradas")
    if extractor.df_coberturas is None:
        print("  [AVISO: Coberturas no disponibles.]")
    else:
        print(f"  CSV coberturas:     {len(extractor.df_coberturas)} entradas")
    preparaciones = extractor.preparaciones
    print(f"  CSV preparaciones:  {len(preparaciones)} estudios configurados\n")

    slots = SLOTS_VACIOS.copy()
    slots["_turno_chequeado"] = False

    historial_ollama             = []
    ultima_pregunta              = ""
    esperando_aclaracion_estudio = False

    # Acumuladores de tiempos para resumen final
    tiempos_llm   = []
    tiempos_total = []
    turno_num     = 0

    print("Bot: ¡Hola! Soy el asistente de turnos médicos. "
          "Contame qué estudio necesitás y cómo te llamás para empezar.\n")

    while True:
        try:
            texto_usuario = input("Vos: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBot: ¡Hasta luego!")
            break

        if texto_usuario.lower() in ("salir", "exit", "quit"):
            print("Bot: ¡Hasta luego!")
            break
        if not texto_usuario:
            continue

        turno_num += 1
        t_inicio_total = time.perf_counter()

        llenos = [k for k in SLOTS_OBLIGATORIOS if slots.get(k)]

        # 1-2. RAG + extracción con LLM
        print("  [extrayendo entidades...]")
        t0 = time.perf_counter()
        try:
            ext = extractor.extraer(texto_usuario, llenos, ultima_pregunta, historial_ollama)
        except Exception as e:
            t_err = time.perf_counter() - t0
            print(f"  [ERROR ({t_err:.2f}s): {e}]")
            print("Bot: No pude entender eso. ¿Podés repetirlo?\n")
            continue

        tiempos_llm.append(ext.t_llm)
        print(f"  [⏱ LLM: {ext.t_llm:.2f}s  |  RAG: {ext.t_rag*1000:.0f}ms]")

        nuevos_slots = ext.slots
        if ext.dni_descartado:
            print(f"  [⚠ DNI descartado: '{ext.dni_descartado}' no es válido]")
        if ext.estudio_original:
            print(f"  [Estudio normalizado: '{ext.estudio_original}' → '{nuevos_slots['estudio']}']")

        estudio_ya_lleno   = bool(slots.get("estudio"))
        estudio_es_ambiguo = nuevos_slots.get("estudio_ambiguo", False) and not estudio_ya_lleno

        debug = {k: v for k, v in nuevos_slots.items()
                 if v and k not in ("estudio_ambiguo", "pregunta_aclaracion")}
        flag  = " | ⚠ AMBIGUO" if estudio_es_ambiguo else ""
        print(f"  [Extraídos: {json.dumps(debug, ensure_ascii=False)}{flag}]")

        # 3. Estudio ambiguo → pedir aclaración
        if estudio_es_ambiguo and not esperando_aclaracion_estudio:
            nuevos_sin_estudio = {k: v for k, v in nuevos_slots.items()
                                  if k not in ("estudio", "pregunta_aclaracion")}
            slots = fusionar_slots(slots, nuevos_sin_estudio)
            print(f"  [Slots: {json.dumps({k:v for k,v in slots.items() if v and not k.startswith('_')}, ensure_ascii=False)}]")
            esperando_aclaracion_estudio = True
            pregunta = nuevos_slots.get("pregunta_aclaracion") or (
                "¿De qué parte del cuerpo necesitás la radiografía? "
                "(por ejemplo: tórax, rodilla, columna lumbar, mano, tobillo...)"
            )
            ultima_pregunta = pregunta

            t_total = time.perf_counter() - t_inicio_total
            tiempos_total.append(t_total)
            print(f"  [⏱ Total turno #{turno_num}: {t_total:.2f}s]")
            print(f"\nBot: {pregunta}\n")
            continue

        # 4. Fusión normal
        slots = fusionar_slots(slots, nuevos_slots)
        esperando_aclaracion_estudio = False
        print(f"  [Slots: {json.dumps({k:v for k,v in slots.items() if v and not k.startswith('_')}, ensure_ascii=False)}]")

        # 5. Check inmediato: ¿el estudio requiere turno?
        estudio_actual = slots.get("estudio")
        if estudio_actual and not slots["_turno_chequeado"]:
            slots["_turno_chequeado"] = True
            info = obtener_preparacion(estudio_actual, preparaciones)
            if info and not info["requiere_turno"]:
                tiempo     = info.get("tiempo_min")
                tiempo_str = f" El estudio dura aproximadamente {tiempo} minutos." if tiempo else ""

                t_total = time.perf_counter() - t_inicio_total
                tiempos_total.append(t_total)
                print(f"  [⏱ Total turno #{turno_num}: {t_total:.2f}s]")

                print(f"\nBot: ✅ Buenas noticias — *{estudio_actual}* no requiere "
                      f"turno previo. Podés presentarte directamente en cualquier sede "
                      f"de lunes a viernes de 8 a 20hs.{tiempo_str}")
                print(f"\nBot: 📋 Preparación: {info['preparacion']}\n")
                _imprimir_resumen_tiempos(tiempos_llm, tiempos_total)
                print("Bot: ¡Hasta luego!\n")
                break

        # Tiempo total del turno
        t_total = time.perf_counter() - t_inicio_total
        tiempos_total.append(t_total)
        print(f"  [⏱ Total turno #{turno_num}: {t_total:.2f}s]")

        # 6. Pedir slots faltantes o confirmar turno
        faltantes = slots_faltantes(slots)

        if not faltantes:
            info = obtener_preparacion(slots.get("estudio"), preparaciones) if slots.get("estudio") else None
            if info:
                print(f"\nBot: 📋 Preparación necesaria:")
                print(f"  {info['preparacion']}")
                if info.get("tiempo_min"):
                    print(f"  Duración estimada: {info['tiempo_min']} minutos.")

            print(f"\nBot: Revisá los datos antes de confirmar:\n{formatear_resumen(slots)}")
            print("\nBot: ¿Confirmás el turno? (SI / NO)\n")

            confirmacion = input("Vos: ").strip().lower()
            if confirmacion in ("si", "sí", "s", "confirmo", "yes"):
                _imprimir_resumen_tiempos(tiempos_llm, tiempos_total)
                print("\nBot: 🎉 ¡Turno registrado! Te vamos a contactar "
                      "para asignarte el horario exacto. ¡Hasta luego!\n")
            else:
                _imprimir_resumen_tiempos(tiempos_llm, tiempos_total)
                print("\nBot: Entendido, cancelamos. Escribime cuando quieras.\n")
            break
        else:
            ultima_pregunta = generar_pregunta_agrupada(faltantes)
            print(f"\nBot: {ultima_pregunta}\n")


def _imprimir_resumen_tiempos(tiempos_llm: list, tiempos_total: list):
    if not tiempos_llm:
        return
    print("\n" + "─" * 50)
    print("  RESUMEN DE TIEMPOS")
    print("─" * 50)
    print(f"  Turnos procesados:      {len(tiempos_llm)}")
    print(f"  LLM  — promedio:        {sum(tiempos_llm)/len(tiempos_llm):.2f}s")
    print(f"  LLM  — mín/máx:         {min(tiempos_llm):.2f}s / {max(tiempos_llm):.2f}s")
    print(f"  Total — promedio:       {sum(tiempos_total)/len(tiempos_total):.2f}s")
    print(f"  Total — mín/máx:        {min(tiempos_total):.2f}s / {max(tiempos_total):.2f}s")
    overhead = [(t - l) for t, l in zip(tiempos_total, tiempos_llm)]
    print(f"  Overhead Python/RAG:    {sum(overhead)/len(overhead)*1000:.0f}ms promedio")
    print("─" * 50 + "\n")


if __name__ == "__main__":
    correr_mock()
