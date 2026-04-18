"""
Chat interactivo por terminal
==============================
Simula una conversación con el chatbot sin necesidad de WhatsApp.
Requiere que el servidor esté corriendo: uvicorn main:app --reload

Uso:
    python chat.py
    python chat.py --phone +5491199999999   # simular otro usuario

Métricas registradas:
    - Tiempo total de sesión
    - Tiempo por turno (cuánto tardó el usuario en responder cada mensaje del bot)
    - Resumen final en pantalla + exportación a JSON
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

API_URL = "http://127.0.0.1:8000/api/v1/webhook"


# ---------------------------------------------------------------------------
# Medición de tiempos
# ---------------------------------------------------------------------------

class SessionTimer:
    def __init__(self, phone: str):
        self.phone = phone
        self.session_start: float = time.perf_counter()
        self.session_start_ts: str = datetime.now().isoformat(timespec="seconds")
        self.turns: list[dict] = []
        self._turn_start: float | None = None
        self._turn_bot_msg: str = ""

    def bot_spoke(self, msg: str):
        """Llamar justo después de que el bot responde — arranca el cronómetro del turno."""
        self._turn_start = time.perf_counter()
        self._turn_bot_msg = msg

    def user_spoke(self, user_msg: str):
        """Llamar justo antes de enviar el mensaje del usuario — registra el turno."""
        if self._turn_start is None:
            return
        elapsed = time.perf_counter() - self._turn_start
        self.turns.append({
            "turn": len(self.turns) + 1,
            "bot_prompt": self._turn_bot_msg[:80] + ("…" if len(self._turn_bot_msg) > 80 else ""),
            "user_reply": user_msg,
            "response_time_s": round(elapsed, 2),
        })
        self._turn_start = None

    def total_seconds(self) -> float:
        return round(time.perf_counter() - self.session_start, 1)

    def summary(self) -> dict:
        times = [t["response_time_s"] for t in self.turns]
        return {
            "phone": self.phone,
            "session_start": self.session_start_ts,
            "total_seconds": self.total_seconds(),
            "total_turns": len(self.turns),
            "avg_response_time_s": round(sum(times) / len(times), 2) if times else 0,
            "turns": self.turns,
        }

    def print_summary(self):
        s = self.summary()
        print("\n" + "═" * 55)
        print("  ⏱   Resumen de la Sesión")
        print("═" * 55)
        print(f"  Sesión iniciada:    {s['session_start']}")
        print(f"  Tiempo total:       {s['total_seconds']} s")
        print("═" * 55)

    def save_json(self, path: Path):
        path.write_text(
            json.dumps(self.summary(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\n  💾  Métricas guardadas en: {path}")


# ---------------------------------------------------------------------------
# Comunicación con el servidor
# ---------------------------------------------------------------------------

def send_message(phone: str, text: str) -> str:
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": phone,
                        "type": "text",
                        "text": {"body": text}
                    }]
                }
            }]
        }]
    }
    response = httpx.post(API_URL, json=payload, timeout=10)
    response.raise_for_status()
    return response.json().get("reply", "(sin respuesta)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Chat de prueba para el chatbot de turnos.")
    parser.add_argument("--phone", default="5491100000000", help="Número de teléfono simulado")
    parser.add_argument("--output", default=None, help="Archivo JSON donde guardar métricas (opcional)")
    args = parser.parse_args()

    print("\n" + "═" * 55)
    print("  🏥  Chatbot de Turnos Médicos — Terminal Chat")
    print("═" * 55)
    print(f"  Simulando usuario: {args.phone}")
    print("  Escribí 'salir' para terminar.")
    print("  Escribí 'estado' para ver los slots actuales.")
    print("═" * 55 + "\n")

    timer = SessionTimer(args.phone)

    # Mensaje de bienvenida automático
    try:
        reply = send_message(args.phone, "hola")
        print(f"🤖 Bot: {reply}\n")
        timer.bot_spoke(reply)
    except httpx.ConnectError:
        print("❌ No se pudo conectar al servidor.")
        print("   Asegurate de que uvicorn esté corriendo en otra terminal.")
        print("   Comando: uvicorn main:app --reload\n")
        sys.exit(1)

    while True:
        try:
            user_input = input("👤 Vos: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 ¡Hasta luego!")
            break

        if not user_input:
            continue

        if user_input.lower() == "salir":
            print("👋 ¡Hasta luego!")
            break

        if user_input.lower() == "estado":
            try:
                r = httpx.get(f"http://127.0.0.1:8000/api/v1/webhook/session/{args.phone}")
                data = r.json()
                print("\n📋 Estado actual de la sesión:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
                print()
            except Exception as e:
                print(f"❌ Error: {e}\n")
            continue

        # Registrar tiempo de respuesta del usuario antes de enviar
        timer.user_spoke(user_input)

        try:
            reply = send_message(args.phone, user_input)
            print(f"\n🤖 Bot: {reply}\n")
            timer.bot_spoke(reply)
        except httpx.HTTPStatusError as e:
            print(f"❌ Error HTTP {e.response.status_code}: {e.response.text}\n")
        except Exception as e:
            print(f"❌ Error inesperado: {e}\n")

    # Mostrar resumen al finalizar
    timer.print_summary()

    # Guardar JSON con métricas
    output_path = Path(args.output) if args.output else Path(f"sesion_{args.phone}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    timer.save_json(output_path)


if __name__ == "__main__":
    main()