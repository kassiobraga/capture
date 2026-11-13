"""Testes de ponta a ponta no display real (XTest). Veja o README.

So rodam com CAPTURE_E2E=1 (sem ela este pacote nao entrega teste nenhum, e a execucao
padrao `python3 -m unittest discover -s tests` os deixa de fora):

    CAPTURE_E2E=1 python3 -m unittest discover -s tests/e2e -t .
"""
import os
import sys
import unittest


def load_tests(loader, tests, pattern):
    if os.environ.get("CAPTURE_E2E") != "1":
        if any("e2e" in a for a in sys.argv[1:]):
            print("e2e: defina CAPTURE_E2E=1 para rodar estes testes (nenhum foi executado).", file=sys.stderr)
        return unittest.TestSuite()
    aqui = os.path.dirname(os.path.abspath(__file__))
    tests.addTests(loader.discover(aqui, pattern=pattern or "test*.py",
                                   top_level_dir=os.path.dirname(os.path.dirname(aqui))))
    return tests
