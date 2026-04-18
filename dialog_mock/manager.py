from __future__ import annotations

import logging
from typing import Dict, Optional

from dialog_mock.session import ConversationSession
from dialog_mock.slots import (
    SLOT_PRIORITY, SLOT_QUESTIONS, CONFIRMATION_TEMPLATE, SlotSet
)
from dialog_mock.states import ConversationState

logger = logging.getLogger(__name__)

RESET_COMMANDS = {"reiniciar", "reset", "empezar de nuevo"}
CANCEL_COMMANDS = {"cancelar", "cancel", "no", "cancelo"}
CONFIRM_COMMANDS = {"si", "sí", "yes", "confirmar", "ok", "dale"}


class ConversationManager:
    """
    Gestor central del flujo de diálogo con Slot Filling no lineal.

    Recibe entidades ya extraídas por el módulo NLU y se encarga
    exclusivamente de la lógica de estados y la respuesta al usuario.

    El almacenamiento en `_sessions` (dict en memoria) es apto para
    desarrollo. Para producción, reemplazar `_get_session` / `_save_session`
    por Redis o PostgreSQL.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, ConversationSession] = {}

    # ------------------------------------------------------------------
    # Gestión de sesiones
    # ------------------------------------------------------------------

    def _get_session(self, phone: str) -> ConversationSession:
        if phone not in self._sessions:
            logger.info(f"Nueva sesión para {phone}")
            self._sessions[phone] = ConversationSession(phone_number=phone)
        return self._sessions[phone]

    def _save_session(self, session: ConversationSession) -> None:
        """Hook de persistencia — reemplazar con Redis / DB en producción."""
        self._sessions[session.phone_number] = session

    def reset_session(self, phone: str) -> None:
        if phone in self._sessions:
            del self._sessions[phone]
            logger.info(f"Sesión reseteada para {phone}")

    # ------------------------------------------------------------------
    # Procesamiento principal
    # ------------------------------------------------------------------

    def process_turn(
        self,
        phone: str,
        user_text: str,
        entities: Dict[str, str],
    ) -> str:
        """
        Procesa un turno de conversación.

        Parámetros
        ----------
        phone      : Identificador de sesión (número de teléfono).
        user_text  : Texto libre del usuario.
        entities   : Entidades ya extraídas por el NLU.
                     Ej: {"dni": "12345678", "estudio": "Rx Tórax"}

        Retorna
        -------
        str : Respuesta del bot lista para enviar.
        """
        session = self._get_session(phone)
        session.add_to_history("user", user_text)
        session.touch()

        normalized = user_text.strip().lower()

        if normalized in RESET_COMMANDS:
            self.reset_session(phone)
            return self._greeting_message()

        if session.state in (ConversationState.COMPLETED, ConversationState.CANCELLED):
            return "Tu turno ya fue procesado. Escribí *reiniciar* para uno nuevo."

        if session.state == ConversationState.GREETING:
            session.state = ConversationState.COLLECTING

        if session.state == ConversationState.COLLECTING:
            response = self._handle_collecting(session, entities)
        elif session.state == ConversationState.CONFIRMING:
            if normalized in CANCEL_COMMANDS:
                response = self._handle_cancellation(session)
            else:
                response = self._handle_confirming(session, normalized)
        else:
            response = "Estado inesperado. Escribí *reiniciar*."

        session.add_to_history("bot", response)
        self._save_session(session)
        return response

    # ------------------------------------------------------------------
    # Handlers de estado
    # ------------------------------------------------------------------

    def _handle_collecting(
        self,
        session: ConversationSession,
        entities: Dict[str, str],
    ) -> str:
        self._merge_entities(session, entities)

        if session.slots.is_complete():
            session.state = ConversationState.CONFIRMING
            return CONFIRMATION_TEMPLATE.format(**session.slots.to_dict())

        missing = session.slots.missing_slots()

        if len(missing) == len(SLOT_PRIORITY):
            return self._greeting_message()

        if len(missing) > 1:
            p1 = missing[0].replace("_", " ")
            p2 = missing[1].replace("_", " ")
            return f"¡Perfecto! Ya tomé esos datos. Necesito tu *{p1}* y tu *{p2}*."

        return SLOT_QUESTIONS[missing[0]]

    def _handle_confirming(self, session: ConversationSession, text: str) -> str:
        if text in CONFIRM_COMMANDS:
            session.state = ConversationState.COMPLETED
            logger.info(f"Turno confirmado para {session.phone_number}: {session.slots.to_dict()}")
            return (
                "🎉 *¡Turno confirmado exitosamente!*\n\n"
                f"Te esperamos en la sede *{session.slots.sede}*.\n"
                "Recibirás un recordatorio 24hs antes. ¡Hasta pronto! 👋"
            )
        return (
            "No entendí tu respuesta. Por favor respondé *SI* para confirmar "
            "o *NO* para cancelar el turno."
        )

    def _handle_cancellation(self, session: ConversationSession) -> str:
        session.state = ConversationState.CANCELLED
        logger.info(f"Turno cancelado para {session.phone_number}")
        return "Entendido, el turno fue cancelado. Escribí *reiniciar* si querés intentarlo de nuevo. 🙏"

    # ------------------------------------------------------------------
    # Utilidades internas
    # ------------------------------------------------------------------

    def _merge_entities(
        self,
        session: ConversationSession,
        entities: Dict[str, str],
    ) -> None:
        """Solo llena slots vacíos; no sobreescribe datos ya confirmados."""
        for slot_name in SLOT_PRIORITY:
            value = entities.get(slot_name)
            if value and getattr(session.slots, slot_name) is None:
                setattr(session.slots, slot_name, value)
                logger.debug(f"Slot '{slot_name}' → '{value}' ({session.phone_number})")

    @staticmethod
    def _greeting_message() -> str:
        return (
            "👋 ¡Hola! Soy el asistente de turnos médicos.\n\n"
            "Podés darme los datos en el orden que quieras:\n"
            "• Tu *DNI*\n"
            "• El *estudio* que necesitás\n"
            "• Tu *obra social*\n"
            "• La *sede* (Centro, Norte o Sur)\n\n"
            "¡Te escucho! 👇"
        )

    # ------------------------------------------------------------------
    # Inspección (debugging y tests)
    # ------------------------------------------------------------------

    def get_session_state(self, phone: str) -> Optional[Dict]:
        session = self._sessions.get(phone)
        if not session:
            return None
        return {
            "phone":      session.phone_number,
            "state":      session.state.value,
            "slots":      session.slots.to_dict(),
            "turn_count": session.turn_count,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
        }
