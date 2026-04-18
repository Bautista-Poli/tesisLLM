"""
test_suite.py — Suite completa: agrega todos los grupos de tests NLU.

Correr todos:      python -m tests.test_suite
Correr grupo:      python -m tests.test_suite ambiguos
Correr test:       python -m tests.test_suite pierna_ambigua

Suites individuales:
  python -m tests.test_estudios   → estudios específicos, ambiguos, aclaraciones
  python -m tests.test_datos      → DNI, coberturas, sede, multislot
  python -m tests.test_bordes     → fuera de dominio, edge cases, typos
"""

import sys
from tests._runner import correr_tests
from tests.test_estudios import TESTS as TESTS_ESTUDIOS
from tests.test_datos    import TESTS as TESTS_DATOS
from tests.test_bordes   import TESTS as TESTS_BORDES

TESTS = TESTS_ESTUDIOS + TESTS_DATOS + TESTS_BORDES

if __name__ == "__main__":
    filtro = sys.argv[1] if len(sys.argv) > 1 else None
    correr_tests(TESTS, "NLU EXTRACCIÓN — SUITE COMPLETA", filtro)
