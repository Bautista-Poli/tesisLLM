# Modelo 2 — Gestor de diálogo por máquina de estados

Núcleo de diálogo con slot filling no lineal: recibe entidades ya extraídas (inyectadas a mano, sin LLM) y lleva la conversación por los estados `GREETING → COLLECTING → CONFIRMING → COMPLETED / CANCELLED`.

## Contenido

| Archivo | Función |
|---|---|
| `manager.py` | `ConversationManager`: máquina de estados |
| `session.py` | `ConversationSession`: estado por usuario |
| `slots.py` | `SlotSet`, preguntas y plantilla de confirmación |
| `states.py` | Enum `ConversationState` |
| `playground_fsm.py` | Playground interactivo con entidades inyectadas |
| `tests/` | Tests unitarios del diálogo (sin LLM) |

## Requisitos

Ninguno fuera de la biblioteca estándar de Python.

## Comandos (desde la raíz del repo)

```bash
python3 -m modelos.fsm.playground_fsm                   # playground interactivo
python3 -m modelos.fsm.tests.test_conversation_manager  # tests unitarios del ConversationManager
```

Formato de entrada en el playground: `texto` o `texto | {"dni": "12345678", "estudio": "tórax"}`. Comandos: `reiniciar`, `estado`, `salir`.
