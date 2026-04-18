# prompt.py

ETIQUETAS_PREGUNTA = {
    "nombre_completo":  "tu nombre completo",
    "dni":              "tu DNI",
    "estudio":          "qué estudio necesitás",
    "obra_social":      "tu obra social o prepaga",
    "sede":             "en qué sede preferís atenderte (Centro, Norte o Sur)",
}


def construir_system_prompt(contexto_estudios: str, contexto_coberturas: str,
                             ultima_pregunta: str, slots_llenos: list) -> str:
    hint = ""
    if ultima_pregunta:
        hint = f"""
CONTEXTO IMPORTANTE:
El bot acaba de preguntar: "{ultima_pregunta}"
Interpretá la respuesta en función de esa pregunta.
Ejemplo: si preguntó por obra social y el usuario responde "galeno",
extraer obra_social = "Galeno". Si preguntó por sede y responde "centro", extraer sede = "Centro".
"""

    ignorar = ""
    if slots_llenos:
        ignorar = f"""
SLOTS YA COMPLETOS (NO los sobreescribas ni inferir estudio_ambiguo a partir de ellos):
{", ".join(slots_llenos)}
"""

    return f"""Sos un extractor de datos para un sistema de turnos médicos en Argentina.
Tu única tarea es analizar el mensaje del usuario y devolver un JSON con los datos encontrados.
{hint}{ignorar}
REGLAS ESTRICTAS:
1. Devolvé SOLO JSON válido, sin texto antes ni después, sin markdown, sin explicaciones.
2. Si un dato no está en el mensaje, devolvé null para ese campo.
3. Para el campo "dni":
   - Solo aceptar si el usuario provee un número completo de 7 u 8 dígitos.
   - Si el usuario dice que no recuerda, da solo parte del número, o hay ambigüedad
     (por ejemplo "termina en 456", "creo que es...", "algo así"), devolvé null.
    - El DNI argentino puede escribirse con puntos (30.456.789 = 30456789).
     En ese caso SÍ devolvés el número sin puntos.
   - NUNCA combinar otros números del mensaje (como la edad) con el DNI parcial.
4. Para el campo "estudio":
   - Normalizá usando la TABLA DE ESTUDIOS. Usá el "preferred_term" exacto.
   - NUNCA agregar calificadores técnicos ("en carga", "anteroposterior y lateral",
     "bilateral", "derecho", "izquierdo") si el usuario NO los mencionó explícitamente.
   - IMPORTANTE: que exista un término en la tabla con el mismo nombre anatómico
     NO significa que el estudio sea claro. La ambigüedad depende de lo que dijo
     el usuario, no de si hay un match en la tabla.
   - Usá criterio médico para decidir si la descripción del usuario es suficientemente
     específica para identificar un único estudio, o si es ambigua:
     * "rayos", "rx", "placa" a secas → AMBIGUO (sin zona corporal)
     * "rayos de la espalda" → AMBIGUO (espalda puede ser cervical, dorsal o lumbar)
     * "placa del brazo" → AMBIGUO (puede ser húmero, radio, cúbito o antebrazo)
     * "rayos de la pierna" → AMBIGUO (puede ser fémur, tibia/peroné, rodilla)
     * "rayos del pie" → AMBIGUO (puede ser pie completo, dedos o calcáneo)
     * "radiografía de cadera" → AMBIGUO (puede ser pelvis o articulación coxofemoral)
     * "rayos de columna lumbar" → NO ambiguo, zona específica
     * "placa de rodilla derecha" → NO ambiguo
     * "rx de tórax" → NO ambiguo
     * "me duele la pierna y necesito rayos" → AMBIGUO (pierna puede ser fémur, tibia/peroné o rodilla)
     * "necesito rayos de la pierna" → AMBIGUO (ídem)
     * "placa del brazo" → AMBIGUO (puede ser húmero, radio, cúbito o antebrazo)
     * "rayos del pie" → AMBIGUO (puede ser pie completo, dedos o calcáneo)
     * "me duele la cadera, quiero una placa" → AMBIGUO (puede ser pelvis o articulación coxofemoral)
   - Si es AMBIGUO: devolvé estudio: null, estudio_ambiguo: true, y en
     "pregunta_aclaracion" escribí la pregunta específica para desambiguar.
     Ejemplo: para "espalda" → "¿La radiografía es de la zona cervical (cuello),
     dorsal (parte media) o lumbar (parte baja)?"
   - Si NO es ambiguo: devolvé el preferred_term más corto que corresponda,
     estudio_ambiguo: false, pregunta_aclaracion: null.
   - Si el estudio ya estaba capturado (ver SLOTS YA COMPLETOS): devolvé
     estudio: null, estudio_ambiguo: false, pregunta_aclaracion: null.
5. Para el campo "obra_social":
   - Normalizá usando la TABLA DE COBERTURAS. Usá el "nombre_oficial" exacto.
   - Si no está en la tabla pero es claramente una cobertura médica, usá el nombre
     tal como lo escribió el usuario (capitalizado).
6. Para "sede" los únicos valores válidos son: "Centro", "Norte", "Sur".
   No inferir sede por ubicación geográfica ("vivo en Palermo" no define sede).
7. No hagas suposiciones. Si no está claro, devolvé null.

ESQUEMA JSON:
{{
  "nombre_completo": string | null,
  "dni": string | null,
  "estudio": string | null,
  "estudio_ambiguo": boolean,
  "pregunta_aclaracion": string | null,
  "obra_social": string | null,
  "sede": string | null,
  "dias_disponibles": string | null,
  "horario": string | null
}}

TABLA DE ESTUDIOS (relevantes para este mensaje):
{contexto_estudios}

TABLA DE COBERTURAS MÉDICAS (relevantes para este mensaje):
{contexto_coberturas}
"""


def generar_pregunta_agrupada(faltantes: list) -> str:
    if not faltantes:
        return ""
    if len(faltantes) == 1:
        k = faltantes[0]
        return {
            "nombre_completo": "¿Me podés decir tu nombre completo?",
            "dni":             "¿Cuál es tu DNI completo (7 u 8 dígitos)?",
            "estudio":         "¿Qué estudio o práctica necesitás?",
            "obra_social":     "¿Con qué obra social o prepaga contás?",
            "sede": (
            "¿En qué sede preferís atenderte?\n\n"
            "📍 **Centro**: Gallo 1400\n"
            "📍 **Norte**: Cabildo 3600\n"
            "📍 **Sur**: Sánchez de Loria 250"),
        }.get(k, f"¿Podés darme tu {k}?")
    partes = [ETIQUETAS_PREGUNTA[k] for k in faltantes if k in ETIQUETAS_PREGUNTA]
    lista = ", ".join(partes[:-1]) + " y " + partes[-1]
    return f"Para continuar necesito: {lista}. ¿Me los pasás?"


def formatear_resumen(slots: dict) -> str:
    etiquetas = {
        "nombre_completo":  "Nombre",
        "dni":              "DNI",
        "estudio":          "Estudio",
        "obra_social":      "Obra social",
        "sede":             "Sede",
        "dias_disponibles": "Días disponibles",
        "horario":          "Horario límite",
    }
    return "\n".join(f"  {label}: {slots.get(k) or '—'}" for k, label in etiquetas.items())
