"""Captura e area de transferencia via python-xlib num display X de verdade.

Pulados sem DISPLAY, sem python-xlib ou sem xclip (usado so para ler de volta).
Para rodar sem desktop: xvfb-run -a python3 -m unittest tests.test_xlib
"""
import os
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from capture import area, x11  # noqa: E402

PULAR = None
if not x11.tem_xlib():
    PULAR = "python-xlib nao esta instalado"
elif not os.environ.get("DISPLAY"):
    PULAR = "sem display X"


@unittest.skipIf(PULAR, PULAR or "")
class Xlib(unittest.TestCase):
    def test_foto_tem_o_tamanho_da_tela(self):
        img = x11.foto_da_tela()
        d = x11._abre()
        geo = d.screen().root.get_geometry()
        d.close()
        self.assertEqual((img.get_width(), img.get_height()), (geo.width, geo.height))

    def test_libx11_e_python_xlib_dao_a_mesma_imagem(self):
        a, b = x11._foto_libx11(), x11._foto_xlib()
        self.assertEqual((a.get_width(), a.get_height()), (b.get_width(), b.get_height()))
        self.assertEqual(bytes(a.get_data()), bytes(b.get_data()))

    def test_listar_janelas_nao_falha(self):
        self.assertIsInstance(x11.listar_janelas(), list)

    @unittest.skipUnless(shutil.which("xclip"), "sem xclip para ler a area de transferencia")
    def test_copia_pequena_e_grande(self):
        for n in (1000, 2_000_000):  # a grande passa pelo protocolo INCR
            dados = os.urandom(n)
            self.assertTrue(area.copiar(dados))
            lido = subprocess.run(["xclip", "-o", "-selection", "clipboard", "-t", "image/png"],
                                  capture_output=True, timeout=20).stdout
            self.assertEqual(lido, dados)
        subprocess.run(["xclip", "-selection", "clipboard"], input=b"fim", timeout=5)


if __name__ == "__main__":
    unittest.main()
