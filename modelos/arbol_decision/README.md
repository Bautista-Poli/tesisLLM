# Modelo 3 — Chatbot clásico por menús (árbol de decisión)

Línea base que simula la atención tradicional por WhatsApp con menús numerados: DNI → confirmación de datos → cobertura → menú principal → estudios. Sirve para comparar tiempos de tarea contra el chatbot conversacional.

## Contenido

| Archivo | Función |
|---|---|
| `playground_arbolDeDecision.py` | Flujo completo por menús |
| `tests/test_arbol_decision.py` | Tests del flujo: turnos, informativos, datos no coincidentes, DNI inválido |

## Requisitos

Ninguno fuera de la biblioteca estándar de Python.

## Comandos (desde la raíz del repo)

```bash
python3 -m modelos.arbol_decision.playground_arbolDeDecision   # arrancar el chatbot por menús
python3 -m unittest discover -s modelos/arbol_decision/tests -t . -v  # tests del flujo (~20 s por los delays)
```
