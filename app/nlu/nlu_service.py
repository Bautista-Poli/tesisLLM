"""
Módulo de NLU (Natural Language Understanding)
===============================================
Responsable de analizar el texto del usuario y extraer entidades relevantes.

Arquitectura en capas
---------------------
- NLUResult      : DTO con el resultado del análisis.
- MockNLUEngine  : Motor basado en regex/diccionarios (desarrollo/testing).
- NLUService     : Fachada pública. Selecciona el engine según configuración.

Extensibilidad
--------------
Para integrar Rasa, Dialogflow u otro servicio, basta con implementar
la interfaz `BaseNLUEngine` y registrarla en `NLUService`.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DTO de resultado
# ---------------------------------------------------------------------------

@dataclass
class NLUResult:
    """Resultado del análisis NLU de un texto de entrada."""
    raw_text:  str
    intent:    Optional[str]       = None
    entities:  Dict[str, str]      = field(default_factory=dict)
    confidence: float              = 1.0

    def has_entity(self, name: str) -> bool:
        return name in self.entities


# ---------------------------------------------------------------------------
# Interfaz base
# ---------------------------------------------------------------------------

class BaseNLUEngine(ABC):
    @abstractmethod
    def analyze(self, text: str) -> NLUResult:
        """Analiza el texto y retorna un NLUResult."""


# ---------------------------------------------------------------------------
# Mock NLU Engine
# ---------------------------------------------------------------------------

# Catálogos mock — en producción vienen de la base de datos
_ESTUDIOS_CONOCIDOS: List[str] = [
    "cardiología", "cardiologia",
    "radiografía", "radiografia", "rx",
    "análisis de sangre", "analisis de sangre", "laboratorio",
    "traumatología", "traumatologia",
    "pediatría", "pediatria",
    "oftalmología", "oftalmologia",
    "neurología", "neurologia",
    "ecografía", "ecografia",
    "resonancia", "resonancia magnética",
    "tomografía", "tomografia", "tac",
    "dermatología", "dermatologia",
    "kinesiología", "kinesiologia",
]

_SEDES_CONOCIDAS: List[str] = [
    "centro", "norte", "sur",
    "sede centro", "sede norte", "sede sur",
]

_OBRAS_SOCIALES: List[str] = [
    "osde", "swiss medical", "galeno", "omint", "medifé", "medife",
    "obra social", "particular", "sin obra social", "ioma", "pami",
    "accord", "federada", "jerarquicos", "jerárquicos",
]

_INTENT_PATTERNS: Dict[str, List[str]] = {
    "saludar":    [r"\b(hola|buenas|buenas tardes|buenas noches|buen día|hey)\b"],
    "confirmar":  [r"\b(si|sí|confirmo|dale|ok|de acuerdo|correcto)\b"],
    "cancelar":   [r"\b(no|cancelar|salir|cancelo|no quiero)\b"],
    "reiniciar":  [r"\b(reiniciar|empezar de nuevo|reset|volver)\b"],
    "pedir_turno":[r"\b(turno|sacar turno|quiero turno|necesito turno|reservar)\b"],
    "ayuda":      [r"\b(ayuda|help|no entiendo|qué puedo hacer)\b"],
}


class MockNLUEngine(BaseNLUEngine):
    """
    Motor NLU basado en expresiones regulares y listas de vocabulario controlado.

    Diseñado para desarrollo y testing. Suficientemente robusto para una demo
    funcional, y fácilmente reemplazable por un servicio real de NLU.
    """

    def analyze(self, text: str) -> NLUResult:
        normalized = text.strip().lower()
        result = NLUResult(raw_text=text)

        result.intent   = self._extract_intent(normalized)
        result.entities = self._extract_entities(normalized)

        logger.debug(
            f"NLU [mock] → intent='{result.intent}' entities={result.entities}"
        )
        return result

    # ------------------------------------------------------------------
    # Extracción de intención
    # ------------------------------------------------------------------

    def _extract_intent(self, text: str) -> Optional[str]:
        for intent, patterns in _INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    return intent
        return "informar_dato"  # intención por defecto: el usuario está dando info

    # ------------------------------------------------------------------
    # Extracción de entidades
    # ------------------------------------------------------------------

    def _extract_entities(self, text: str) -> Dict[str, str]:
        entities: Dict[str, str] = {}

        dni = self._extract_dni(text)
        if dni:
            entities["dni"] = dni

        estudio = self._extract_estudio(text)
        if estudio:
            entities["estudio"] = estudio.title()

        sede = self._extract_sede(text)
        if sede:
            entities["sede"] = sede.title()

        obra_social = self._extract_obra_social(text)
        if obra_social:
            entities["obra_social"] = obra_social.title()

        return entities

    def _extract_dni(self, text: str) -> Optional[str]:
        """Detecta secuencias de 7 u 8 dígitos como DNI."""
        # Acepta formatos: 12345678 | 12.345.678 | 12 345 678
        match = re.search(r"\b(\d{1,2}[.\s]?\d{3}[.\s]?\d{3})\b", text)
        if match:
            # Normalizar: solo dígitos
            return re.sub(r"[.\s]", "", match.group(1))
        return None

    def _extract_estudio(self, text: str) -> Optional[str]:
        for estudio in _ESTUDIOS_CONOCIDOS:
            if estudio in text:
                # Normalizar hacia la versión sin tilde si existe par
                return estudio
        return None

    def _extract_sede(self, text: str) -> Optional[str]:
        for sede in _SEDES_CONOCIDAS:
            if sede in text:
                # Extraer solo la parte relevante (ej: "sede norte" → "norte")
                return sede.replace("sede ", "").strip()
        return None

    def _extract_obra_social(self, text: str) -> Optional[str]:
        for obra in _OBRAS_SOCIALES:
            if obra in text:
                return obra
        return None


# ---------------------------------------------------------------------------
# Fachada pública
# ---------------------------------------------------------------------------

class NLUService:
    """
    Fachada que selecciona el engine de NLU según la configuración.

    Uso
    ---
        nlu = NLUService()
        result = nlu.analyze("Mi DNI es 30123456, necesito cardiología")
        # result.entities → {"dni": "30123456", "estudio": "Cardiología"}
    """

    def __init__(self) -> None:
        self._engine = self._load_engine()

    def _load_engine(self) -> BaseNLUEngine:
        mode = settings.NLU_MODE
        if mode == "mock":
            logger.info("NLU Engine: Mock (regex/diccionario)")
            return MockNLUEngine()
        # Punto de extensión para motores reales:
        # elif mode == "rasa":
        #     from app.nlu.rasa_engine import RasaNLUEngine
        #     return RasaNLUEngine(settings.NLU_SERVICE_URL)
        else:
            logger.warning(f"NLU mode '{mode}' desconocido. Usando Mock.")
            return MockNLUEngine()

    def analyze(self, text: str) -> NLUResult:
        return self._engine.analyze(text)


# Instancia singleton para inyectar en los endpoints
nlu_service = NLUService()
