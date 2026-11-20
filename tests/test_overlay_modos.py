"""Selecao de captura: todo modo oferecido tem icone (evita KeyError ao abrir a sobreposicao)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from capture import MODOS  # noqa: E402
from capture import icons  # noqa: E402
from capture.overlay import ICONES_MODO, MODOS_CAPTURA, MODOS_GRAVAR  # noqa: E402


class ModosDaSelecao(unittest.TestCase):
    def test_todo_modo_do_app_tem_icone_na_selecao(self):
        for cod, _ in MODOS:
            with self.subTest(cod):
                self.assertIn(cod, ICONES_MODO)

    def test_modos_de_captura_imediata_nao_incluem_a_rolavel(self):
        self.assertEqual([c for c, _ in MODOS_CAPTURA], ["ret", "janela", "tela", "livre"])

    def test_todo_modo_oferecido_tem_icone(self):
        for lista in (MODOS_CAPTURA, MODOS_GRAVAR):
            for cod, _ in lista:
                with self.subTest(cod):
                    self.assertIn(cod, ICONES_MODO)

    def test_os_icones_da_selecao_existem(self):
        for nome in ICONES_MODO.values():
            with self.subTest(nome):
                self.assertTrue(hasattr(icons, "ic_" + nome), nome)


if __name__ == "__main__":
    unittest.main()
