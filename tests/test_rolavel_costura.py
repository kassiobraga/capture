"""Fase 1 (congelado): costura de quadros da captura rolavel. Sem GTK e sem display."""
import hashlib
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from capture.costura import Costura, SemSobreposicao, deslocamento, linhas_fixas


def linha(i, largura=16):
    return hashlib.sha256(b"linha-%d" % i).digest()[:largura]


def pagina(n, inicio=0):
    return [linha(inicio + i) for i in range(n)]


def periodica():
    """20 linhas unicas e depois conteudo que se repete a cada 10 linhas."""
    return pagina(20, 7000) + [linha(i % 10) for i in range(300)]


class Deslocamento(unittest.TestCase):
    def test_rolagem_simples(self):
        p = pagina(400)
        self.assertEqual(deslocamento(p[0:100], p[30:130]), 30)

    def test_quadros_iguais_dao_zero(self):
        p = pagina(100)
        self.assertEqual(deslocamento(p, list(p)), 0)

    def test_sem_relacao_da_none(self):
        self.assertIsNone(deslocamento(pagina(100, 0), pagina(100, 5000)))

    def test_sobreposicao_menor_que_o_minimo_da_none(self):
        p = pagina(400)
        self.assertIsNone(deslocamento(p[0:100], p[95:195]))

    def test_minimo_configuravel(self):
        p = pagina(400)
        self.assertEqual(deslocamento(p[0:100], p[95:195], minimo=4), 95)

    def test_alturas_diferentes_levantam_valueerror(self):
        p = pagina(200)
        with self.assertRaises(ValueError):
            deslocamento(p[0:100], p[10:90])

    def test_conteudo_periodico_escolhe_o_menor_sem_esperado(self):
        p = periodica()
        self.assertEqual(deslocamento(p[0:100], p[20:120]), 20)

    def test_conteudo_periodico_usa_o_candidato_mais_proximo_do_esperado(self):
        p = periodica()
        self.assertEqual(deslocamento(p[0:100], p[20:120], esperado=50), 50)
        self.assertEqual(deslocamento(p[0:100], p[20:120], esperado=44), 40)

    def test_cabecalho_e_rodape_fixos(self):
        corpo = pagina(400, 1000)
        cab, rod = pagina(10, 50000), pagina(5, 60000)
        a = cab + corpo[0:85] + rod
        b = cab + corpo[30:115] + rod
        self.assertEqual(deslocamento(a, b), 30)

    def test_tolerancia_aceita_uma_linha_diferente(self):
        p = pagina(400)
        a, b = p[0:100], p[30:130]
        b[20] = linha(99999)
        self.assertIsNone(deslocamento(a, b))
        self.assertEqual(deslocamento(a, b, tolerancia=0.05), 30)


class LinhasFixas(unittest.TestCase):
    def test_cabecalho_e_rodape(self):
        corpo = pagina(400, 1000)
        cab, rod = pagina(10, 50000), pagina(5, 60000)
        a = cab + corpo[0:85] + rod
        b = cab + corpo[30:115] + rod
        self.assertEqual(linhas_fixas(a, b), (10, 5))

    def test_sem_partes_fixas(self):
        p = pagina(400)
        self.assertEqual(linhas_fixas(p[0:100], p[30:130]), (0, 0))

    def test_quadros_iguais(self):
        p = pagina(50)
        self.assertEqual(linhas_fixas(p, list(p)), (50, 0))


class CosturaClasse(unittest.TestCase):
    def test_reconstroi_a_pagina_inteira(self):
        p = pagina(400)
        c = Costura(p[0:100])
        for ini in (30, 60, 90, 120, 150, 180, 210, 240, 270, 300):
            c.adicionar(p[ini:ini + 100])
        self.assertEqual(c.linhas(), p[0:400])
        self.assertEqual(c.altura, 400)

    def test_ultimo_passo_menor_no_fim_da_pagina(self):
        p = pagina(250)
        c = Costura(p[0:100])
        self.assertEqual(c.adicionar(p[60:160]), 60)
        self.assertEqual(c.adicionar(p[120:220]), 60)
        self.assertEqual(c.adicionar(p[150:250]), 30)
        self.assertEqual(c.adicionar(p[150:250]), 0)
        self.assertEqual(c.linhas(), p)

    def test_cabecalho_e_rodape_aparecem_uma_vez(self):
        corpo = pagina(300, 1000)
        cab, rod = pagina(10, 50000), pagina(5, 60000)
        c = Costura(cab + corpo[0:85] + rod)
        for ini in (30, 60, 90, 120, 150):
            c.adicionar(cab + corpo[ini:ini + 85] + rod)
        esperado = cab + corpo[0:235] + rod
        self.assertEqual(c.linhas(), esperado)

    def test_sem_sobreposicao_levanta_e_mantem_o_que_ja_tem(self):
        p = pagina(400)
        c = Costura(p[0:100])
        c.adicionar(p[40:140])
        with self.assertRaises(SemSobreposicao):
            c.adicionar(pagina(100, 9000))
        self.assertEqual(c.linhas(), p[0:140])

    def test_esperado_resolve_conteudo_periodico(self):
        p = periodica()
        c = Costura(p[0:100])
        self.assertEqual(c.adicionar(p[20:120], esperado=50), 50)
        self.assertEqual(c.altura, 150)

    def test_linhas_devolve_copia(self):
        p = pagina(100)
        c = Costura(p)
        c.linhas().clear()
        self.assertEqual(c.altura, 100)


if __name__ == "__main__":
    unittest.main()
