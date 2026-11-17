"""Testes unitarios do historico de capturas, miniaturas e preferencias."""
import datetime
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import cairo  # noqa: E402

from capture.historico import Registro, pastas_padrao, rotulo_data  # noqa: E402
from tests.helpers import superficie  # noqa: E402


class Historico(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dados = os.path.join(self.tmp.name, "dados")
        self.cache = os.path.join(self.tmp.name, "cache")
        self.config = os.path.join(self.tmp.name, "config")
        self.capturas = os.path.join(self.tmp.name, "capturas")
        os.makedirs(self.capturas)

    def novo_registro(self, agora=None):
        return Registro(self.dados, self.cache, self.config, agora=agora)

    def cria_png(self, nome, w=400, h=240):
        cam = os.path.join(self.capturas, nome)
        img = superficie(w, h, (0.2, 0.5, 0.8, 1.0))
        img.write_to_png(cam)
        return cam, img

    def test_adicionar_ordena_da_mais_nova_para_a_mais_antiga_e_persiste(self):
        t1 = datetime.datetime(2026, 11, 17, 10, 0, 0)
        t2 = datetime.datetime(2026, 11, 17, 10, 5, 0)
        a, img_a = self.cria_png("a.png", 640, 480)
        b, img_b = self.cria_png("b.png", 320, 200)
        reg = self.novo_registro(agora=t1)
        reg.adicionar(a, img_a, agora=t1)
        reg.adicionar(b, img_b, agora=t2)
        itens = reg.listar(agora=t2)
        self.assertEqual([i["caminho"] for i in itens], [b, a])
        self.assertEqual((itens[0]["largura"], itens[0]["altura"]), (320, 200))
        mini = reg.caminho_miniatura(itens[0])
        self.assertTrue(mini and os.path.isfile(mini))
        s = cairo.ImageSurface.create_from_png(mini)
        self.assertLessEqual(s.get_width(), 200)
        self.assertLessEqual(s.get_height(), 130)
        # reabrir do disco preserva a ordem
        reg2 = self.novo_registro(agora=t2)
        self.assertEqual([i["caminho"] for i in reg2.listar(agora=t2)], [b, a])

    def test_remover_tira_da_lista_e_do_cache_mas_mantem_o_arquivo(self):
        a, img = self.cria_png("a.png")
        reg = self.novo_registro()
        it = reg.adicionar(a, img)
        mini = reg.caminho_miniatura(it)
        self.assertTrue(os.path.isfile(mini))
        self.assertTrue(reg.remover(it["id"]))
        self.assertEqual(reg.listar(), [])
        self.assertFalse(os.path.exists(mini))
        self.assertTrue(os.path.isfile(a), "o arquivo original em Capturas deve ficar")

    def test_limpar_apaga_so_a_lista_e_mantem_os_arquivos(self):
        a, ia = self.cria_png("a.png")
        b, ib = self.cria_png("b.png")
        reg = self.novo_registro()
        reg.adicionar(a, ia)
        reg.adicionar(b, ib)
        reg.limpar()
        self.assertEqual(reg.listar(), [])
        self.assertTrue(os.path.isfile(a) and os.path.isfile(b))

    def test_arquivo_sumido_sai_da_lista_sozinho(self):
        a, ia = self.cria_png("a.png")
        b, ib = self.cria_png("b.png")
        reg = self.novo_registro()
        it_a = reg.adicionar(a, ia)
        reg.adicionar(b, ib)
        mini_a = reg.caminho_miniatura(it_a)
        os.unlink(a)
        itens = reg.listar()
        self.assertEqual([i["caminho"] for i in itens], [b])
        self.assertFalse(os.path.exists(mini_a))

    def test_limpeza_diaria_remove_dias_anteriores_sem_apagar_arquivos(self):
        ontem = datetime.datetime(2026, 11, 16, 23, 40, 0)
        hoje = datetime.datetime(2026, 11, 17, 8, 15, 0)
        a, ia = self.cria_png("ontem.png")
        b, ib = self.cria_png("hoje.png")
        reg = self.novo_registro(agora=ontem)
        reg.definir_retencao("diaria", agora=ontem)
        it_ontem = reg.adicionar(a, ia, agora=ontem)
        mini_ontem = reg.caminho_miniatura(it_ontem)
        self.assertEqual(len(reg.listar(agora=ontem)), 1)
        # virou o dia: a entrada de ontem sai da lista, mas o PNG continua na pasta
        self.assertEqual(reg.listar(agora=hoje), [])
        self.assertFalse(os.path.exists(mini_ontem))
        self.assertTrue(os.path.isfile(a))
        reg.adicionar(b, ib, agora=hoje)
        self.assertEqual([i["caminho"] for i in reg.listar(agora=hoje)], [b])
        # preferencia persiste ao reabrir
        reg2 = self.novo_registro(agora=hoje)
        self.assertEqual(reg2.retencao, "diaria")
        self.assertEqual([i["caminho"] for i in reg2.listar(agora=hoje)], [b])

    def test_manter_historico_preserva_dias_anteriores(self):
        ontem = datetime.datetime(2026, 11, 16, 18, 0, 0)
        hoje = datetime.datetime(2026, 11, 17, 9, 0, 0)
        a, ia = self.cria_png("ontem.png")
        reg = self.novo_registro(agora=ontem)
        self.assertEqual(reg.retencao, "manter")
        reg.adicionar(a, ia, agora=ontem)
        self.assertEqual([i["caminho"] for i in reg.listar(agora=hoje)], [a])

    def test_modo_anonimo_nao_registra_e_persiste_preferencia(self):
        a, ia = self.cria_png("a.png")
        reg = self.novo_registro()
        self.assertFalse(reg.anonimo)
        reg.definir_anonimo(True)
        self.assertIsNone(reg.adicionar(a, ia))
        self.assertEqual(reg.listar(), [])
        reg2 = self.novo_registro()
        self.assertTrue(reg2.anonimo)
        reg2.definir_anonimo(False)
        self.assertIsNotNone(reg2.adicionar(a, ia))
        self.assertEqual(len(reg2.listar()), 1)

    def test_miniatura_apagada_do_cache_e_recriada_sob_demanda(self):
        a, ia = self.cria_png("a.png")
        reg = self.novo_registro()
        it = reg.adicionar(a, ia)
        mini = reg.caminho_miniatura(it)
        os.unlink(mini)
        recriada = reg.caminho_miniatura(it)
        self.assertTrue(recriada and os.path.isfile(recriada))

    def test_rotulo_data(self):
        hoje = datetime.date(2026, 11, 17)
        self.assertEqual(rotulo_data("2026-11-17T14:35:10", hoje), "Hoje, 14:35")
        self.assertEqual(rotulo_data("2026-11-16T09:05:00", hoje), "Ontem, 09:05")
        self.assertEqual(rotulo_data("2026-11-10T20:00:00", hoje), "10/11/2026, 20:00")

    def test_capture_estado_sobrepoe_pastas_padrao(self):
        antigo = os.environ.get("CAPTURE_ESTADO")
        os.environ["CAPTURE_ESTADO"] = "/tmp/cap-est"
        try:
            self.assertEqual(pastas_padrao(), ("/tmp/cap-est/dados", "/tmp/cap-est/cache", "/tmp/cap-est/config"))
        finally:
            os.environ.pop("CAPTURE_ESTADO", None)
            if antigo is not None:
                os.environ["CAPTURE_ESTADO"] = antigo


if __name__ == "__main__":
    unittest.main()
