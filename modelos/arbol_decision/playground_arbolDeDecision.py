"""
Chatbot Clásico — Flujo Lineal por Menús
==========================================
Simula el sistema tradicional de atención por WhatsApp con menús numerados.
Usado para comparar tiempos de tarea contra el chatbot conversacional con NLU.

Flujo completo:
  Paso 1 → DNI
  Paso 2 → Confirmación de datos
  Paso 3 → Tipo de cobertura (obra social / particular)
  Paso 4 → Menú principal (Turnos / Estudios / Laboratorios / Sedes / Vacunatorios)
  Paso 5 → Submenú Estudios → Más opciones → Radiología (hoja informativa)

Uso:
    python -m modelos.arbol_decision.playground_arbolDeDecision
"""

import time
import sys

# ---------------------------------------------------------------------------
# Helpers de UI
# ---------------------------------------------------------------------------

def header():
    print("\n" + "═" * 52)
    print("  🏥  Centro Médico — Atención por WhatsApp")
    print("═" * 52)


def bot(msg: str, delay: float = 0.6):
    """Imprime un mensaje del bot con un pequeño delay para simular latencia."""
    time.sleep(delay)
    print(f"\n🤖  {msg}")


def opciones(lista: list[str]):
    """Muestra un menú numerado."""
    for i, item in enumerate(lista, 1):
        print(f"   {i}. {item}")


def input_usuario(prompt: str = "") -> str:
    try:
        val = input(f"\n👤  {prompt}").strip()
        return val
    except (KeyboardInterrupt, EOFError):
        print("\n\n👋  Sesión finalizada.")
        sys.exit(0)


def pedir_opcion(opciones_lista: list[str]) -> int:
    """Pide una opción numerada y valida que sea válida."""
    while True:
        raw = input_usuario("Tu opción: ")
        try:
            n = int(raw)
            if 1 <= n <= len(opciones_lista):
                return n
        except ValueError:
            pass
        bot(
            "Disculpá, no logro comprender 😔. "
            "Probá escribir las *palabras clave* de tu consulta.\n"
            "   O también podés elegir una de las *opciones del menú*.",
            delay=0.3,
        )
        opciones(opciones_lista)


# ---------------------------------------------------------------------------
# Mensajes de hoja (nodos terminales del árbol)
# ---------------------------------------------------------------------------

INFO_RADIOLOGIA = (
    "Las radiografías generales son sin turno previo\n"
    "   (incluye espinograma, escanograma y panorámica dental).\n\n"
    "   Se realizan en las siguientes sedes:\n"
    "   Abasto, Arenales, Belgrano, Esmeralda y San Isidro.\n"
    "   Lunes a Viernes de 07 a 20hs | Sábados de 08 a 13hs.\n\n"
    "   Tené en cuenta que para los demás estudios odontológicos\n"
    "   y radiologías contrastadas se requiere turno previo.\n\n"
    "   ⏳ Por favor aguardá un momento.\n"
    "   Pronto un agente se va a contactar con vos."
)

INFO_TURNO_CONFIRMADO = (
    "✅ *Tu turno fue registrado correctamente.*\n\n"
    "   Te enviaremos una confirmación en breve.\n"
    "   ⏳ Aguardá que un agente se contacte con vos."
)

INFO_NO_IMPLEMENTADO = (
    "Esta opción no está disponible en este momento.\n"
    "   ⏳ Aguardá que un agente se contacte con vos."
)


# ---------------------------------------------------------------------------
# Submenús
# ---------------------------------------------------------------------------

def flujo_mas_opciones() -> bool:
    """
    Submenú 'Más opciones' dentro de Estudios.
    Retorna True si la conversación terminó, False si el usuario eligió volver.
    """
    while True:
        bot("Seleccioná la opción deseada:")
        opts = [
            "Odontología",
            "Radiología",
            "Consultorios Externos",
            "Densitometría",
            "🔙 Volver a Estudios",
        ]
        opciones(opts)
        n = pedir_opcion(opts)

        if n == 1:
            bot(INFO_NO_IMPLEMENTADO)
            return True
        elif n == 2:
            bot(INFO_RADIOLOGIA)
            return True
        elif n == 3:
            bot(INFO_NO_IMPLEMENTADO)
            return True
        elif n == 4:
            bot(INFO_NO_IMPLEMENTADO)
            return True
        elif n == 5:
            return False  # volver a estudios


def flujo_estudios() -> bool:
    """
    Menú de Estudios.
    Retorna True si la conversación terminó, False para volver al menú principal.
    """
    while True:
        bot("*Paso 5*\nSeleccioná el estudio deseado:")
        opts = [
            "Tomografía",
            "Resonancia",
            "PET CT",
            "Ecografía / Ecodoppler",
            "Mamografía / Punciones",
            "Neumología",
            "Estudio Cardiológico",
            "➕ Más opciones",
            "🏠 Menú principal",
        ]
        opciones(opts)
        n = pedir_opcion(opts)

        if 1 <= n <= 7:
            bot(INFO_TURNO_CONFIRMADO)
            return True
        elif n == 8:
            finalizo = flujo_mas_opciones()
            if finalizo:
                return True
            # si no finalizó, vuelve al menú de estudios
        elif n == 9:
            return False  # volver al menú principal


def flujo_menu_principal(datos: dict) -> None:
    """Menú principal post-autenticación."""
    while True:
        bot(
            f"*Paso 4*\n"
            f"Hola {datos['nombre']} 👋\n"
            "   ¿En qué te puedo ayudar hoy?"
        )
        opts = [
            "📅 Turnos",
            "🔬 Estudios",
            "🧪 Laboratorios",
            "📍 Sedes",
            "💉 Vacunatorios",
        ]
        opciones(opts)
        n = pedir_opcion(opts)

        if n == 1:
            bot(INFO_TURNO_CONFIRMADO)
            break
        elif n == 2:
            finalizo = flujo_estudios()
            if finalizo:
                break
            # si volvió, continúa el while (re-muestra el menú principal)
        elif n in (3, 4, 5):
            bot(INFO_NO_IMPLEMENTADO)
            break


# ---------------------------------------------------------------------------
# Flujo principal
# ---------------------------------------------------------------------------

def main():
    header()

    # ── Paso 1 — DNI ─────────────────────────────────────────────────────
    bot(
        "¡Hola! Bienvenido/a al Centro Médico. 👋\n\n"
        "   *Paso 1*\n"
        "   Por favor, ingresá el número de DNI del paciente."
    )

    while True:
        dni_raw = input_usuario("DNI: ")
        digitos = "".join(c for c in dni_raw if c.isdigit())
        if 7 <= len(digitos) <= 8:
            break
        bot(
            "Disculpá, no logro comprender 😔.\n"
            "   Por favor ingresá un DNI válido (7 u 8 dígitos).",
            delay=0.3,
        )

    bot("🔍 Estamos verificando tus datos...", delay=1.2)

    # ── Paso 2 — Confirmación de datos ───────────────────────────────────
    datos = {
        "nombre": "Juan Pérez",
        "dni": digitos,
        "fecha_nac": "15/03/1990",
    }

    bot(
        f"*Paso 2*\n"
        f"   ¿Tus datos son los siguientes?\n\n"
        f"   👤 Nombre:       {datos['nombre']}\n"
        f"   🪪  DNI:          {datos['dni']}\n"
        f"   📅 Fecha de nac.: {datos['fecha_nac']}"
    )
    opts_confirm = ["✅ Sí, son mis datos", "❌ No, no son mis datos"]
    opciones(opts_confirm)
    if pedir_opcion(opts_confirm) == 2:
        bot(
            "Entendido. Por favor acercate a la recepción más cercana\n"
            "   para actualizar tus datos. ¡Hasta pronto! 👋"
        )
        return

    # ── Paso 3 — Tipo de cobertura ────────────────────────────────────────
    bot("*Paso 3*\nPor favor, seleccioná la opción deseada:")
    opts_cob = [
        "🏥 Prepaga u Obra Social",
        "💳 Consulta Privada (particular)",
    ]
    opciones(opts_cob)
    cob_n = pedir_opcion(opts_cob)
    datos["cobertura"] = "Obra Social / Prepaga" if cob_n == 1 else "Particular"

    if cob_n == 1:
        bot("Por favor, ingresá el nombre de tu obra social o prepaga.")
        nombre_os = input_usuario("Obra social: ")
        datos["obra_social"] = nombre_os if nombre_os else "No especificada"

    # ── Paso 4 en adelante — Menú principal ──────────────────────────────
    flujo_menu_principal(datos)

    # ── Cierre ────────────────────────────────────────────────────────────
    bot(
        "Gracias por contactarnos. 🙏\n"
        "   ¡Que te mejores pronto! 👋",
        delay=0.8,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    inicio = time.time()
    main()
    duracion = time.time() - inicio
    print(f"\n⏱  Tiempo total de sesión: {duracion:.1f} segundos")
    print("─" * 52)
