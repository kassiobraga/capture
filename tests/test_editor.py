import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import os
import tempfile
import unittest

import cairo

from capture.editor import Modelo, caixa_item
from tests.helpers import pixel, superficie, transparente

VERM = (1.0, 0.0, 0.0)


class Doc(Modelo):
    """Modelo sem GTK, com contagem dos avisos."""

    def __init__(self, img):
        self.avisos = 0
        self._inicia_modelo(self._aviso)
        self.definir_imagem(img)

    def _aviso(self):
        self.avisos += 1


def caneta(pts, esp=4):
    return {"t": "caneta", "cor": VERM, "esp": esp, "pts": pts}


def ret(a, b):
    return {"t": "f_ret", "cor": VERM, "esp": 4, "a": a, "b": b}


class Borracha(unittest.TestCase):
    def setUp(self):
        self.d = Doc(superficie(100, 100, (1, 1, 1, 1)))

    def test_apaga_item_sob_o_ponto(self):
        self.d.adiciona(caneta([(10, 10), (50, 10)]))
        self.assertTrue(self.d.apaga_em((30, 10)))
        self.assertEqual(self.d.itens, [])

    def test_tolerancia_em_volta_do_item(self):
        self.d.adiciona(caneta([(10, 10), (50, 10)], esp=4))
        # tolerancia = 6 + esp/2 = 8
        self.assertTrue(self.d.apaga_em((30, 17)))

    def test_fora_da_tolerancia_nao_apaga(self):
        self.d.adiciona(caneta([(10, 10), (50, 10)], esp=4))
        self.assertFalse(self.d.apaga_em((30, 19)))
        self.assertFalse(self.d.apaga_em((70, 10)))
        self.assertEqual(len(self.d.itens), 1)

    def test_apaga_so_o_de_cima(self):
        self.d.adiciona(ret((10, 10), (60, 60)))
        self.d.adiciona(caneta([(20, 20), (40, 40)]))
        self.d.apaga_em((30, 30))
        self.assertEqual([i["t"] for i in self.d.itens], ["f_ret"])

    def test_apagar_pode_ser_desfeito(self):
        self.d.adiciona(caneta([(10, 10), (50, 10)]))
        self.d.apaga_em((30, 10))
        self.d.desfazer()
        self.assertEqual(len(self.d.itens), 1)

    def test_caixa_do_texto_e_estimada(self):
        x0, y0, x1, y1 = caixa_item({"t": "texto", "txt": "abcd", "a": (10, 20), "tam": 20})
        self.assertEqual((x0, y0), (10, 20))
        self.assertAlmostEqual(x1, 10 + 4 * 20 * 0.62)
        self.assertAlmostEqual(y1, 20 + 20 * 1.3)


class DesfazerRefazer(unittest.TestCase):
    def setUp(self):
        self.d = Doc(superficie(50, 50, (1, 1, 1, 1)))

    def test_desfazer_e_refazer(self):
        self.d.adiciona(caneta([(5, 5), (20, 5)]))
        self.d.adiciona(ret((5, 10), (30, 30)))
        self.assertEqual(len(self.d.itens), 2)
        self.d.desfazer()
        self.assertEqual(len(self.d.itens), 1)
        self.d.desfazer()
        self.assertEqual(self.d.itens, [])
        self.d.refazer()
        self.assertEqual([i["t"] for i in self.d.itens], ["caneta"])
        self.d.refazer()
        self.assertEqual([i["t"] for i in self.d.itens], ["caneta", "f_ret"])

    def test_nada_a_desfazer_ou_refazer(self):
        n = self.d.avisos
        self.d.desfazer()
        self.d.refazer()
        self.assertEqual(self.d.avisos, n)
        self.assertEqual(self.d.itens, [])

    def test_nova_acao_limpa_o_refazer(self):
        self.d.adiciona(caneta([(5, 5), (20, 5)]))
        self.d.desfazer()
        self.d.adiciona(ret((5, 10), (30, 30)))
        self.d.refazer()
        self.assertEqual([i["t"] for i in self.d.itens], ["f_ret"])

    def test_avisa_quando_muda(self):
        self.d.adiciona(caneta([(5, 5), (20, 5)]))
        self.d.desfazer()
        self.assertEqual(self.d.avisos, 1)
        self.d.refazer()
        self.assertEqual(self.d.avisos, 2)

    def test_nova_imagem_zera_o_historico(self):
        self.d.adiciona(caneta([(5, 5), (20, 5)]))
        self.d.definir_imagem(superficie(10, 10))
        self.assertEqual((self.d.itens, self.d.desf, self.d.refz), ([], [], []))


class Corte(unittest.TestCase):
    def setUp(self):
        self.d = Doc(superficie(100, 80, (1, 1, 1, 1)))

    def test_corta_para_a_caixa(self):
        self.assertTrue(self.d.corta(10, 20, 60, 50))
        self.assertEqual((self.d.base.get_width(), self.d.base.get_height()), (50, 30))

    def test_aceita_pontos_invertidos(self):
        self.assertTrue(self.d.corta(60, 50, 10, 20))
        self.assertEqual((self.d.base.get_width(), self.d.base.get_height()), (50, 30))

    def test_area_pequena_e_ignorada(self):
        self.assertFalse(self.d.corta(10, 10, 15, 50))
        self.assertEqual((self.d.base.get_width(), self.d.base.get_height()), (100, 80))
        self.assertEqual(self.d.desf, [])

    def test_aplica_as_marcacoes_e_zera_a_lista(self):
        self.d.adiciona(ret((20, 25), (50, 45)))
        self.d.corta(10, 20, 60, 50)
        self.assertEqual(self.d.itens, [])
        # contorno do retangulo (20,25) agora em (10,5)
        self.assertEqual(pixel(self.d.base, 10, 15), (255, 0, 0, 255))

    def test_origem_negativa_corta_so_a_parte_dentro(self):
        self.assertTrue(self.d.corta(-20, -20, 30, 30))
        self.assertEqual((self.d.base.get_width(), self.d.base.get_height()), (30, 30))

    def test_sobreposicao_parcial(self):
        self.assertTrue(self.d.corta(80, 60, 200, 200))
        self.assertEqual((self.d.base.get_width(), self.d.base.get_height()), (20, 20))

    def test_totalmente_fora_nao_muda_nada(self):
        for caixa in ((150, 10, 200, 60), (10, 100, 60, 150), (-60, 10, -10, 60)):
            self.assertFalse(self.d.corta(*caixa), caixa)
        self.assertEqual((self.d.base.get_width(), self.d.base.get_height()), (100, 80))
        self.assertEqual(self.d.desf, [])

    def test_interseccao_de_8_px_ou_menos_e_ignorada(self):
        self.assertFalse(self.d.corta(92, 10, 140, 60))   # so 8 px dentro
        self.assertTrue(self.d.corta(91, 10, 140, 60))    # 9 px
        self.assertEqual(self.d.base.get_width(), 9)

    def test_corte_pode_ser_desfeito(self):
        self.d.corta(10, 20, 60, 50)
        self.d.desfazer()
        self.assertEqual((self.d.base.get_width(), self.d.base.get_height()), (100, 80))


class Exportar(unittest.TestCase):
    def test_exporta_imagem_com_marcacoes(self):
        d = Doc(superficie(60, 40, (1, 1, 1, 1)))
        d.adiciona(caneta([(10, 20), (50, 20)], esp=6))
        out = d.exportar()
        self.assertEqual((out.get_width(), out.get_height()), (60, 40))
        self.assertEqual(pixel(out, 30, 20), (255, 0, 0, 255))
        self.assertEqual(pixel(out, 30, 5), (255, 255, 255, 255))

    def test_exportar_nao_altera_a_base(self):
        d = Doc(superficie(60, 40, (1, 1, 1, 1)))
        d.adiciona(caneta([(10, 20), (50, 20)], esp=6))
        d.exportar()
        self.assertEqual(pixel(d.base, 30, 20), (255, 255, 255, 255))

    def test_grava_png_legivel(self):
        d = Doc(superficie(60, 40, (0, 0, 1, 1)))
        d.adiciona(caneta([(10, 20), (50, 20)], esp=6))
        with tempfile.TemporaryDirectory() as pasta:
            arq = os.path.join(pasta, "saida.png")
            d.exportar().write_to_png(arq)
            with open(arq, "rb") as f:
                self.assertEqual(f.read(8), b"\x89PNG\r\n\x1a\n")
            volta = cairo.ImageSurface.create_from_png(arq)
        self.assertEqual((volta.get_width(), volta.get_height()), (60, 40))
        self.assertEqual(pixel(volta, 30, 20), (255, 0, 0, 255))
        self.assertEqual(pixel(volta, 30, 5), (0, 0, 255, 255))

    def test_png_preserva_transparencia_de_recorte_livre(self):
        from capture.overlay import recortar
        base = recortar(superficie(40, 40, (0, 1, 0, 1)), 0, 0, 40, 40, [(0, 0), (40, 0), (0, 40)])
        d = Doc(base)
        with tempfile.TemporaryDirectory() as pasta:
            arq = os.path.join(pasta, "livre.png")
            d.exportar().write_to_png(arq)
            volta = cairo.ImageSurface.create_from_png(arq)
        self.assertTrue(transparente(volta, 38, 38))
        self.assertEqual(pixel(volta, 5, 5), (0, 255, 0, 255))


if __name__ == "__main__":
    unittest.main()
