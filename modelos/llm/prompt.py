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
      - Si el usuario dice que no recuerda, da solo parte del número, o hay ambigüedad, devolvé null.
      - El DNI argentino puede escribirse con puntos (30.456.789 = 30456789). Devolvé sin puntos.
      - NUNCA combinar otros números del mensaje con el DNI parcial.

    4. - Antes de devolver cualquier estudio, ejecutá estos pasos en orden:

        PASO 1 — ¿El usuario mencionó una zona anatómica?
        Si el mensaje no tiene zona corporal ("rayos", "rx", "placa" solos) → AMBIGUO.

        PASO 2 — ¿La zona mencionada es una región grande con múltiples estructuras distintas?
        Zonas que SIEMPRE requieren aclaración:
          • "pierna"    → puede ser tibia/peroné, fémur o rodilla. Preguntá cuál.
          • "espalda"   → puede ser cervical, dorsal o lumbar. Preguntá cuál.
          • "brazo"     → puede ser húmero o antebrazo. Preguntá cuál.
          • "pie"       → puede ser calcáneo, dedos o metatarso. Preguntá cuál.
          • "cadera"    → puede ser pelvis o articulación coxofemoral. Preguntá cuál.
          • "columna"   → sin cervical/dorsal/lumbar/sacra es AMBIGUO. Preguntá cuál.
          • "hombro"    → sin derecho/izquierdo es AMBIGUO. Preguntá cuál.
        Si el usuario usó alguna de estas palabras sin especificar más → AMBIGUO, aunque
        exista un término genérico en la tabla. NO uses ese término genérico.

        PASO 3 — Si pasó los pasos anteriores, la zona es específica. Buscá el preferred_term
        más corto que corresponda. NO agregués calificadores que el usuario no mencionó
        (lateralidad, proyecciones, "seriada", "en carga", "bilateral").

        PASO 4 — Si hay contexto de aclaración (ver CONTEXTO IMPORTANTE arriba), combiná
        la zona original con la aclaración para resolver el estudio.

    5. Para el campo "obra_social":
      - Normalizá usando la TABLA DE COBERTURAS. Usá el "nombre_oficial" exacto.
      - Si no está en la tabla pero es claramente una cobertura médica, usá el nombre
        tal como lo escribió el usuario (capitalizado).
    6. Para "sede" los únicos valores válidos son: "Centro", "Norte", "Sur".
      No inferir sede por ubicación geográfica.
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
