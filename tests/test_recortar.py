import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import unittest

from tests.helpers import pixel, superficie, transparente
from capture.overlay import interseccao, recortar


class RecortarRetangulo(unittest.TestCase):
    def setUp(self):
        # imagem 40x30: metade esquerda vermelha, direita azul
        self.img = superficie(40, 30)
        import cairo
        cr = cairo.Context(self.img)
        cr.set_source_rgb(1, 0, 0)
        cr.rectangle(0, 0, 20, 30)
        cr.fill()
        cr.set_source_rgb(0, 0, 1)
        cr.rectangle(20, 0, 20, 30)
        cr.fill()

    def test_tamanho(self):
        out = recortar(self.img, 5, 4, 10, 8)
        self.assertEqual((out.get_width(), out.get_height()), (10, 8))

    def test_conteudo(self):
        out = recortar(self.img, 15, 0, 10, 10)
        self.assertEqual(pixel(out, 0, 0), (255, 0, 0, 255))
        self.assertEqual(pixel(out, 4, 5), (255, 0, 0, 255))
        self.assertEqual(pixel(out, 5, 5), (0, 0, 255, 255))
        self.assertEqual(pixel(out, 9, 9), (0, 0, 255, 255))

    def test_limita_ao_tamanho_da_imagem(self):
        out = recortar(self.img, 30, 20, 100, 100)
        self.assertEqual((out.get_width(), out.get_height()), (10, 10))

    def test_origem_negativa_encolhe_o_recorte(self):
        out = recortar(self.img, -5, -5, 10, 10)
        self.assertEqual((out.get_width(), out.get_height()), (5, 5))
        self.assertEqual(pixel(out, 0, 0), (255, 0, 0, 255))

    def test_sobreposicao_parcial_a_direita(self):
        out = recortar(self.img, 35, 25, 20, 20)
        self.assertEqual((out.get_width(), out.get_height()), (5, 5))
        self.assertEqual(pixel(out, 0, 0), (0, 0, 255, 255))

    def test_totalmente_fora_devolve_none(self):
        for caixa in ((50, 0, 10, 10), (0, 40, 10, 10), (-20, 0, 10, 10), (0, -20, 10, 10), (40, 30, 5, 5)):
            self.assertIsNone(recortar(self.img, *caixa), caixa)

    def test_tamanho_minimo_um_pixel(self):
        out = recortar(self.img, 3, 3, 0, 0)
        self.assertEqual((out.get_width(), out.get_height()), (1, 1))

    def test_interseccao(self):
        self.assertEqual(interseccao(-5, -5, 10, 10, 40, 30), (0, 0, 5, 5))
        self.assertEqual(interseccao(10, 10, 5, 5, 40, 30), (10, 10, 5, 5))
        self.assertIsNone(interseccao(40, 0, 5, 5, 40, 30))


class RecortarForma(unittest.TestCase):
    def setUp(self):
        self.img = superficie(60, 60, (0, 1, 0, 1))
        # triangulo (10,10) (50,10) (10,50), em coordenadas da imagem original
        self.poli = [(10, 10), (50, 10), (10, 50)]
        self.out = recortar(self.img, 10, 10, 40, 40, self.poli)

    def test_tamanho_da_caixa(self):
        self.assertEqual((self.out.get_width(), self.out.get_height()), (40, 40))

    def test_dentro_do_poligono_e_opaco(self):
        self.assertEqual(pixel(self.out, 5, 5), (0, 255, 0, 255))
        self.assertEqual(pixel(self.out, 15, 10), (0, 255, 0, 255))

    def test_fora_do_poligono_e_transparente(self):
        self.assertTrue(transparente(self.out, 38, 38))
        self.assertTrue(transparente(self.out, 35, 30))
        self.assertTrue(transparente(self.out, 39, 20))


if __name__ == "__main__":
    unittest.main()
