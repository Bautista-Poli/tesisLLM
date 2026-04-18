"""
ConversationManager - Versión Tesis Ingeniería
==============================================
Núcleo del sistema de diálogo con Slot Filling No Lineal y 
estrategia de recolección proactiva de datos.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Estados y Configuración
# ---------------------------------------------------------------------------

class ConversationState(str, Enum):
    GREETING        = "greeting"
    COLLECTING      = "collecting"
    CONFIRMING      = "confirming"
    COMPLETED       = "completed"
    CANCELLED       = "cancelled"

# Prioridad de recolección
SLOT_PRIORITY: List[str] = ["dni", "estudio", "obra_social", "sede"]

# Preguntas específicas (Fallback cuando falta solo uno)
SLOT_QUESTIONS: Dict[str, str] = {
    "dni": "Me falta tu *DNI* para identificarte. ¿Me lo podrías indicar? 📋",
    "estudio": "¿Qué *estudio* médico necesitás realizarte? 🔬",
    "obra_social": "¿Con qué *obra social o prepaga* contás? (Si no tenés, escribí 'Particular') 🏥",
    "sede": "¿En qué *sede* preferís el turno? (Centro, Norte o Sur) 📍",
}

CONFIRMATION_TEMPLATE = """
✅ *Revisá los datos de tu turno:*

👤 *DNI:* {dni}
🔬 *Estudio:* {estudio}
🏥 *Obra social:* {obra_social}
📍 *Sede:* {sede}

¿Confirmás el turno? Respondé *SI* para confirmar o *NO* para cancelar.
""".strip()

# ---------------------------------------------------------------------------
# Estructuras de Datos (Dataclasses)
# ---------------------------------------------------------------------------

@dataclass
class SlotSet:
    dni:         Optional[str] = None
    estudio:     Optional[str] = None
    sede:        Optional[str] = None
    obra_social: Optional[str] = None

    def is_complete(self) -> bool:
        return all([self.dni, self.estudio, self.sede, self.obra_social])

    def missing_slots(self) -> List[str]:
        return [s for s in SLOT_PRIORITY if getattr(self, s) is None]

    def to_dict(self) -> Dict[str, Any]:
        return {k: v if v else "Pendiente" for k, v in self.__dict__.items()}

@dataclass
class ConversationSession:
    phone_number:  str
    state:         ConversationState = ConversationState.GREETING
    slots:         SlotSet           = field(default_factory=SlotSet)
    created_at:    datetime          = field(default_factory=datetime.utcnow)
    updated_at:    datetime          = field(default_factory=datetime.utcnow)
    turn_count:    int               = 0
    history:       List[Dict]        = field(default_factory=list)

    def add_to_history(self, role: str, text: str) -> None:
        self.history.append({"role": role, "text": text, "ts": datetime.utcnow().isoformat()})
        if len(self.history) > 20: self.history = self.history[-20:]

    def touch(self) -> None:
        self.updated_at = datetime.utcnow()
        self.turn_count += 1

# ---------------------------------------------------------------------------
# Gestor de Conversación
# ---------------------------------------------------------------------------

class ConversationManager:
    def __init__(self) -> None:
        self._sessions: Dict[str, ConversationSession] = {}

    def _get_session(self, phone: str) -> ConversationSession:
        if phone not in self._sessions:
            self._sessions[phone] = ConversationSession(phone_number=phone)
        return self._sessions[phone]

    def reset_session(self, phone: str) -> None:
        if phone in self._sessions:
            del self._sessions[phone]

    def process_turn(self, phone: str, user_text: str, entities: Dict[str, str]) -> str:
        session = self._get_session(phone)
        session.add_to_history("user", user_text)
        session.touch()

        normalized = user_text.strip().lower()

        # Comandos globales
        if normalized in ("reiniciar", "reset", "empezar de nuevo"):
            self.reset_session(phone)
            return self._greeting_message()

        # Lógica de estados
        if session.state == ConversationState.GREETING:
            # Si el usuario ya mandó datos en el saludo, los procesamos directo
            session.state = ConversationState.COLLECTING
            return self._handle_collecting(session, entities)

        if session.state == ConversationState.COLLECTING:
            return self._handle_collecting(session, entities)

        if session.state == ConversationState.CONFIRMING:
            return self._handle_confirming(session, normalized)

        return "Tu turno ya fue procesado. Escribí *reiniciar* para uno nuevo."

    def _handle_collecting(self, session: ConversationSession, entities: Dict[str, str]) -> str:
        # Fusionar datos nuevos (permite corregir datos ya existentes)
        self._merge_entities(session, entities)

        if session.slots.is_complete():
            session.state = ConversationState.CONFIRMING
            return CONFIRMATION_TEMPLATE.format(**session.slots.to_dict())

        missing = session.slots.missing_slots()
        
        # Caso 1: No tenemos nada todavía
        if len(missing) == len(SLOT_PRIORITY):
            return self._greeting_message()

        # Caso 2: Falta más de un dato (Respuesta proactiva)
        if len(missing) > 1:
            p1 = missing[0].replace('_', ' ')
            p2 = missing[1].replace('_', ' ')
            return f"¡Perfecto! Ya tomé esos datos. Para continuar necesito tu *{p1}* y tu *{p2}*."

        # Caso 3: Falta solo un dato (Pregunta específica)
        return SLOT_QUESTIONS[missing[0]]

    def _handle_confirming(self, session: ConversationSession, text: str) -> str:
        if text in ("si", "sí", "confirmar", "ok", "dale", "yes"):
            session.state = ConversationState.COMPLETED
            return (
                "🎉 *¡Turno confirmado exitosamente!*\n\n"
                f"Te esperamos en la sede *{session.slots.sede}*.\n"
                "Recibirás un recordatorio 24hs antes. ¡Hasta pronto! 👋"
            )
        if text in ("no", "cancelar", "cancelo"):
            session.state = ConversationState.CANCELLED
            return "Entendido, cancelamos el proceso. Si cambiás de opinión, escribí *reiniciar*. 🙏"
        
        return "Por favor, respondé *SI* para confirmar o *NO* para cancelar el turno."

    def _merge_entities(self, session: ConversationSession, entities: Dict[str, str]) -> None:
        """Fusiona y permite actualizar slots."""
        for slot_name, value in entities.items():
            if value and slot_name in SLOT_PRIORITY:
                setattr(session.slots, slot_name, value)
                logger.debug(f"Slot {slot_name} actualizado a {value}")

    @staticmethod
    def _greeting_message() -> str:
        return (
            "👋 ¡Hola! Soy tu asistente de turnos médicos.\n\n"
            "Para agendarte rápido, por favor indicame:\n"
            "• Tu *DNI*\n"
            "• El *estudio* que buscás\n"
            "• Tu *obra social*\n"
            "• La *sede* (Centro, Norte o Sur)\n\n"
            "Podés escribirmelo como quieras ¡Te escucho! 👇"
        )
