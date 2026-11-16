"""Gravacao em PNG, JPEG e PDF, sem display."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import cairo  # noqa: E402
import gi  # noqa: E402

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf  # noqa: E402

from capture import exportar  # noqa: E402
from tests.helpers import superficie  # noqa: E402


class Formato(unittest.TestCase):
    def test_extensoes(self):
        self.assertEqual(exportar.formato("a.PNG"), "PNG")
        self.assertEqual(exportar.formato("a.jpg"), "JPEG")
        self.assertEqual(exportar.formato("a.jpeg"), "JPEG")
        self.assertEqual(exportar.formato("a.pdf"), "PDF")
        self.assertIsNone(exportar.formato("a.gif"))
        self.assertIsNone(exportar.formato("sem extensao"))

    def test_com_extensao(self):
        self.assertEqual(exportar.com_extensao("x.jpg"), "x.jpg")
        self.assertEqual(exportar.com_extensao("x"), "x.png")
        self.assertEqual(exportar.com_extensao("x", "PDF"), "x.pdf")
        self.assertEqual(exportar.com_extensao("x.gif", "JPEG"), "x.gif.jpg")


class Salvar(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.img = superficie(120, 80, (1, 0, 0, 1))

    def tearDown(self):
        self.dir.cleanup()

    def caminho(self, nome):
        return os.path.join(self.dir.name, nome)

    def test_png(self):
        c = self.caminho("a.png")
        exportar.salvar(self.img, c)
        s = cairo.ImageSurface.create_from_png(c)
        self.assertEqual((s.get_width(), s.get_height()), (120, 80))

    def test_jpeg_tem_o_tamanho_e_a_cor(self):
        c = self.caminho("a.jpg")
        exportar.salvar(self.img, c)
        with open(c, "rb") as f:
            self.assertEqual(f.read(3), b"\xff\xd8\xff")  # assinatura JPEG
        pb = GdkPixbuf.Pixbuf.new_from_file(c)
        self.assertEqual((pb.get_width(), pb.get_height()), (120, 80))
        r, g, b = pb.get_pixels()[:3]
        self.assertGreater(r, 230)
        self.assertLess(g, 30)
        self.assertLess(b, 30)

    def test_jpeg_transparente_vira_branco(self):
        c = self.caminho("t.jpg")
        exportar.salvar(superficie(10, 10), c)
        r, g, b = GdkPixbuf.Pixbuf.new_from_file(c).get_pixels()[:3]
        self.assertGreater(min(r, g, b), 240)

    def test_pdf_de_uma_imagem(self):
        c = self.caminho("a.pdf")
        exportar.salvar(self.img, c)
        with open(c, "rb") as f:
            self.assertEqual(f.read(4), b"%PDF")
        if shutil.which("pdfinfo"):
            self.assertEqual(paginas(c), [(90, 60)])  # 120 x 80 px a 0,75 pt/px

    @unittest.skipUnless(shutil.which("pdfinfo"), "sem pdfinfo (poppler-utils)")
    def test_pdf_com_varias_imagens_uma_por_pagina(self):
        c = self.caminho("abas.pdf")
        exportar.pdf([self.img, superficie(200, 400, (0, 0, 1, 1)), superficie(40, 40)], c)
        self.assertEqual(paginas(c), [(90, 60), (150, 300), (30, 30)])

    def test_pdf_sem_imagens_falha(self):
        with self.assertRaises(ValueError):
            exportar.pdf([], self.caminho("v.pdf"))

    def test_sem_extensao_grava_png(self):
        c = self.caminho("sem")
        exportar.salvar(self.img, c)
        with open(c, "rb") as f:
            self.assertEqual(f.read(4), b"\x89PNG")


def paginas(caminho):
    """Tamanhos (largura, altura) em pt de cada pagina, na ordem (via pdfinfo)."""
    saida = subprocess.run(["pdfinfo", "-f", "1", "-l", "999", caminho], capture_output=True,
                           text=True, check=True).stdout
    return [(round(float(w)), round(float(h)))
            for w, h in re.findall(r"Page\s+\d+ size:\s+([\d.]+) x ([\d.]+)", saida)]


if __name__ == "__main__":
    unittest.main()
