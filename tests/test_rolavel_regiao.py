"""Fase 3 (congelado): rolar_roda (XTest) e rolar_regiao, com dependencias injetadas. Sem display."""
import hashlib
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from capture import x11
from capture.rolagem import Resultado, rolar_regiao


def linha(i):
    return hashlib.sha256(b"rg-%d" % i).digest()[:16]


class RolarRoda(unittest.TestCase):
    def test_move_o_ponteiro_e_gira_a_roda_para_baixo(self):
        ev = []
        x11.rolar_roda(30, 40, 2, enviar=lambda *a: ev.append(a))
        self.assertEqual(ev, [("move", 0, 30, 40),
                              ("press", 5, 30, 40), ("release", 5, 30, 40),
                              ("press", 5, 30, 40), ("release", 5, 30, 40)])

    def test_para_cima_usa_o_botao_4(self):
        ev = []
        x11.rolar_roda(1, 2, 1, baixo=False, enviar=lambda *a: ev.append(a))
        self.assertEqual(ev[1], ("press", 4, 1, 2))
        self.assertEqual(ev[2], ("release", 4, 1, 2))

    def test_cliques_invalidos(self):
        with self.assertRaises(ValueError):
            x11.rolar_roda(0, 0, 0, enviar=lambda *a: None)


class Capturador:
    """Tela falsa de largura 4 px: cada linha tem 16 bytes (BGR0)."""
    w = 4

    def __init__(self, n=400, alt=100, por_clique=20):
        self.corpo = [linha(i) for i in range(n)]
        self.h, self.alt, self.por_clique = alt, alt, por_clique
        self.pos = 0
        self.fechado = 0

    def quadro(self):
        return b"".join(self.corpo[self.pos:self.pos + self.alt])

    def fechar(self):
        self.fechado += 1


def roda_regiao(cap, **kw):
    chamadas = []

    def rodar(x, y, cliques):
        chamadas.append((x, y, cliques))
        cap.pos = min(cap.pos + cliques * cap.por_clique, len(cap.corpo) - cap.alt)

    r = rolar_regiao(100, 50, cap.w, cap.h, capturador=cap, rodar=rodar, esperar=lambda: None, **kw)
    return r, chamadas


class RolarRegiao(unittest.TestCase):
    def test_captura_a_regiao_inteira_rolando(self):
        cap = Capturador()
        r, chamadas = roda_regiao(cap)
        self.assertIsInstance(r, Resultado)
        self.assertEqual(r.motivo, "fim")
        self.assertEqual(r.linhas, cap.corpo)
        self.assertEqual(r.largura, 4)

    def test_ponteiro_vai_para_o_centro_da_regiao(self):
        cap = Capturador()
        r, chamadas = roda_regiao(cap)
        self.assertEqual(chamadas[0][:2], (102, 100))
        self.assertTrue(all(c[:2] == (102, 100) for c in chamadas))

    def test_cliques_por_passo_configuravel(self):
        cap = Capturador(por_clique=10)
        r, chamadas = roda_regiao(cap, cliques=2)
        self.assertTrue(all(c[2] == 2 for c in chamadas))
        self.assertEqual(r.linhas, cap.corpo)

    def test_fecha_o_capturador_uma_vez(self):
        cap = Capturador()
        roda_regiao(cap)
        self.assertEqual(cap.fechado, 1)

    def test_fecha_o_capturador_mesmo_com_erro(self):
        cap = Capturador()

        def quebra():
            raise RuntimeError("falhou")
        cap.quadro = quebra
        with self.assertRaises(RuntimeError):
            roda_regiao(cap)
        self.assertEqual(cap.fechado, 1)

    def test_cancelado_devolve_o_parcial(self):
        cap = Capturador(n=1000)
        n = {"v": 0}

        def cancelado():
            n["v"] += 1
            return n["v"] > 3
        r, _ = roda_regiao(cap, cancelado=cancelado)
        self.assertEqual(r.motivo, "cancelado")
        self.assertEqual(r.linhas, cap.corpo[0:len(r.linhas)])

    def test_superficie_do_resultado(self):
        cap = Capturador()
        r, _ = roda_regiao(cap)
        s = r.superficie()
        self.assertEqual((s.get_width(), s.get_height()), (4, 400))


if __name__ == "__main__":
    unittest.main()
