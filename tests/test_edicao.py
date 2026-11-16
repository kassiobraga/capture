"""Pixelar, girar e redimensionar no modelo do editor, sem display."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import cairo  # noqa: E402

from capture.editor import Modelo, bloco_pixel, girar, pixelar, proporcional, redimensionar  # noqa: E402
from tests.helpers import pixel, superficie  # noqa: E402


class Doc(Modelo):
    def __init__(self, img):
        self.avisos = 0
        self._inicia_modelo(self._aviso)
        self.definir_imagem(img)

    def _aviso(self):
        self.avisos += 1


def xadrez(w, h, lado=2):
    """Xadrez preto e branco miudo: pixelado, vira cinza."""
    s = superficie(w, h, (1, 1, 1, 1))
    cr = cairo.Context(s)
    cr.set_source_rgb(0, 0, 0)
    for y in range(0, h, lado):
        for x in range((y // lado) % 2 * lado, w, 2 * lado):
            cr.rectangle(x, y, lado, lado)
    cr.fill()
    return s


def metades(w, h):
    """Esquerda vermelha, direita azul."""
    s = superficie(w, h, (1, 0, 0, 1))
    cr = cairo.Context(s)
    cr.set_source_rgb(0, 0, 1)
    cr.rectangle(w // 2, 0, w - w // 2, h)
    cr.fill()
    return s


class Pixelar(unittest.TestCase):
    def test_bloco_minimo(self):
        self.assertEqual(bloco_pixel(20, 20), 12)
        self.assertEqual(bloco_pixel(480, 100), 30)

    def test_detalhe_fino_vira_media(self):
        p = pixelar(xadrez(64, 64), 0, 0, 64, 64, bloco=16)
        r, g, b, _ = pixel(p, 8, 8)
        self.assertTrue(80 <= r <= 175 and r == g == b, (r, g, b))

    def test_blocos_sao_uniformes(self):
        p = pixelar(metades(64, 64), 0, 0, 64, 64, bloco=16)
        self.assertEqual(pixel(p, 1, 1), pixel(p, 14, 14))
        self.assertEqual(pixel(p, 50, 1), pixel(p, 62, 14))

    def test_marcacao_apagavel_e_desfazivel(self):
        d = Doc(xadrez(100, 100))
        self.assertTrue(d.pixela(10, 10, 60, 50))
        self.assertEqual(len(d.itens), 1)
        it = d.itens[0]
        self.assertEqual(it["pos"], (10, 10))
        self.assertEqual((it["patch"].get_width(), it["patch"].get_height()), (50, 40))
        self.assertTrue(d.alterado)
        self.assertTrue(d.apaga_em((30, 30)))
        self.assertEqual(d.itens, [])
        d.desfazer()
        self.assertEqual(len(d.itens), 1)

    def test_area_minuscula_ou_fora_nao_faz_nada(self):
        d = Doc(xadrez(100, 100))
        self.assertFalse(d.pixela(10, 10, 13, 50))
        self.assertFalse(d.pixela(200, 200, 300, 300))
        self.assertEqual(d.itens, [])
        self.assertFalse(d.alterado)

    def test_area_passando_da_borda_e_limitada(self):
        d = Doc(xadrez(100, 100))
        self.assertTrue(d.pixela(80, 80, 150, 150))
        self.assertEqual(d.itens[0]["patch"].get_width(), 20)

    def test_exportar_aplica_o_pixelado(self):
        d = Doc(xadrez(64, 64))
        d.pixela(0, 0, 64, 64)
        r, g, b, _ = pixel(d.exportar(), 5, 5)
        self.assertTrue(60 <= r <= 195, r)


class Girar(unittest.TestCase):
    def test_horario(self):
        g = girar(metades(40, 20), 1)
        self.assertEqual((g.get_width(), g.get_height()), (20, 40))
        self.assertEqual(pixel(g, 10, 5)[:3], (255, 0, 0))   # esquerda vermelha foi para cima
        self.assertEqual(pixel(g, 10, 35)[:3], (0, 0, 255))

    def test_anti_horario(self):
        g = girar(metades(40, 20), -1)
        self.assertEqual(pixel(g, 10, 5)[:3], (0, 0, 255))
        self.assertEqual(pixel(g, 10, 35)[:3], (255, 0, 0))

    def test_quatro_voltas_voltam_ao_inicio(self):
        img = metades(30, 10)
        g = img
        for _ in range(4):
            g = girar(g, 1)
        self.assertEqual(bytes(g.get_data()), bytes(img.get_data()))

    def test_no_modelo_aplica_marcacoes_e_desfaz(self):
        d = Doc(metades(40, 20))
        d.adiciona({"t": "caneta", "cor": (0, 1, 0), "esp": 2, "pts": [(1, 1), (5, 1)]})
        d.gira(1)
        self.assertEqual((d.base.get_width(), d.base.get_height()), (20, 40))
        self.assertEqual(d.itens, [])
        d.desfazer()
        self.assertEqual((d.base.get_width(), d.base.get_height()), (40, 20))
        self.assertEqual(len(d.itens), 1)


class Redimensionar(unittest.TestCase):
    def test_proporcional(self):
        self.assertEqual(proporcional(1920, 1080, w=960), (960, 540))
        self.assertEqual(proporcional(1920, 1080, h=270), (480, 270))
        self.assertEqual(proporcional(1000, 10, w=50), (50, 1))

    def test_tamanho_novo_e_cores(self):
        r = redimensionar(metades(200, 100), 50, 25)
        self.assertEqual((r.get_width(), r.get_height()), (50, 25))
        self.assertEqual(pixel(r, 5, 12)[:3], (255, 0, 0))
        self.assertEqual(pixel(r, 45, 12)[:3], (0, 0, 255))
        self.assertEqual(pixel(r, 0, 0)[3], 255)  # sem borda transparente

    def test_no_modelo(self):
        d = Doc(metades(200, 100))
        self.assertTrue(d.redimensiona(100, 50))
        self.assertEqual((d.base.get_width(), d.base.get_height()), (100, 50))
        self.assertFalse(d.redimensiona(100, 50))  # mesmo tamanho: nada
        self.assertFalse(d.redimensiona(0, 50))
        d.desfazer()
        self.assertEqual(d.base.get_width(), 200)


class Alterado(unittest.TestCase):
    def test_imagem_nova_comeca_sem_alteracao(self):
        d = Doc(superficie(10, 10))
        self.assertFalse(d.alterado)
        d.adiciona({"t": "caneta", "cor": (0, 0, 0), "esp": 2, "pts": [(1, 1), (5, 5)]})
        self.assertTrue(d.alterado)
        d.definir_imagem(superficie(10, 10))
        self.assertFalse(d.alterado)


if __name__ == "__main__":
    unittest.main()
