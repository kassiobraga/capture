"""Contas da selecao: monitor com deslocamento e escala, caixa e janela sob o ponto."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from capture.overlay import alvo_janela, caixa_selecao, janela_em, ponto_na_captura  # noqa: E402


class Coordenadas(unittest.TestCase):
    def test_monitor_na_origem_escala_1(self):
        self.assertEqual(ponto_na_captura(0, 0, 1, 30, 40), (30, 40))

    def test_monitor_deslocado(self):
        self.assertEqual(ponto_na_captura(1920, 0, 1, 100, 50), (2020, 50))

    def test_monitor_deslocado_e_escala_2(self):
        # a captura esta em pixels fisicos: (deslocamento + ponto) * escala
        self.assertEqual(ponto_na_captura(1920, 0, 2, 100, 50), (4040, 100))
        self.assertEqual(ponto_na_captura(1920, 100, 2, 0, 0), (3840, 200))


class Caixa(unittest.TestCase):
    def test_retangulo_arrastado_em_qualquer_direcao(self):
        self.assertEqual(caixa_selecao("ret", (10, 20), (50, 80), [], 200, 200), (10, 20, 50, 80))
        self.assertEqual(caixa_selecao("ret", (50, 80), (10, 20), [], 200, 200), (10, 20, 50, 80))

    def test_prende_ao_monitor(self):
        self.assertEqual(caixa_selecao("ret", (-30, -30), (500, 500), [], 200, 100), (0, 0, 200, 100))

    def test_forma_livre_usa_a_caixa_do_caminho(self):
        cam = [(40, 30), (90, 35), (60, 80)]
        self.assertEqual(caixa_selecao("livre", (40, 30), (60, 80), cam, 200, 200), (40, 30, 90, 80))

    def test_forma_livre_sem_caminho_cai_no_retangulo(self):
        self.assertEqual(caixa_selecao("livre", (1, 2), (9, 8), [], 200, 200), (1, 2, 9, 8))


class JanelaSobOPonto(unittest.TestCase):
    JANELAS = [(0, 0, 1920, 1080), (2000, 100, 800, 600), (2200, 300, 400, 300)]  # de baixo para cima

    def test_a_de_cima_vence(self):
        self.assertEqual(janela_em(self.JANELAS, 2300, 400), (2200, 300, 400, 300))
        self.assertEqual(janela_em(self.JANELAS, 2050, 150), (2000, 100, 800, 600))

    def test_borda_direita_e_inferior_sao_exclusivas(self):
        self.assertEqual(janela_em(self.JANELAS, 2800, 150), None)
        self.assertEqual(janela_em(self.JANELAS, 2799, 150), (2000, 100, 800, 600))

    def test_fora_de_todas(self):
        self.assertIsNone(janela_em(self.JANELAS, 5000, 5000))

    def test_alvo_com_monitor_deslocado_e_escala(self):
        # monitor em x=1920, escala 2: ponto local (100, 50) -> pixel (4040, 100)
        jan = [(4000, 50, 300, 200)]
        self.assertEqual(alvo_janela(jan, 1920, 0, 2560, 1080, 2, 100, 50), (4000, 50, 300, 200))

    def test_sem_janela_o_alvo_e_o_monitor_inteiro(self):
        self.assertEqual(alvo_janela([], 1920, 0, 2560, 1080, 2, 100, 50), (3840, 0, 5120, 2160))
        self.assertEqual(alvo_janela([], 0, 0, 1920, 1080, 1, 5, 5), (0, 0, 1920, 1080))


if __name__ == "__main__":
    unittest.main()
