import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import math
import unittest

from tests.helpers import desenha, perto, pixel, transparente

VERM = (1.0, 0.0, 0.0)
AZUL = (0.0, 0.0, 1.0)


class Caneta(unittest.TestCase):
    def test_traco_horizontal(self):
        s = desenha({"t": "caneta", "cor": VERM, "esp": 6, "pts": [(10, 50), (90, 50)]})
        self.assertEqual(pixel(s, 50, 50), (255, 0, 0, 255))
        self.assertEqual(pixel(s, 50, 52), (255, 0, 0, 255))
        self.assertTrue(transparente(s, 50, 40))
        self.assertTrue(transparente(s, 50, 60))

    def test_ponta_arredondada_alem_do_ponto_final(self):
        s = desenha({"t": "caneta", "cor": VERM, "esp": 10, "pts": [(20, 50), (80, 50)]})
        self.assertEqual(pixel(s, 83, 50)[3], 255)   # dentro do raio de 5
        self.assertTrue(transparente(s, 90, 50))

    def test_um_ponto_so_desenha_pontinho(self):
        s = desenha({"t": "caneta", "cor": AZUL, "esp": 10, "pts": [(50, 50)]})
        self.assertEqual(pixel(s, 50, 50), (0, 0, 255, 255))
        self.assertTrue(transparente(s, 50, 60))

    def test_segue_a_poligonal(self):
        s = desenha({"t": "caneta", "cor": VERM, "esp": 4, "pts": [(10, 10), (10, 80), (80, 80)]})
        self.assertEqual(pixel(s, 10, 45)[3], 255)
        self.assertEqual(pixel(s, 45, 80)[3], 255)
        self.assertTrue(transparente(s, 45, 45))


class MarcaTexto(unittest.TestCase):
    def test_e_semitransparente(self):
        s = desenha({"t": "marca", "cor": (1.0, 0.88, 0.3), "esp": 20, "pts": [(10, 50), (90, 50)]})
        a = pixel(s, 50, 50)[3]
        self.assertTrue(90 <= a <= 115, a)  # 0.4 * 255 = 102
        self.assertLess(a, 255)

    def test_deixa_o_fundo_aparecer(self):
        s = desenha({"t": "marca", "cor": (1.0, 0.0, 0.0), "esp": 20, "pts": [(10, 50), (90, 50)]},
                    fundo=(1, 1, 1, 1))
        r, g, b, a = pixel(s, 50, 50)
        self.assertEqual(a, 255)
        self.assertEqual(r, 255)
        self.assertTrue(130 <= g <= 175, g)  # 255 * 0.6 = 153
        self.assertTrue(130 <= b <= 175, b)

    def test_ponta_reta(self):
        s = desenha({"t": "marca", "cor": VERM, "esp": 20, "pts": [(20, 50), (80, 50)]})
        # ponta quadrada: cobre ate 10 px alem do fim
        self.assertGreater(pixel(s, 88, 45)[3], 0)
        self.assertTrue(transparente(s, 95, 50))


class Formas(unittest.TestCase):
    def test_retangulo_so_contorno(self):
        s = desenha({"t": "f_ret", "cor": VERM, "esp": 4, "a": (20, 20), "b": (80, 70)})
        self.assertEqual(pixel(s, 50, 20), (255, 0, 0, 255))   # lado de cima
        self.assertEqual(pixel(s, 20, 45), (255, 0, 0, 255))   # lado esquerdo
        self.assertEqual(pixel(s, 80, 45), (255, 0, 0, 255))   # lado direito
        self.assertEqual(pixel(s, 50, 70), (255, 0, 0, 255))   # lado de baixo
        self.assertTrue(transparente(s, 50, 45))               # centro vazio
        self.assertTrue(transparente(s, 10, 10))

    def test_retangulo_com_pontos_invertidos(self):
        s = desenha({"t": "f_ret", "cor": VERM, "esp": 4, "a": (80, 70), "b": (20, 20)})
        self.assertEqual(pixel(s, 50, 20), (255, 0, 0, 255))
        self.assertTrue(transparente(s, 50, 45))

    def test_elipse_so_contorno(self):
        s = desenha({"t": "f_elipse", "cor": AZUL, "esp": 4, "a": (10, 25), "b": (90, 75)})
        self.assertEqual(pixel(s, 90, 50), (0, 0, 255, 255))   # extremo direito
        self.assertEqual(pixel(s, 10, 50), (0, 0, 255, 255))
        self.assertEqual(pixel(s, 50, 25), (0, 0, 255, 255))   # topo
        self.assertTrue(transparente(s, 50, 50))               # centro
        self.assertTrue(transparente(s, 12, 27))               # canto da caixa, fora da elipse

    def test_elipse_degenerada_nao_desenha(self):
        s = desenha({"t": "f_elipse", "cor": AZUL, "esp": 4, "a": (10, 50), "b": (90, 50.5)})
        self.assertTrue(all(transparente(s, x, 50) for x in range(0, 100, 7)))

    def test_linha_diagonal(self):
        s = desenha({"t": "f_linha", "cor": VERM, "esp": 4, "a": (10, 10), "b": (90, 90)})
        for k in (20, 50, 80):
            self.assertEqual(pixel(s, k, k), (255, 0, 0, 255))
        self.assertTrue(transparente(s, 20, 70))
        self.assertTrue(transparente(s, 70, 20))

    def test_seta_tem_haste_e_ponta(self):
        a, b = (10, 50), (80, 50)
        esp = 4
        s = desenha({"t": "f_seta", "cor": VERM, "esp": esp, "a": a, "b": b})
        # haste
        self.assertEqual(pixel(s, 40, 50), (255, 0, 0, 255))
        # ponta: duas abas de comprimento max(10, esp*4) = 16, abertas a +-2.6 rad
        c = max(10, esp * 4)
        for d in (2.6, -2.6):
            meio = (b[0] + c / 2 * math.cos(d), b[1] + c / 2 * math.sin(d))
            x, y = round(meio[0]), round(meio[1])
            self.assertEqual(pixel(s, x, y), (255, 0, 0, 255), (x, y))
        # longe da haste e da ponta nada e desenhado
        self.assertTrue(transparente(s, 40, 20))
        self.assertTrue(transparente(s, 40, 80))

    def test_ponta_da_seta_so_existe_na_seta(self):
        s = desenha({"t": "f_linha", "cor": VERM, "esp": 4, "a": (10, 50), "b": (80, 50)})
        c = 16
        x = round(80 + c / 2 * math.cos(2.6))
        y = round(50 + c / 2 * math.sin(2.6))
        self.assertTrue(transparente(s, x, y))

    def test_seta_cresce_com_a_espessura(self):
        # espessura 10 -> aba de 40 px; ponto a 30 px da ponta na direcao da aba
        s = desenha({"t": "f_seta", "cor": VERM, "esp": 10, "a": (10, 100), "b": (150, 100)}, 200, 200)
        x = round(150 + 30 * math.cos(2.6))
        y = round(100 + 30 * math.sin(2.6))
        self.assertEqual(pixel(s, x, y)[3], 255)


class Texto(unittest.TestCase):
    def test_desenha_pixels_na_cor_pedida(self):
        s = desenha({"t": "texto", "cor": VERM, "txt": "MMMM", "a": (5, 5), "tam": 30, "esp": 2},
                    w=200, h=80)
        achou = False
        for y in range(5, 45):
            for x in range(5, 120):
                p = pixel(s, x, y)
                if p[3] == 255:
                    self.assertTrue(perto(p, (255, 0, 0, 255), 12), p)
                    achou = True
        self.assertTrue(achou, "nenhum pixel de texto encontrado")

    def test_nao_desenha_fora_da_caixa_do_texto(self):
        s = desenha({"t": "texto", "cor": VERM, "txt": "MMMM", "a": (5, 5), "tam": 30, "esp": 2},
                    w=200, h=120)
        self.assertTrue(all(transparente(s, x, 110) for x in range(0, 200)))
        self.assertTrue(all(transparente(s, 190, y) for y in range(0, 120)))

    def test_texto_maior_ocupa_mais_area(self):
        def tinta(tam):
            s = desenha({"t": "texto", "cor": VERM, "txt": "Abc", "a": (2, 2), "tam": tam, "esp": 2},
                        w=200, h=100)
            return sum(1 for y in range(100) for x in range(200) if pixel(s, x, y)[3])
        self.assertGreater(tinta(40), tinta(16) * 2)


if __name__ == "__main__":
    unittest.main()
