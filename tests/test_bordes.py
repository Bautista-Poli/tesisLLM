"""
test_bordes.py — Tests de bordes: fuera de dominio, casos límite y errores de tipeo.
Incluye: especialidades no radiológicas, inputs extremos, typos comunes del usuario.

Correr todos:  python -m tests.test_bordes
Correr grupo:  python -m tests.test_bordes typos
Correr test:   python -m tests.test_bordes typo_torax_sin_tilde
"""

import sys
from tests._runner import correr_tests

TESTS = [

    # ── FUERA DE DOMINIO ──────────────────────────────────────────────────────
    {
        "id": "fuera_dominio_cardiologia", "grupo": "fuera_dominio",
        "descripcion": "Especialidad médica fuera de radiología → no extraer estudio",
        "input": "quiero turno para cardiología",
        "checks": [
            ("estudio", None, "no debe extraer una especialidad como estudio"),
        ]
    },
    {
        "id": "fuera_dominio_laboratorio", "grupo": "fuera_dominio",
        "descripcion": "Laboratorio no es radiología → no extraer estudio",
        "input": "necesito hacerme un análisis de sangre",
        "checks": [
            ("estudio", None, "análisis de sangre no es un estudio de radiología"),
        ]
    },
    {
        "id": "fuera_dominio_ecografia", "grupo": "fuera_dominio",
        "descripcion": "Ecografía no es radiología → no extraer como preferred_term de Rx",
        "input": "quiero sacar turno para una eco abdominal",
        "checks": [
            ("estudio_ambiguo", False, "no es ambiguo, es directamente otro dominio"),
            ("estudio", None, "ecografía no debe mapearse a un preferred_term de Rx"),
        ]
    },
    {
        "id": "fuera_dominio_resonancia", "grupo": "fuera_dominio",
        "descripcion": "Resonancia magnética no es Rx → no extraer como estudio radiológico",
        "input": "necesito una resonancia de rodilla",
        "checks": [
            ("estudio", None, "resonancia no debe mapearse a un estudio de Rx"),
        ]
    },
    {
        "id": "fuera_dominio_tomografia", "grupo": "fuera_dominio",
        "descripcion": "Tomografía (TC) no es Rx convencional → no extraer",
        "input": "me pidieron una tomografía de tórax",
        "checks": [
            ("estudio", None, "tomografía no debe mapearse a un estudio de Rx convencional"),
        ]
    },
    {
        "id": "fuera_dominio_consulta_medica", "grupo": "fuera_dominio",
        "descripcion": "Consulta médica genérica → no extraer estudio",
        "input": "quiero ver a un médico por un dolor de cabeza",
        "checks": [
            ("estudio", None, "consulta médica genérica no debe generar estudio"),
        ]
    },

    # ── CASOS BORDE — ESTUDIOS ────────────────────────────────────────────────
    {
        "id": "edge_pecho_sino_torax", "grupo": "edge_estudios",
        "descripcion": "Pecho como sinónimo coloquial de tórax → debe mapear",
        "input": "necesito una placa del pecho",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and ("tórax" in v.lower() or "torax" in v.lower() or "pecho" in v.lower()),
             "debe mapear a tórax o reconocer 'pecho'"),
        ]
    },
    {
        "id": "edge_columna_dorsal", "grupo": "edge_estudios",
        "descripcion": "Columna dorsal explícita → específica, no ambigua",
        "input": "necesito rayos de la columna dorsal",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and "dorsal" in v.lower(), "debe contener dorsal"),
        ]
    },
    {
        "id": "edge_sacro_coxis", "grupo": "edge_estudios",
        "descripcion": "Sacro o cóccix específicos → no ambiguo",
        "input": "necesito rayos del sacro",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and ("sacro" in v.lower() or "coxis" in v.lower() or "lumbar" in v.lower()),
             "debe contener sacro o mapearse a zona sacra"),
        ]
    },
    {
        "id": "edge_input_vacio_equivalente", "grupo": "edge_estudios",
        "descripcion": "Input de saludo puro → no debe extraer estudio ni marcar ambiguo",
        "input": "hola, buenos días",
        "checks": [
            ("estudio", None, "saludo puro no debe extraer estudio"),
            ("estudio_ambiguo", False, "saludo no debe marcar ambiguo"),
        ]
    },
    {
        "id": "edge_doble_zona", "grupo": "edge_estudios",
        "descripcion": "Dos zonas en el mismo mensaje → no inventar estudio combinado",
        "input": "necesito una placa de mano y otra de pie",
        "checks": [
            ("estudio_ambiguo", False, "no debe marcar ambiguo si hay zona explícita"),
            ("estudio", lambda v: v and ("mano" in v.lower() or "pie" in v.lower()),
             "debe extraer al menos una zona"),
        ]
    },
    {
        "id": "edge_rodilla_bilateral", "grupo": "edge_estudios",
        "descripcion": "Rodillas bilaterales → debe reconocer sin agregar 'en carga'",
        "input": "necesito rayos de ambas rodillas",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and "rodilla" in v.lower(), "debe contener rodilla"),
            ("estudio", lambda v: v and "carga" not in v.lower(), "no debe agregar 'en carga'"),
        ]
    },

    # ── TYPOS — ESTUDIOS ──────────────────────────────────────────────────────
    {
        "id": "typo_torax_sin_tilde", "grupo": "typos",
        "descripcion": "Tórax escrito sin tilde → debe reconocer igual",
        "input": "quiero sacar una placa de torax",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and ("tórax" in v.lower() or "torax" in v.lower()),
             "debe mapear a tórax"),
        ]
    },
    {
        "id": "typo_lumbal", "grupo": "typos",
        "descripcion": "'Lumbal' en vez de 'lumbar' → debe reconocer igual",
        "input": "necesito rayos de columna lumbal",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and ("lumbar" in v.lower() or "lumbal" in v.lower()),
             "debe mapear a lumbar pese al typo"),
        ]
    },
    {
        "id": "typo_columna_lumbra", "grupo": "typos",
        "descripcion": "Transposición 'lumbra' en vez de 'lumbar' → debe reconocer",
        "input": "rayos de columna lumbra",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and ("lumbar" in v.lower() or "lumbra" in v.lower()),
             "debe mapear a lumbar pese a la transposición"),
        ]
    },
    {
        "id": "typo_radigrafia", "grupo": "typos",
        "descripcion": "'Radigrafia' con sílaba omitida → debe reconocer estudio",
        "input": "quiero una radigrafia de rodilla derecha",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and "rodilla" in v.lower(),
             "debe extraer rodilla pese al typo en 'radiografía'"),
        ]
    },
    {
        "id": "typo_cervival", "grupo": "typos",
        "descripcion": "'Cervival' en vez de 'cervical' → debe reconocer",
        "input": "necesito rayos de columna cervival",
        "checks": [
            ("estudio_ambiguo", False, "debe ser False"),
            ("estudio", lambda v: v and ("cervical" in v.lower() or "cervival" in v.lower()),
             "debe mapear a cervical pese al typo"),
        ]
    },

    # ── TYPOS — DNI ───────────────────────────────────────────────────────────
    {
        "id": "typo_dni_guiones", "grupo": "typos",
        "descripcion": "DNI con guiones → debe normalizar sin guiones",
        "input": "mi DNI es 30-456-789",
        "checks": [
            ("dni", "30456789", "debe normalizar sin guiones"),
        ]
    },
    {
        "id": "typo_deni", "grupo": "typos",
        "descripcion": "Typo 'deni' en vez de 'DNI' → debe seguir extrayendo el número",
        "input": "mi deni es 30456789",
        "checks": [
            ("dni", "30456789", "debe extraer el número pese al typo en 'DNI'"),
        ]
    },
    {
        "id": "typo_dni_con_letra_o", "grupo": "typos",
        "descripcion": "DNI con 'O' (letra) en vez de '0' (cero) → debe ser null o corregirse",
        "input": "mi DNI es 3O456789",
        "checks": [
            # El sistema debería rechazar el DNI inválido o intentar corregirlo
            ("dni", lambda v: v is None or v == "30456789",
             "debe rechazar o corregir DNI con letra O en vez de cero"),
        ]
    },

    # ── TYPOS — COBERTURAS ────────────────────────────────────────────────────
    {
        "id": "typo_osde_osdi", "grupo": "typos",
        "descripcion": "'OSDI' como typo de 'OSDE' → debe reconocer",
        "input": "mi cobertura es OSDI",
        "checks": [
            ("obra_social", lambda v: v and "OSDE" in v.upper(),
             "debe reconocer OSDE pese al typo"),
        ]
    },
    {
        "id": "typo_pami_pame", "grupo": "typos",
        "descripcion": "'pame' como typo de 'PAMI' → debe reconocer",
        "input": "tengo el pame",
        "checks": [
            ("obra_social", lambda v: v and "PAMI" in v.upper(),
             "debe reconocer PAMI pese al typo"),
        ]
    },
    {
        "id": "typo_galeno_doble_o", "grupo": "typos",
        "descripcion": "'Galenoo' con letra duplicada → debe reconocer Galeno",
        "input": "tengo galenoo",
        "checks": [
            ("obra_social", lambda v: v and "Galeno" in v,
             "debe reconocer Galeno pese a la letra duplicada"),
        ]
    },
]

if __name__ == "__main__":
    filtro = sys.argv[1] if len(sys.argv) > 1 else None
    correr_tests(TESTS, "BORDES, EDGE CASES Y TYPOS", filtro)
