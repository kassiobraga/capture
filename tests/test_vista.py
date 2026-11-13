"""Mapeamento entre a area de desenho do editor e a imagem."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from capture.editor import para_imagem, raio_cantos, vista  # noqa: E402


class Vista(unittest.TestCase):
    def test_imagem_pequena_fica_centralizada_sem_zoom(self):
        zoom, ox, oy = vista(800, 600, 400, 200)
        self.assertEqual((zoom, ox, oy), (1, 200, 200))

    def test_imagem_grande_reduz_para_caber_com_margem(self):
        zoom, ox, oy = vista(840, 640, 1600, 1200)
        self.assertAlmostEqual(zoom, 0.5)   # (640 - 40) / 1200
        self.assertAlmostEqual(ox, (840 - 800) / 2)
        self.assertAlmostEqual(oy, 20)

    def test_reserva_do_dock_nunca_e_coberta(self):
        zoom, ox, oy = vista(840, 640, 1600, 1200, reserva=90)
        self.assertAlmostEqual(zoom, (640 - 90 - 40) / 1200)
        self.assertLessEqual(oy + 1200 * zoom, 640 - 90 - 20 + 1e-6)

    def test_imagem_pequena_centraliza_acima_da_reserva(self):
        zoom, ox, oy = vista(800, 600, 400, 200, reserva=100)
        self.assertEqual((zoom, ox, oy), (1, 200, 150))

    def test_raio_dos_cantos_e_limitado_pela_imagem(self):
        self.assertEqual(raio_cantos(600, 400, 1), 6)
        self.assertEqual(raio_cantos(600, 400, 0.5), 12)        # 6 px na tela = 12 px da imagem
        self.assertEqual(raio_cantos(10, 40, 1), 5)             # no maximo metade do menor lado
        self.assertEqual(raio_cantos(3, 3, 1), 1.5)
        self.assertEqual(raio_cantos(1, 1, 0.02), 0.5)

    def test_zoom_minimo(self):
        self.assertEqual(vista(30, 30, 100000, 100000)[0], 0.02)

    def test_ida_e_volta(self):
        zoom, ox, oy = vista(840, 640, 1600, 1200)
        x, y = ox + 300 * zoom, oy + 700 * zoom
        px, py = para_imagem(x, y, zoom, ox, oy)
        self.assertAlmostEqual(px, 300)
        self.assertAlmostEqual(py, 700)

    def test_origem_da_imagem(self):
        self.assertEqual(para_imagem(250, 120, 1, 250, 120), (0, 0))


if __name__ == "__main__":
    unittest.main()
