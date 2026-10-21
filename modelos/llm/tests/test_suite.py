"""
test_suite.py — Suite completa: agrega todos los grupos de tests NLU.

Correr todos:      python -m modelos.llm.tests.test_suite
Correr grupo:      python -m modelos.llm.tests.test_suite ambiguos
Correr test:       python -m modelos.llm.tests.test_suite pierna_ambigua

Suites individuales:
  python -m modelos.llm.tests.test_estudios   → estudios específicos, ambiguos, aclaraciones
  python -m modelos.llm.tests.test_datos      → DNI, coberturas, sede, multislot
  python -m modelos.llm.tests.test_bordes     → fuera de dominio, edge cases, typos
"""

import sys
from modelos.llm.tests._runner import correr_tests
from modelos.llm.tests.test_estudios import TESTS as TESTS_ESTUDIOS
from modelos.llm.tests.test_datos    import TESTS as TESTS_DATOS
from modelos.llm.tests.test_bordes   import TESTS as TESTS_BORDES

TESTS = TESTS_ESTUDIOS + TESTS_DATOS + TESTS_BORDES

if __name__ == "__main__":
    filtro = sys.argv[1] if len(sys.argv) > 1 else None
    correr_tests(TESTS, "NLU EXTRACCIÓN — SUITE COMPLETA", filtro)
