"""Fase 2 (congelado): laco de rolagem com quadros e rolagem injetados. Sem GTK e sem display."""
import hashlib
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.helpers import pixel
from capture.rolagem import Rolador, linhas_para_superficie, quadro_para_linhas


def linha(i):
    return hashlib.sha256(b"pg-%d" % i).digest()[:16]


class Pagina:
    """Pagina falsa: janela de `alt` linhas sobre `corpo`, com cabecalho e rodape fixos."""

    def __init__(self, n, alt=100, passo=60, cab=0, rod=0):
        self.corpo = [linha(i) for i in range(n)]
        self.cab = [linha(70000 + i) for i in range(cab)]
        self.rod = [linha(80000 + i) for i in range(rod)]
        self.alt, self.passo, self.pos = alt, passo, 0
        self.janela = alt - cab - rod
        self.rolagens = 0
        self.esperas = 0
        self.capturas = 0
        self.pendente = []  # respostas forcadas para as proximas capturas

    def completa(self):
        return self.cab + self.corpo + self.rod

    def capturar(self):
        self.capturas += 1
        if self.pendente:
            return self.pendente.pop(0)
        return self.cab + self.corpo[self.pos:self.pos + self.janela] + self.rod

    def rolar(self):
        self.rolagens += 1
        antes = self.capturar_sem_contar()
        self.pos = min(self.pos + self.passo, len(self.corpo) - self.janela)
        self.ultimo = antes
        return self.passo

    def capturar_sem_contar(self):
        return self.cab + self.corpo[self.pos:self.pos + self.janela] + self.rod

    def esperar(self):
        self.esperas += 1


def roda(pg, **kw):
    return Rolador(pg.capturar, pg.rolar, pg.esperar, **kw).executar()


class Laco(unittest.TestCase):
    def test_pagina_simples_ate_o_fim(self):
        pg = Pagina(500)
        r = roda(pg)
        self.assertEqual(r.linhas, pg.completa())
        self.assertEqual(r.motivo, "fim")

    def test_cabecalho_e_rodape_fixos_aparecem_uma_vez(self):
        pg = Pagina(500, cab=10, rod=5)
        r = roda(pg)
        self.assertEqual(r.linhas, pg.completa())
        self.assertEqual(r.motivo, "fim")

    def test_ultimo_passo_menor(self):
        pg = Pagina(250, passo=70)
        r = roda(pg)
        self.assertEqual(r.linhas, pg.completa())

    def test_pagina_que_cabe_na_janela_nao_rola_de_verdade(self):
        pg = Pagina(100)
        r = roda(pg)
        self.assertEqual(r.linhas, pg.completa())
        self.assertEqual(r.motivo, "fim")

    def test_quadro_atrasado_nao_encerra_antes_da_hora(self):
        pg = Pagina(500)
        original = pg.rolar

        def rolar_com_atraso():
            passo = original()
            pg.pendente = [pg.ultimo]
            return passo
        pg.rolar = rolar_com_atraso
        r = roda(pg)
        self.assertEqual(r.linhas, pg.completa())
        self.assertEqual(r.motivo, "fim")

    def test_quadro_corrompido_e_recapturado(self):
        pg = Pagina(500)
        original = pg.rolar
        estado = {"n": 0}

        def rolar_e_corrompe():
            passo = original()
            estado["n"] += 1
            if estado["n"] == 2:
                pg.pendente = [[linha(900000 + i) for i in range(100)]]
            return passo
        pg.rolar = rolar_e_corrompe
        r = roda(pg)
        self.assertEqual(r.linhas, pg.completa())

    def test_salto_maior_que_a_janela_para_com_o_que_ja_tem(self):
        pg = Pagina(500, passo=150)
        r = roda(pg)
        self.assertEqual(r.motivo, "sem_sobreposicao")
        self.assertEqual(r.linhas, pg.corpo[0:100])

    def test_limite_de_altura_corta_no_limite(self):
        pg = Pagina(1000)
        r = roda(pg, altura_maxima=200)
        self.assertEqual(r.motivo, "limite_altura")
        self.assertEqual(len(r.linhas), 200)
        self.assertEqual(r.linhas, pg.corpo[0:200])

    def test_limite_de_quadros(self):
        pg = Pagina(1000)
        r = roda(pg, max_quadros=3)
        self.assertEqual(r.motivo, "limite_quadros")
        self.assertEqual(r.linhas, pg.corpo[0:r.linhas.__len__()])
        self.assertGreaterEqual(len(r.linhas), 100)

    def test_cancelado(self):
        pg = Pagina(1000)
        chamadas = {"n": 0}

        def cancelado():
            chamadas["n"] += 1
            return chamadas["n"] > 2
        r = roda(pg, cancelado=cancelado)
        self.assertEqual(r.motivo, "cancelado")
        self.assertEqual(r.linhas, pg.corpo[0:len(r.linhas)])
        self.assertGreater(len(r.linhas), 100)

    def test_esperar_e_chamado_a_cada_rolagem(self):
        pg = Pagina(500)
        roda(pg)
        self.assertGreaterEqual(pg.esperas, pg.rolagens)

    def test_rolar_sem_passo_conhecido(self):
        pg = Pagina(500)
        original = pg.rolar

        def rolar_sem_passo():
            original()
            return None
        pg.rolar = rolar_sem_passo
        r = roda(pg)
        self.assertEqual(r.linhas, pg.completa())

    def test_resultado_tem_contagem_de_quadros(self):
        pg = Pagina(500)
        r = roda(pg)
        self.assertGreaterEqual(r.quadros, 8)


class Conversoes(unittest.TestCase):
    def test_quadro_para_linhas_e_volta(self):
        w, h = 4, 3
        dados = bytes((x * 10 + y) % 256 for y in range(h) for x in range(w) for _ in range(4))
        linhas = quadro_para_linhas(dados, w, h)
        self.assertEqual(len(linhas), h)
        self.assertTrue(all(len(l) == w * 4 for l in linhas))
        self.assertEqual(b"".join(linhas), dados)

    def test_linhas_para_superficie(self):
        w = 3
        linhas = [bytes([10, 20, 30, 0] * w), bytes([40, 50, 60, 0] * w)]
        s = linhas_para_superficie(linhas, w)
        self.assertEqual((s.get_width(), s.get_height()), (3, 2))
        self.assertEqual(pixel(s, 0, 0)[:3], (30, 20, 10))
        self.assertEqual(pixel(s, 2, 1)[:3], (60, 50, 40))


if __name__ == "__main__":
    unittest.main()
