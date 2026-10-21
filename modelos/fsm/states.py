from enum import Enum


class ConversationState(str, Enum):
    GREETING   = "greeting"    # Saludo inicial
    COLLECTING = "collecting"  # Recolectando slots
    CONFIRMING = "confirming"  # Esperando confirmación del turno
    COMPLETED  = "completed"   # Turno confirmado
    CANCELLED  = "cancelled"   # El usuario canceló
