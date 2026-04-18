# Chatbot de Turnos Médicos con LLM

Trabajo Final de Ingeniería Informática — Sistema conversacional para gestión de turnos de radiología vía WhatsApp.

El bot extrae información del paciente (DNI, estudio, obra social, sede) a través de una conversación en lenguaje natural, usando un LLM local con RAG basado en terminología SNOMED CT.

---

## Arquitectura general

```
Usuario (WhatsApp)
       │
       ▼
  FastAPI (main.py)          ← webhook + HTTP API
       │
       ├── app/dialog/        ← ConversationManager: máquina de estados
       ├── app/nlu/           ← NLU Service: extracción de entidades
       └── app/db/            ← SQLAlchemy + SQLite/PostgreSQL
```

### Módulos reutilizables

| Módulo | Descripción |
|---|---|
| `nlu_mock/` | Librería de NLU: RAG (TF-IDF), prompts, validadores, cliente Ollama |
| `dialog_mock/` | Gestor de diálogo desacoplado del NLU: sesiones, slots, estados |
| `playgrounds/` | Scripts interactivos para explorar el sistema manualmente |
| `tests/` | Suite de tests unitarios e integración |
| `CSVs/` | Datos de referencia: estudios SNOMED, coberturas médicas, preparaciones |

---

## Stack tecnológico

- **LLM:** [Ollama](https://ollama.ai) con modelo `qwen2.5:7b` (local, sin API externa)
- **RAG:** TF-IDF + cosine similarity sobre terminología SNOMED CT
- **API:** FastAPI + Uvicorn
- **DB:** SQLAlchemy con SQLite (dev) / PostgreSQL (prod)
- **Python:** 3.11+

---

## Instalación

### 1. Clonar y crear entorno

```bash
git clone https://github.com/Bautista-Poli/tesisLLM.git
cd tesisLLM
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Instalar y levantar Ollama

```bash
# Instalar desde https://ollama.ai
ollama pull qwen2.5:7b
ollama serve                    # queda corriendo en localhost:11434
```

### 3. Variables de entorno (opcional)

Crear un archivo `.env` en la raíz si se quieren sobreescribir valores por defecto:

```env
DATABASE_URL=sqlite+aiosqlite:///./turnos.db
ALLOWED_ORIGINS=["*"]
```

---

## Uso

### API (FastAPI)

```bash
python3 main.py
# Docs interactivas: http://localhost:8000/docs
```

### Playground conversacional con LLM

Simula una conversación completa mostrando entidades extraídas y tiempos:

```bash
python3 -m playgrounds.playground_llm
```

### Playground del gestor de diálogo

Prueba el flujo de estados sin LLM, inyectando entidades manualmente:

```bash
python3 -m playgrounds.test-conversationmanager
# Formato de entrada: texto | {"dni": "12345678", "estudio": "tórax"}
```

---

## Tests

### Tests unitarios del ConversationManager (sin LLM, rápidos)

```bash
python3 -m tests.test_conversation_manager
```

### Tests de extracción NLU (requieren Ollama corriendo)

```bash
# Estudios y ambigüedades
python3 -m tests.test_estudios

# DNI, coberturas, sede, multi-slot
python3 -m tests.test_datos

# Casos borde, fuera de dominio, typos
python3 -m tests.test_bordes

# Suite completa
python3 -m tests.test_suite

# Filtrar por grupo específico
python3 -m tests.test_estudios ambiguos
python3 -m tests.test_bordes typos
```

Los tests NLU muestran precisión, recall y F1 por campo extraído.

---

## Estructura del proyecto

```
├── main.py                        # Entrypoint FastAPI
├── requirements.txt
├── CSVs/
│   ├── snomed_con_variantes.csv   # Terminología SNOMED con variantes coloquiales
│   ├── coberturas_medicas.csv     # Obras sociales y planes
│   └── preparaciones_radiologia.csv
│
├── nlu_mock/                      # Librería NLU (importable)
│   ├── rag.py                     # Carga CSVs + búsqueda TF-IDF
│   ├── prompt.py                  # Construcción de system prompt
│   ├── slots.py                   # Definición y lógica de slots
│   ├── validators.py              # Validación de DNI
│   ├── estudios.py                # Normalización de estudios + preparaciones
│   └── ollama_client.py           # HTTP client para Ollama
│
├── dialog_mock/                   # Gestor de diálogo (importable)
│   ├── manager.py                 # ConversationManager: máquina de estados
│   ├── session.py                 # ConversationSession: estado por usuario
│   ├── slots.py                   # SlotSet + preguntas + plantilla confirmación
│   └── states.py                  # Enum ConversationState
│
├── playgrounds/                   # Interfaces interactivas (no son librería)
│   ├── playground_llm.py          # Mock completo con Ollama + RAG
│   ├── playground_fsm.py          # Mock con árbol de decisión
│   └── playground_arbolDeDecision.py
│
├── tests/
│   ├── _runner.py                 # Infraestructura compartida (F1, colores, runner)
│   ├── test_conversation_manager.py  # Tests unitarios del diálogo (sin LLM)
│   ├── test_estudios.py           # Tests de extracción de estudios
│   ├── test_datos.py              # Tests de DNI, coberturas, sede
│   ├── test_bordes.py             # Tests de casos borde, typos, fuera de dominio
│   └── test_suite.py              # Agregador de toda la suite NLU
│
├── app/                           # Aplicación FastAPI (en desarrollo)
│   ├── core/config.py
│   ├── db/models.py
│   ├── dialog/conversation_manager.py
│   └── nlu/nlu_service.py
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
- [ ] Integración con WhatsApp Business API
- [ ] Autenticación y multitenancy
- [ ] Deploy en producción (PostgreSQL + Redis)
