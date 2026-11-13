import datetime
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from capture.arquivos import nome_captura, nome_livre, pasta_capturas, pasta_para_exibir  # noqa: E402


class Arquivos(unittest.TestCase):
    def test_nome_livre_nao_sobrescreve(self):
        with tempfile.TemporaryDirectory() as d:
            a = os.path.join(d, "x.png")
            self.assertEqual(nome_livre(a), a)
            open(a, "w").close()
            self.assertEqual(nome_livre(a), os.path.join(d, "x (2).png"))
            open(os.path.join(d, "x (2).png"), "w").close()
            self.assertEqual(nome_livre(a), os.path.join(d, "x (3).png"))

    def test_duas_capturas_no_mesmo_segundo_tem_nomes_diferentes(self):
        agora = datetime.datetime(2026, 1, 2, 3, 4, 5)
        with tempfile.TemporaryDirectory() as d:
            a = nome_captura(d, agora)
            open(a, "w").close()
            b = nome_captura(d, agora)
            self.assertNotEqual(a, b)
            self.assertTrue(os.path.basename(a).startswith("Captura de tela 2026-01-02 030405"))

    def test_cria_a_pasta(self):
        with tempfile.TemporaryDirectory() as d:
            nome_captura(os.path.join(d, "a", "b"))
            self.assertTrue(os.path.isdir(os.path.join(d, "a", "b")))

    def test_capture_dir_sobrepoe_a_pasta(self):
        antigo = os.environ.get("CAPTURE_DIR")
        os.environ["CAPTURE_DIR"] = "/tmp/xyz"
        try:
            self.assertEqual(pasta_capturas(), "/tmp/xyz")
        finally:
            os.environ.pop("CAPTURE_DIR")
            if antigo:
                os.environ["CAPTURE_DIR"] = antigo

    def test_pasta_para_exibir(self):
        home = os.path.expanduser("~")
        self.assertEqual(pasta_para_exibir(home + "/Imagens/a.png"), "~/Imagens/a.png")
        self.assertEqual(pasta_para_exibir("/tmp/a.png"), "/tmp/a.png")


if __name__ == "__main__":
    unittest.main()
