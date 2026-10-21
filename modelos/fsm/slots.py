from __future__ import annotations

from typing import Any, Dict, List, Optional


# Orden de prioridad para recolectar slots faltantes
SLOT_PRIORITY: List[str] = ["dni", "estudio", "obra_social", "sede"]

# Preguntas de fallback cuando falta un único slot
SLOT_QUESTIONS: Dict[str, str] = {
    "dni": (
        "Para comenzar, ¿me podés indicar tu número de DNI? 📋"
    ),
    "estudio": (
        "¿Qué estudio o especialidad médica necesitás? "
        "(Ej: Cardiología, Radiografía, Análisis de sangre)"
    ),
    "obra_social": (
        "¿Con qué obra social o prepaga contás? "
        "Si no tenés, podés responder 'particular'. 🏥"
    ),
    "sede": (
        "¿En qué sede preferís atenderte? "
        "Nuestras sedes disponibles son: Centro, Norte, Sur. 📍"
    ),
}

CONFIRMATION_TEMPLATE = """
✅ *Revisá los datos de tu turno:*

👤 *DNI:* {dni}
🔬 *Estudio:* {estudio}
🏥 *Obra social:* {obra_social}
📍 *Sede:* {sede}

¿Confirmás el turno? Respondé *SI* para confirmar o *NO* para cancelar.
""".strip()


class SlotSet:
    """Contenedor de los slots del turno médico."""

    __slots__ = ("dni", "estudio", "sede", "obra_social")

    def __init__(self) -> None:
        self.dni:         Optional[str] = None
        self.estudio:     Optional[str] = None
        self.sede:        Optional[str] = None
        self.obra_social: Optional[str] = None

    def is_complete(self) -> bool:
        return all(getattr(self, s) for s in SLOT_PRIORITY)

    def missing_slots(self) -> List[str]:
        return [s for s in SLOT_PRIORITY if not getattr(self, s)]

    def to_dict(self) -> Dict[str, Any]:
        return {s: getattr(self, s) for s in SLOT_PRIORITY}
