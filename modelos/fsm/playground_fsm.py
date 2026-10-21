"""
playground_fsm.py — Playground interactivo del ConversationManager.

Permite probar el flujo de slot filling no lineal inyectando entidades
manualmente, sin necesidad del stack NLU (Ollama, RAG, etc.).

Correr con:  python -m modelos.fsm.playground_fsm

Cómo ingresar entidades
-----------------------
  Texto libre:                    hola, buenos días
  Entidades como JSON inline:     {"dni": "30456789", "estudio": "Rx Tórax"}
  Entidades + texto separados:    mi dni es 30456789 | {"dni": "30456789"}
  Sin entidades (solo texto):     ok, confirmo

Comandos especiales
-------------------
  reiniciar   → Resetea la sesión
  estado      → Muestra el estado interno actual
  salir       → Sale del playground
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from modelos.fsm.manager import ConversationManager
from modelos.fsm.states import ConversationState

VERDE    = "\033[92m"
AMARILLO = "\033[93m"
GRIS     = "\033[90m"
RESET    = "\033[0m"

PHONE = "playground_user"


def parsear_entidades(texto: str) -> tuple[str, dict]:
    """
    Separa el texto del usuario de las entidades JSON inline.

    Si el input contiene '|', la parte derecha se parsea como JSON.
    Si el input completo es JSON válido, se usa como entidades con texto vacío.
    En cualquier otro caso, devuelve texto=input y entidades={}.
    """
    if "|" in texto:
        partes = texto.split("|", 1)
        texto_limpio = partes[0].strip()
        try:
            entidades = json.loads(partes[1].strip())
            return texto_limpio, entidades
        except json.JSONDecodeError:
            return texto_limpio, {}

    try:
        entidades = json.loads(texto.strip())
        if isinstance(entidades, dict):
            return "", entidades
    except (json.JSONDecodeError, ValueError):
        pass

    return texto.strip(), {}


def correr_playground():
    print("\n" + "=" * 62)
    print("  PLAYGROUND — CONVERSATION MANAGER")
    print("  Slot Filling No Lineal | Sin NLU")
    print("=" * 62)
    print(f"{GRIS}  Ingresá entidades como JSON: {{\"dni\": \"30456789\"}}")
    print(f"  O combiná texto y entidades con '|': texto | {{\"dni\": \"30456789\"}}")
    print(f"  Comandos: reiniciar · estado · salir{RESET}\n")

    manager = ConversationManager()

    respuesta_inicial = manager.process_turn(PHONE, "hola", {})
    print(f"Bot: {respuesta_inicial}\n")

    while True:
        try:
            raw = input("Vos: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBot: ¡Hasta luego!")
            break

        if not raw:
            continue

        if raw.lower() == "salir":
            print("Bot: ¡Hasta luego!")
            break

        if raw.lower() == "estado":
            estado = manager.get_session_state(PHONE)
            print(f"{GRIS}  {json.dumps(estado, ensure_ascii=False, indent=2)}{RESET}\n")
            continue

        texto, entidades = parsear_entidades(raw)

        if entidades:
            print(f"{GRIS}  [Entidades: {json.dumps(entidades, ensure_ascii=False)}]{RESET}")

        respuesta = manager.process_turn(PHONE, texto or raw, entidades)
        print(f"\nBot: {respuesta}\n")

        estado = manager.get_session_state(PHONE)
        if estado:
            slots_rellenos = {k: v for k, v in estado["slots"].items() if v}
            color = VERDE if estado["state"] in ("completed", "cancelled") else AMARILLO
            print(f"{GRIS}  Estado: {color}{estado['state']}{GRIS} | Slots: {slots_rellenos}{RESET}\n")

        if estado and estado["state"] in ("completed", "cancelled"):
            print(f"{GRIS}  Sesión finalizada. Escribí 'reiniciar' o 'salir'.{RESET}\n")


if __name__ == "__main__":
    correr_playground()
