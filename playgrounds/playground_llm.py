"""
playground_llm.py — Mock de conversación con slot filling usando Ollama + RAG
Correr con: python -m playgrounds.playground_llm
Requiere: pip install requests scikit-learn pandas
"""

import json
import time

MODEL           = "qwen2.5:7b"
CSV_TERMINOS    = "CSVs/snomed_con_variantes.csv"
CSV_PREPARACION = "CSVs/preparaciones_radiologia.csv"
CSV_COBERTURAS  = "CSVs/coberturas_medicas.csv"

from nlu_mock.validators import validar_dni
from nlu_mock.rag import (
    cargar_terminos, cargar_coberturas, cargar_preparaciones,
    buscar_terminos_relevantes, buscar_coberturas_relevantes,
)
from nlu_mock.estudios import normalizar_estudio, obtener_preparacion
from nlu_mock.slots import SLOTS_VACIOS, SLOTS_OBLIGATORIOS, slots_faltantes, fusionar_slots
from nlu_mock.prompt import construir_system_prompt, generar_pregunta_agrupada, formatear_resumen
from nlu_mock.ollama_client import llamar_ollama, extraer_json


# ─── LOOP PRINCIPAL ───────────────────────────────────────────────────────────

def correr_mock():
    print("=" * 60)
    print("  MOCK DE CHATBOT DE TURNOS — RADIOLOGÍA")
    print("  Modelo:", MODEL)
    print("  Escribí 'salir' para terminar")
    print("=" * 60)

    try:
        df_terminos = cargar_terminos(CSV_TERMINOS)
        print(f"  CSV estudios:       {len(df_terminos)} entradas")
    except FileNotFoundError:
        print(f"  ERROR: No se encontró '{CSV_TERMINOS}'. Corré desde Tesis/Codigo/")
        return

    try:
        df_coberturas = cargar_coberturas(CSV_COBERTURAS)
        print(f"  CSV coberturas:     {len(df_coberturas)} entradas")
    except FileNotFoundError:
        print(f"  [AVISO: No se encontró '{CSV_COBERTURAS}'. Coberturas no disponibles.]")
        df_coberturas = None

    preparaciones = cargar_preparaciones(CSV_PREPARACION)
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

        # 1. RAG
        t0 = time.perf_counter()
        contexto_estudios   = buscar_terminos_relevantes(texto_usuario, df_terminos)
        contexto_coberturas = (
            buscar_coberturas_relevantes(texto_usuario, df_coberturas)
            if df_coberturas is not None else "No disponible."
        )
        t_rag = time.perf_counter() - t0

        system_prompt = construir_system_prompt(
            contexto_estudios, contexto_coberturas, ultima_pregunta, llenos
        )

        # Limitar historial a últimos 6 mensajes (3 turnos) para no crecer indefinidamente
        historia_recortada = historial_ollama[-6:]
        mensajes = [{"role": "system", "content": system_prompt}] + historia_recortada
        mensajes.append({"role": "user", "content": texto_usuario})

        # 2. Extracción NLU — medir tiempo del LLM
        print("  [extrayendo entidades...]")
        t0 = time.perf_counter()
        try:
            respuesta_raw = llamar_ollama(mensajes)
            nuevos_slots  = extraer_json(respuesta_raw)
            t_llm = time.perf_counter() - t0
            tiempos_llm.append(t_llm)
            print(f"  [⏱ LLM: {t_llm:.2f}s  |  RAG: {t_rag*1000:.0f}ms]")
        except Exception as e:
            t_llm = time.perf_counter() - t0
            print(f"  [ERROR ({t_llm:.2f}s): {e}]")
            print("Bot: No pude entender eso. ¿Podés repetirlo?\n")
            continue

        # Fix DNI
        dni_raw    = nuevos_slots.get("dni")
        dni_valido = validar_dni(dni_raw)
        if dni_raw and not dni_valido:
            print(f"  [⚠ DNI descartado: '{dni_raw}' no es válido]")
        nuevos_slots["dni"] = dni_valido

        # Fix Estudio
        if nuevos_slots.get("estudio") and not nuevos_slots.get("estudio_ambiguo"):
            original    = nuevos_slots["estudio"]
            normalizado = normalizar_estudio(original, df_terminos)
            if normalizado != original:
                print(f"  [Estudio normalizado: '{original}' → '{normalizado}']")
            nuevos_slots["estudio"] = normalizado

        estudio_ya_lleno   = bool(slots.get("estudio"))
        estudio_es_ambiguo = nuevos_slots.get("estudio_ambiguo", False) and not estudio_ya_lleno

        debug = {k: v for k, v in nuevos_slots.items()
                 if v and k not in ("estudio_ambiguo", "pregunta_aclaracion")}
        flag  = " | ⚠ AMBIGUO" if estudio_es_ambiguo else ""
        print(f"  [Extraídos: {json.dumps(debug, ensure_ascii=False)}{flag}]")

        historial_ollama.append({"role": "user",      "content": texto_usuario})
        historial_ollama.append({"role": "assistant",  "content": respuesta_raw})

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