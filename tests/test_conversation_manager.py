"""
test_conversation_manager.py — Tests unitarios del ConversationManager.

No requieren Ollama ni ningún modelo externo; prueban exclusivamente
la lógica de estados y slot filling.

Correr todos:  python -m tests.test_conversation_manager
Correr grupo:  python -m tests.test_conversation_manager flujo
Correr test:   python -m tests.test_conversation_manager todo_en_un_turno
"""

import sys

from dialog_mock.manager import ConversationManager
from dialog_mock.states import ConversationState

VERDE    = "\033[92m"
ROJO     = "\033[91m"
AMARILLO = "\033[93m"
RESET    = "\033[0m"

def ok(msg):   print(f"  {VERDE}✅ PASS{RESET} {msg}")
def fail(msg): print(f"  {ROJO}❌ FAIL{RESET} {msg}")


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def nueva_sesion() -> tuple[ConversationManager, str]:
    """Devuelve un manager fresco y un phone único por test."""
    import uuid
    return ConversationManager(), str(uuid.uuid4())


def estado(manager: ConversationManager, phone: str) -> str:
    return manager.get_session_state(phone)["state"]

def slots(manager: ConversationManager, phone: str) -> dict:
    return manager.get_session_state(phone)["slots"]


# ─── TESTS ───────────────────────────────────────────────────────────────────

TESTS = [

    # ── FLUJO COMPLETO ────────────────────────────────────────────────────────
    {
        "id": "flujo_completo_un_slot_por_turno", "grupo": "flujo",
        "descripcion": "Slots de a uno en orden de prioridad → confirmar al final",
        "fn": lambda: _flujo_completo_un_slot_por_turno(),
    },
    {
        "id": "todo_en_un_turno", "grupo": "flujo",
        "descripcion": "Todos los slots en el primer mensaje → ir directo a confirming",
        "fn": lambda: _todo_en_un_turno(),
    },
    {
        "id": "orden_invertido", "grupo": "flujo",
        "descripcion": "Slots en orden invertido → se recolectan igual",
        "fn": lambda: _orden_invertido(),
    },
    {
        "id": "confirmacion_exitosa", "grupo": "flujo",
        "descripcion": "Confirmar con 'si' → estado COMPLETED",
        "fn": lambda: _confirmacion_exitosa(),
    },
    {
        "id": "confirmacion_con_variantes", "grupo": "flujo",
        "descripcion": "Variantes de 'si' (dale, ok, sí) → COMPLETED",
        "fn": lambda: _confirmacion_con_variantes(),
    },

    # ── CANCELACIÓN ───────────────────────────────────────────────────────────
    {
        "id": "cancelacion_en_confirming", "grupo": "cancelacion",
        "descripcion": "Cancelar en estado CONFIRMING → estado CANCELLED",
        "fn": lambda: _cancelacion_en_confirming(),
    },
    {
        "id": "cancelacion_con_no", "grupo": "cancelacion",
        "descripcion": "'no' en confirming → estado CANCELLED",
        "fn": lambda: _cancelacion_con_no(),
    },
    {
        "id": "post_completado_bloquea", "grupo": "cancelacion",
        "descripcion": "Mensaje después de COMPLETED → respuesta de bloqueo",
        "fn": lambda: _post_completado_bloquea(),
    },

    # ── REINICIO ──────────────────────────────────────────────────────────────
    {
        "id": "reiniciar_limpia_slots", "grupo": "reinicio",
        "descripcion": "Reiniciar a mitad del flujo → sesión limpia",
        "fn": lambda: _reiniciar_limpia_slots(),
    },
    {
        "id": "reiniciar_desde_confirming", "grupo": "reinicio",
        "descripcion": "Reiniciar desde CONFIRMING → volver a GREETING",
        "fn": lambda: _reiniciar_desde_confirming(),
    },

    # ── SLOTS ─────────────────────────────────────────────────────────────────
    {
        "id": "slot_no_se_sobreescribe", "grupo": "slots",
        "descripcion": "Slot ya lleno no se sobreescribe con None",
        "fn": lambda: _slot_no_se_sobreescribe(),
    },
    {
        "id": "slots_faltantes_en_orden", "grupo": "slots",
        "descripcion": "Missing slots respetan SLOT_PRIORITY",
        "fn": lambda: _slots_faltantes_en_orden(),
    },
    {
        "id": "entidades_desconocidas_ignoradas", "grupo": "slots",
        "descripcion": "Entidades fuera de SLOT_PRIORITY se ignoran silenciosamente",
        "fn": lambda: _entidades_desconocidas_ignoradas(),
    },

    # ── RESPUESTAS ────────────────────────────────────────────────────────────
    {
        "id": "pregunta_slot_unico_faltante", "grupo": "respuestas",
        "descripcion": "Solo falta un slot → pregunta específica del slot",
        "fn": lambda: _pregunta_slot_unico_faltante(),
    },
    {
        "id": "respuesta_ambigua_en_confirming", "grupo": "respuestas",
        "descripcion": "Texto ambiguo en CONFIRMING → pide SI o NO explícito",
        "fn": lambda: _respuesta_ambigua_en_confirming(),
    },
    {
        "id": "greeting_incluye_slots_pedidos", "grupo": "respuestas",
        "descripcion": "Mensaje de saludo menciona los 4 slots necesarios",
        "fn": lambda: _greeting_incluye_slots_pedidos(),
    },
]


# ─── IMPLEMENTACIONES DE TESTS ────────────────────────────────────────────────

def _flujo_completo_un_slot_por_turno():
    m, p = nueva_sesion()
    m.process_turn(p, "hola", {})
    assert estado(m, p) == ConversationState.COLLECTING.value

    m.process_turn(p, "mi dni", {"dni": "30456789"})
    assert slots(m, p)["dni"] == "30456789"
    assert estado(m, p) == ConversationState.COLLECTING.value

    m.process_turn(p, "rx torax", {"estudio": "Rx Tórax"})
    assert slots(m, p)["estudio"] == "Rx Tórax"

    m.process_turn(p, "osde", {"obra_social": "OSDE"})
    assert slots(m, p)["obra_social"] == "OSDE"

    m.process_turn(p, "sede norte", {"sede": "Norte"})
    assert estado(m, p) == ConversationState.CONFIRMING.value
    assert slots(m, p)["sede"] == "Norte"


def _todo_en_un_turno():
    m, p = nueva_sesion()
    m.process_turn(p, "hola", {
        "dni": "30456789",
        "estudio": "Rx Tórax",
        "obra_social": "OSDE",
        "sede": "Centro",
    })
    assert estado(m, p) == ConversationState.CONFIRMING.value
    s = slots(m, p)
    assert s["dni"] == "30456789"
    assert s["estudio"] == "Rx Tórax"


def _orden_invertido():
    m, p = nueva_sesion()
    m.process_turn(p, "hola", {})
    m.process_turn(p, "sede sur", {"sede": "Sur"})
    m.process_turn(p, "ioma", {"obra_social": "IOMA"})
    m.process_turn(p, "rodilla derecha", {"estudio": "Rx Rodilla Derecha"})
    m.process_turn(p, "mi dni 27654321", {"dni": "27654321"})
    assert estado(m, p) == ConversationState.CONFIRMING.value


def _confirmacion_exitosa():
    m, p = nueva_sesion()
    m.process_turn(p, "hola", {
        "dni": "30456789", "estudio": "Rx Tórax",
        "obra_social": "OSDE", "sede": "Centro",
    })
    assert estado(m, p) == ConversationState.CONFIRMING.value
    m.process_turn(p, "si", {})
    assert estado(m, p) == ConversationState.COMPLETED.value


def _confirmacion_con_variantes():
    for confirmacion in ("dale", "ok", "sí", "confirmar", "yes"):
        m, p = nueva_sesion()
        m.process_turn(p, "hola", {
            "dni": "30456789", "estudio": "Rx Tórax",
            "obra_social": "OSDE", "sede": "Centro",
        })
        m.process_turn(p, confirmacion, {})
        assert estado(m, p) == ConversationState.COMPLETED.value, \
            f"Fallo con confirmación '{confirmacion}'"


def _cancelacion_en_confirming():
    m, p = nueva_sesion()
    m.process_turn(p, "hola", {
        "dni": "30456789", "estudio": "Rx Tórax",
        "obra_social": "OSDE", "sede": "Centro",
    })
    m.process_turn(p, "cancelar", {})
    assert estado(m, p) == ConversationState.CANCELLED.value


def _cancelacion_con_no():
    m, p = nueva_sesion()
    m.process_turn(p, "hola", {
        "dni": "30456789", "estudio": "Rx Tórax",
        "obra_social": "OSDE", "sede": "Centro",
    })
    m.process_turn(p, "no", {})
    assert estado(m, p) == ConversationState.CANCELLED.value


def _post_completado_bloquea():
    m, p = nueva_sesion()
    m.process_turn(p, "hola", {
        "dni": "30456789", "estudio": "Rx Tórax",
        "obra_social": "OSDE", "sede": "Centro",
    })
    m.process_turn(p, "si", {})
    resp = m.process_turn(p, "quiero otro turno", {})
    assert "reiniciar" in resp.lower(), "Debe sugerir reiniciar"
    assert estado(m, p) == ConversationState.COMPLETED.value


def _reiniciar_limpia_slots():
    m, p = nueva_sesion()
    m.process_turn(p, "hola", {"dni": "30456789", "estudio": "Rx Tórax"})
    m.process_turn(p, "reiniciar", {})
    assert m.get_session_state(p) is None or \
           estado(m, p) == ConversationState.GREETING.value


def _reiniciar_desde_confirming():
    m, p = nueva_sesion()
    m.process_turn(p, "hola", {
        "dni": "30456789", "estudio": "Rx Tórax",
        "obra_social": "OSDE", "sede": "Centro",
    })
    assert estado(m, p) == ConversationState.CONFIRMING.value
    m.process_turn(p, "reiniciar", {})
    # Después de reiniciar no existe la sesión previa
    s = m.get_session_state(p)
    assert s is None or s["state"] == ConversationState.GREETING.value


def _slot_no_se_sobreescribe():
    m, p = nueva_sesion()
    m.process_turn(p, "hola", {"dni": "30456789"})
    assert slots(m, p)["dni"] == "30456789"
    m.process_turn(p, "otro mensaje", {"dni": None})
    assert slots(m, p)["dni"] == "30456789", "El slot no debe borrarse con None"


def _slots_faltantes_en_orden():
    from dialog_mock.slots import SLOT_PRIORITY, SlotSet
    s = SlotSet()
    s.estudio = "Rx Tórax"
    faltantes = s.missing_slots()
    assert faltantes[0] == "dni", "El primero en faltar debe ser 'dni' (mayor prioridad)"
    assert "estudio" not in faltantes, "El estudio ya está lleno, no debe estar en faltantes"


def _entidades_desconocidas_ignoradas():
    m, p = nueva_sesion()
    m.process_turn(p, "hola", {"campo_inventado": "valor", "otro_campo": "123"})
    s = slots(m, p)
    assert all(v is None for v in s.values()), "Entidades desconocidas no deben llenar slots"


def _pregunta_slot_unico_faltante():
    from dialog_mock.slots import SLOT_QUESTIONS
    m, p = nueva_sesion()
    m.process_turn(p, "hola", {
        "dni": "30456789",
        "estudio": "Rx Tórax",
        "obra_social": "OSDE",
    })
    resp = m.process_turn(p, "otro mensaje", {})
    assert SLOT_QUESTIONS["sede"] in resp or "sede" in resp.lower(), \
        "Debe preguntar por la sede"


def _respuesta_ambigua_en_confirming():
    m, p = nueva_sesion()
    m.process_turn(p, "hola", {
        "dni": "30456789", "estudio": "Rx Tórax",
        "obra_social": "OSDE", "sede": "Centro",
    })
    resp = m.process_turn(p, "mmm no sé", {})
    assert "SI" in resp or "NO" in resp, \
        "Debe pedir SI o NO explícito ante respuesta ambigua"
    assert estado(m, p) == ConversationState.CONFIRMING.value


def _greeting_incluye_slots_pedidos():
    m, p = nueva_sesion()
    resp = m.process_turn(p, "hola", {})
    resp_lower = resp.lower()
    for slot in ("dni", "estudio", "obra social", "sede"):
        assert slot in resp_lower, f"El saludo debe mencionar '{slot}'"


# ─── RUNNER ───────────────────────────────────────────────────────────────────

def correr_tests(filtro=None):
    print("\n" + "=" * 62)
    print("  TEST SUITE — CONVERSATION MANAGER")
    print("=" * 62)

    tests_a_correr = [t for t in TESTS if filtro is None or
                      t["grupo"] == filtro or t["id"] == filtro]

    if not tests_a_correr:
        print(f"  No se encontraron tests con filtro '{filtro}'")
        return

    grupos_vistos = set()
    total = passed_count = 0

    for test in tests_a_correr:
        grupo = test["grupo"]
        if grupo not in grupos_vistos:
            print(f"\n── {grupo.upper()} ──────────────────────────────────────")
            grupos_vistos.add(grupo)

        print(f"\n  [{test['id']}] {test['descripcion']}")
        total += 1
        try:
            test["fn"]()
            passed_count += 1
            ok("pasó")
        except AssertionError as e:
            fail(f"AssertionError: {e}")
        except Exception as e:
            fail(f"ERROR inesperado: {e}")

    print("\n" + "=" * 62)
    color = VERDE if passed_count == total else ROJO
    print(f"  {color}Resultado: {passed_count}/{total} tests pasaron{RESET}")
    print("=" * 62 + "\n")


if __name__ == "__main__":
    filtro = sys.argv[1] if len(sys.argv) > 1 else None
    correr_tests(filtro)
