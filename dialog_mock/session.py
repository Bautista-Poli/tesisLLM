from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

from dialog_mock.slots import SlotSet
from dialog_mock.states import ConversationState


@dataclass
class ConversationSession:
    """
    Sesión de conversación de un usuario.

    En producción persiste en Redis o DB; aquí se mantiene en memoria.
    """
    phone_number: str
    state:        ConversationState = ConversationState.GREETING
    slots:        SlotSet           = field(default_factory=SlotSet)
    created_at:   datetime          = field(default_factory=datetime.utcnow)
    updated_at:   datetime          = field(default_factory=datetime.utcnow)
    turn_count:   int               = 0
    history:      List[Dict]        = field(default_factory=list)

    def add_to_history(self, role: str, text: str) -> None:
        self.history.append({
            "role": role,
            "text": text,
            "ts":   datetime.utcnow().isoformat(),
        })
        if len(self.history) > 20:
            self.history = self.history[-20:]

    def touch(self) -> None:
        self.updated_at = datetime.utcnow()
        self.turn_count += 1
