"""
test_datos.py — Tests de extracción de datos del paciente.
Incluye: DNI, coberturas/obra social, sede y mensajes multislot.

Correr todos:  python -m tests.test_datos
Correr grupo:  python -m tests.test_datos dni
Correr test:   python -m tests.test_datos osde_directo
"""

import sys
from tests._runner import correr_tests

TESTS = [

    # ── DNI ───────────────────────────────────────────────────────────────────
    {
        "id": "dni_completo", "grupo": "dni",
        "descripcion": "DNI completo válido → debe extraerse",
        "input": "soy Juan Pérez, DNI 30456789",
        "checks": [
            ("dni", "30456789", "debe extraer el DNI completo"),
        ]
    },
    {
        "id": "dni_con_puntos", "grupo": "dni",
        "descripcion": "DNI con puntos → debe normalizarse sin puntos",
        "input": "mi DNI es 30.456.789",
        "checks": [
            ("dni", "30456789", "debe normalizar sin puntos"),
        ]
    },
    {
        "id": "dni_con_espacios", "grupo": "dni",
        "descripcion": "DNI con espacios → debe normalizarse sin espacios",
        "input": "mi DNI es 30 456 789",
        "checks": [
            ("dni", "30456789", "debe normalizar sin espacios"),
        ]
    },
    {
        "id": "dni_parcial", "grupo": "dni",
        "descripcion": "DNI parcial → debe ser null",
        "input": "mi dni termina en 456, no me acuerdo bien",
        "checks": [
            ("dni", None, "DNI incompleto debe ser null"),
        ]
    },
    {
        "id": "dni_mezclado_con_edad", "grupo": "dni",
        "descripcion": "Edad + fragmento DNI → no debe combinarlos",
        "input": "tengo 54 años, mi dni termina en 456",
        "checks": [
            ("dni", None, "no debe combinar edad con DNI parcial"),
        ]
    },
    {
        "id": "dni_7_digitos", "grupo": "dni",
        "descripcion": "DNI de 7 dígitos (anterior a 1990) → debe aceptarse",
        "input": "mi DNI es 8456789",
        "checks": [
            ("dni", "8456789", "debe aceptar DNI de 7 dígitos"),
        ]
    },
    {
        "id": "dni_solo_numero", "grupo": "dni",
        "descripcion": "Número de 8 dígitos sin aclaración explícita → debe interpretar como DNI",
        "input": "30456789",
        "checks": [
            ("dni", "30456789", "debe extraer DNI aunque no diga 'DNI'"),
        ]
    },
    {
        "id": "dni_en_frase_larga", "grupo": "dni",
        "descripcion": "DNI dentro de una frase larga con otros datos → no confundir con otros números",
        "input": "soy María García, necesito turno para el miércoles a las 10, mi DNI es 27654321",
        "checks": [
            ("dni", "27654321", "debe extraer el DNI correcto ignorando la hora"),
        ]
    },

    # ── COBERTURAS ────────────────────────────────────────────────────────────
    {
        "id": "osde_directo", "grupo": "coberturas",
        "descripcion": "OSDE mencionado directamente → normalizar",
        "input": "tengo osde 310",
        "checks": [
            ("obra_social", "OSDE", "debe normalizar a OSDE"),
        ]
    },
    {
        "id": "osecac_por_descripcion", "grupo": "coberturas",
        "descripcion": "Obra social por descripción → debe reconocer OSECAC",
        "input": "la cobertura la tengo a través del sindicato de empleados de comercio",
        "checks": [
            ("obra_social", lambda v: v and "OSECAC" in v.upper(), "debe reconocer OSECAC"),
        ]
    },
    {
        "id": "pami_coloquial", "grupo": "coberturas",
        "descripcion": "PAMI mencionado coloquialmente",
        "input": "soy jubilado, tengo el pami",
        "checks": [
            ("obra_social", lambda v: v and "PAMI" in v.upper(), "debe reconocer PAMI"),
        ]
    },
    {
        "id": "swiss_con_typo", "grupo": "coberturas",
        "descripcion": "Swiss Medical con error ortográfico → debe reconocer",
        "input": "tengo suiss medical",
        "checks": [
            ("obra_social", lambda v: v and "Swiss" in v, "debe reconocer Swiss Medical"),
        ]
    },
    {
        "id": "ioma_coloquial", "grupo": "coberturas",
        "descripcion": "IOMA mencionado como 'obra social de la provincia'",
        "input": "tengo la obra social de la provincia de buenos aires",
        "checks": [
            ("obra_social", lambda v: v and "IOMA" in v.upper(), "debe reconocer IOMA"),
        ]
    },
    {
        "id": "galeno_directo", "grupo": "coberturas",
        "descripcion": "Galeno mencionado directamente → normalizar",
        "input": "mi obra social es Galeno",
        "checks": [
            ("obra_social", lambda v: v and "Galeno" in v, "debe reconocer Galeno"),
        ]
    },
    {
        "id": "sin_cobertura", "grupo": "coberturas",
        "descripcion": "Paciente particular sin obra social → debe ser null",
        "input": "no tengo obra social, soy particular",
        "checks": [
            ("obra_social", None, "debe ser null si no tiene cobertura"),
        ]
    },

    # ── SEDE ──────────────────────────────────────────────────────────────────
    {
        "id": "sede_no_inferida", "grupo": "sede",
        "descripcion": "Ubicación geográfica → NO inferir sede",
        "input": "vivo en Palermo, ¿qué sede me queda cerca?",
        "checks": [
            ("sede", None, "no debe inferir sede por ubicación"),
        ]
    },
    {
        "id": "sede_explicita", "grupo": "sede",
        "descripcion": "Sede mencionada explícitamente → extraer",
        "input": "prefiero la sede norte",
        "ultima_pregunta": "¿En qué sede preferís atenderte?",
        "checks": [
            ("sede", "Norte", "debe extraer sede Norte"),
        ]
    },
    {
        "id": "sede_sur_coloquial", "grupo": "sede",
        "descripcion": "Sede sur mencionada coloquialmente",
        "input": "quiero ir a la del sur",
        "ultima_pregunta": "¿En qué sede preferís atenderte? Tenemos Centro, Norte y Sur.",
        "checks": [
            ("sede", "Sur", "debe extraer sede Sur"),
        ]
    },
    {
        "id": "sede_centro_directo", "grupo": "sede",
        "descripcion": "Sede Centro mencionada explícitamente → extraer",
        "input": "prefiero la sede del centro",
        "ultima_pregunta": "¿En qué sede preferís atenderte? Tenemos Centro, Norte y Sur.",
        "checks": [
            ("sede", "Centro", "debe extraer sede Centro"),
        ]
    },

    # ── MULTISLOT ─────────────────────────────────────────────────────────────
    {
        "id": "todo_en_uno", "grupo": "multislot",
        "descripcion": "Todos los datos en un mensaje → extraer todo",
        "input": "Soy Bautista Alvarez, DNI 40123456, necesito placa de tórax, OSDE, sede Centro",
        "checks": [
            ("nombre_completo", lambda v: v and "Bautista" in v, "debe extraer nombre"),
            ("dni",             "40123456",                       "debe extraer DNI"),
            ("estudio",         lambda v: v and "tórax" in v.lower(), "debe extraer estudio"),
            ("obra_social",     "OSDE",                           "debe extraer obra social"),
            ("sede",            "Centro",                         "debe extraer sede"),
            ("estudio_ambiguo", False,                            "no debe ser ambiguo"),
        ]
    },
    {
        "id": "nombre_compuesto", "grupo": "multislot",
        "descripcion": "Nombre compuesto con partícula → extraer completo",
        "input": "me llamo María de los Ángeles Bustamante",
        "checks": [
            ("nombre_completo", lambda v: v and "María" in v and "Bustamante" in v,
             "debe extraer nombre completo con partícula"),
        ]
    },
    {
        "id": "mensaje_con_ruido", "grupo": "multislot",
        "descripcion": "Mensaje con info irrelevante → extraer solo lo útil",
        "input": "hola buen día, me mandó el doctor López para hacerme una placa de tórax, soy Carlos Ruiz DNI 25678901, tengo galeno",
        "checks": [
            ("nombre_completo", lambda v: v and "Carlos" in v, "debe extraer nombre"),
            ("dni",             "25678901",                    "debe extraer DNI"),
            ("estudio",         lambda v: v and "tórax" in v.lower(), "debe extraer estudio"),
            ("obra_social",     lambda v: v and "Galeno" in v, "debe reconocer Galeno"),
            ("estudio_ambiguo", False, "no debe ser ambiguo"),
        ]
    },
    {
        "id": "disponibilidad_horaria", "grupo": "multislot",
        "descripcion": "Días y horario mencionados → extraer",
        "input": "puedo los miércoles y jueves antes de las 14hs",
        "checks": [
            ("dias_disponibles", lambda v: v and ("miércoles" in v.lower() or "miercoles" in v.lower()),
             "debe extraer días disponibles"),
            ("horario", lambda v: v and "14" in v, "debe extraer horario límite"),
        ]
    },
    {
        "id": "nombre_apellido_invertido", "grupo": "multislot",
        "descripcion": "Nombre en formato 'apellido, nombre' → extraer completo",
        "input": "me llamo Fernández, Roberto",
        "checks": [
            ("nombre_completo", lambda v: v and "Fernández" in v and "Roberto" in v,
             "debe extraer nombre y apellido aunque estén invertidos"),
        ]
    },
]

if __name__ == "__main__":
    filtro = sys.argv[1] if len(sys.argv) > 1 else None
    correr_tests(TESTS, "DATOS DEL PACIENTE", filtro)
