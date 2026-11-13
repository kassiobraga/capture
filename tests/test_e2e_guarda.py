"""A guarda de interferencia do mouse dos testes e2e: repete uma vez so para esse erro."""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from tests.e2e import x  # noqa: E402


def fabrica(chamadas):
    """Classe de amostra criada so dentro do teste (para o discover nao rodar os testes dela)."""

    class Amostra(x.CasoE2E):
        def setUp(self):       # sem display nem app: so a logica de repeticao
            self.limpeza = []

        def tearDown(self):
            pass

        def conta(self):
            chamadas[self.id()] = chamadas.get(self.id(), 0) + 1
            return chamadas[self.id()]

        def test_interferencia_uma_vez(self):
            if self.conta() == 1:
                raise x.InterferenciaDoMouse("interferência do mouse: teste")

        def test_interferencia_sempre(self):
            self.conta()
            raise x.InterferenciaDoMouse("interferência do mouse: teste")

        def test_asserção_nunca_repete(self):
            self.conta()
            self.fail("falha de verdade")

        def test_erro_comum_nunca_repete(self):
            self.conta()
            raise ValueError("outro erro")

    return Amostra


class Guarda(unittest.TestCase):
    def roda(self, nome):
        chamadas = {}
        suite = unittest.TestSuite([fabrica(chamadas)(nome)])
        err = io.StringIO()
        antigo, sys.stderr = sys.stderr, err
        try:
            res = unittest.TestResult()
            suite.run(res)
        finally:
            sys.stderr = antigo
        return res, err.getvalue(), chamadas

    def test_passa_na_segunda_e_avisa_em_voz_alta(self):
        res, saida, ch = self.roda("test_interferencia_uma_vez")
        self.assertTrue(res.wasSuccessful())
        self.assertEqual(list(ch.values()), [2])
        self.assertIn("AVISO", saida)
        self.assertIn("interferência do mouse", saida)

    def test_so_repete_uma_vez(self):
        res, saida, ch = self.roda("test_interferencia_sempre")
        self.assertFalse(res.wasSuccessful())
        self.assertEqual(list(ch.values()), [2])

    def test_falha_de_asserção_nao_repete(self):
        res, saida, ch = self.roda("test_asserção_nunca_repete")
        self.assertEqual(len(res.failures), 1)
        self.assertEqual(list(ch.values()), [1])
        self.assertNotIn("AVISO", saida)

    def test_outro_erro_nao_repete(self):
        res, saida, ch = self.roda("test_erro_comum_nunca_repete")
        self.assertEqual(len(res.errors), 1)
        self.assertEqual(list(ch.values()), [1])


if __name__ == "__main__":
    unittest.main()
