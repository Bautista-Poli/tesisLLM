# Chatbot de Turnos Médicos con LLM

Trabajo Final de Ingeniería Informática — Sistema conversacional para gestión de turnos de radiología vía WhatsApp.

El bot extrae información del paciente (DNI, estudio, obra social, sede) a través de una conversación en lenguaje natural, usando un LLM local con RAG basado en terminología SNOMED CT.

---

## Arquitectura general

El trabajo compara tres enfoques conversacionales. Cada uno es independiente y vive en su carpeta dentro de `modelos/`:

```
modelos/
├── llm/              ← Modelo 1: NLU con LLM (Ollama + RAG sobre SNOMED)
├── fsm/              ← Modelo 2: gestor de diálogo por máquina de estados
└── arbol_decision/   ← Modelo 3: chatbot clásico por menús (línea base)
```

### Modelos

| Módulo | Descripción |
|---|---|
| `modelos/llm/` | Modelo 1 — NLU con LLM (Ollama + RAG TF-IDF): prompts, validadores, slots, playground y tests NLU |
| `modelos/fsm/` | Modelo 2 — Gestor de diálogo por máquina de estados: sesiones, slots, estados, playground y tests |
| `modelos/arbol_decision/` | Modelo 3 — Chatbot clásico por menús (árbol de decisión), usado como línea base |
| `CSVs/` | Datos de referencia: estudios SNOMED, coberturas médicas, preparaciones |

---

## Stack tecnológico

- **LLM:** [Ollama](https://ollama.ai) con modelo `qwen2.5:7b` (local, sin API externa)
- **RAG:** TF-IDF + cosine similarity sobre terminología SNOMED CT
- **Python:** 3.11+

---

## Instalación

### 1. Clonar y crear entorno

```bash
git clone https://github.com/Bautista-Poli/tesisLLM.git
cd tesisLLM
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt     # herramientas de desarrollo + dependencias del modelo LLM
```

### 2. Instalar y levantar Ollama

```bash
# Instalar desde https://ollama.ai
ollama pull qwen2.5:7b
ollama serve                    # queda corriendo en localhost:11434
```

---

## Modelos: cómo arrancar y testear

Cada modelo vive en su carpeta dentro de `modelos/`, con su código, playground, tests y dependencias. Desde la raíz del repo:

| Modelo | Carpeta | Arrancar | Tests |
|---|---|---|---|
| 1 — LLM (Ollama + RAG) | [`modelos/llm/`](modelos/llm/README.md) | `python3 -m modelos.llm.playground_llm` | `python3 -m modelos.llm.tests.test_suite` (requiere Ollama) |
| 2 — FSM (máquina de estados) | [`modelos/fsm/`](modelos/fsm/README.md) | `python3 -m modelos.fsm.playground_fsm` | `python3 -m modelos.fsm.tests.test_conversation_manager` |
| 3 — Árbol de decisión (menú) | [`modelos/arbol_decision/`](modelos/arbol_decision/README.md) | `python3 -m modelos.arbol_decision.playground_arbolDeDecision` | `python3 -m unittest discover -s modelos/arbol_decision/tests -t . -v` |

Los tests de los tres modelos se pueden correr uno por uno con los comandos de la tabla.

---

## Estructura del proyecto

```
├── requirements.txt               # Dependencias del proyecto
├── CSVs/
│   ├── snomed_con_variantes.csv   # Terminología SNOMED con variantes coloquiales
│   ├── coberturas_medicas.csv     # Obras sociales y planes
│   └── preparaciones_radiologia.csv
│
├── modelos/                       # Un directorio por modelo
│   ├── llm/                       # Modelo 1: NLU con LLM (Ollama + RAG)
│   │   ├── rag.py                 # Carga CSVs + búsqueda TF-IDF
│   │   ├── prompt.py              # Construcción de system prompt
│   │   ├── slots.py               # Definición y lógica de slots
│   │   ├── validators.py          # Validación de DNI
│   │   ├── estudios.py            # Normalización de estudios + preparaciones
│   │   ├── ollama_client.py       # HTTP client para Ollama
│   │   ├── extractor.py           # ExtractorLLM: RAG + LLM + validación de slots
│   │   ├── borrar.py              # Script auxiliar de exploración de términos
│   │   ├── playground_llm.py      # Playground de conversación con Ollama + RAG
│   │   ├── evaluacion/            # Evaluación: TOP_K (recall@k, F1) y baseline TF-IDF (curva PR)
│   │   └── tests/                 # Tests de extracción NLU (requieren Ollama)
│   │       ├── _runner.py         # Infraestructura compartida (F1, colores, runner)
│   │       ├── test_estudios.py   # Tests de extracción de estudios
│   │       ├── test_datos.py      # Tests de DNI, coberturas, sede
│   │       ├── test_bordes.py     # Tests de casos borde, typos, fuera de dominio
│   │       └── test_suite.py      # Agregador de toda la suite NLU
│   │
│   ├── fsm/                       # Modelo 2: gestor de diálogo (máquina de estados)
│   │   ├── manager.py             # ConversationManager: máquina de estados
│   │   ├── session.py             # ConversationSession: estado por usuario
│   │   ├── slots.py               # SlotSet + preguntas + plantilla confirmación
│   │   ├── states.py              # Enum ConversationState
│   │   ├── playground_fsm.py      # Playground con entidades inyectadas
│   │   └── tests/
│   │       └── test_conversation_manager.py  # Tests unitarios del diálogo (sin LLM)
│   │
│   └── arbol_decision/            # Modelo 3: chatbot clásico por menús
│       ├── playground_arbolDeDecision.py
│       └── tests/
│           └── test_arbol_decision.py    # Tests del flujo por menús
│
└── ObtencionDeInfoMedica/         # Scripts de construcción del dataset SNOMED
    └── Snomed/
```

---

## Flujo de conversación

El bot recorre un ciclo de **Slot Filling no lineal** para recolectar 4 datos:

| Slot | Descripción |
|---|---|
| `nombre` | Nombre del paciente |
| `dni` | DNI (validado: 7–8 dígitos) |
| `estudio` | Estudio de radiología (normalizado contra SNOMED) |
| `obra_social` | Cobertura médica |
| `sede` | Sede preferida |

**Estados:** `GREETING → COLLECTING → CONFIRMING → COMPLETED / CANCELLED`

Si el estudio es ambiguo (ej: "me duele la espalda"), el bot hace una pregunta de aclaración antes de continuar.

---

## Dataset SNOMED

Los estudios de radiología se obtienen de **SNOMED CT** y se enriquecen con variantes coloquiales generadas automáticamente. Los scripts en `ObtencionDeInfoMedica/` procesan los archivos raw de SNOMED para generar `CSVs/snomed_con_variantes.csv`.

---

## Estado del proyecto

- [x] NLU con Ollama + RAG (TF-IDF)
- [x] Slot Filling no lineal con detección de ambigüedad
- [x] Gestor de diálogo con máquina de estados
- [x] Suite de tests con métricas F1 por campo
- [x] Playgrounds interactivos para desarrollo
- [ ] Autenticación y multitenancy
- [ ] Deploy en producción (PostgreSQL + Redis)
