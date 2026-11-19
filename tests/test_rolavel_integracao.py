"""Fase 4 (congelado): o modo Rolavel ligado ao app. Confere a estrutura sem abrir janelas."""
import inspect
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from capture import MODOS
from capture import overlay, rolagem
from capture.overlay import Sessao, caixa_selecao

RAIZ = os.path.join(os.path.dirname(__file__), "..")


def fonte(rel):
    with open(os.path.join(RAIZ, rel), encoding="utf-8") as f:
        return f.read()


class Modos(unittest.TestCase):
    def test_modo_rolavel_e_o_quinto_e_os_outros_nao_mudaram(self):
        self.assertEqual(MODOS[:4], [("ret", "Retângulo"), ("janela", "Janela"),
                                     ("tela", "Tela cheia"), ("livre", "Forma livre")])
        self.assertEqual(MODOS[4], ("rolavel", "Rolável"))
        self.assertEqual(len(MODOS), 5)

    def test_modos_de_gravar_nao_ganham_o_rolavel(self):
        self.assertNotIn("rolavel", dict(overlay.MODOS_GRAVAR))


class Selecao(unittest.TestCase):
    def test_dicas_do_modo_rolar(self):
        d = overlay.DICAS_ROLAR
        self.assertTrue({"ret", "janela"} <= set(d))
        for texto in d.values():
            self.assertIn("Esc cancela", texto)

    def test_sessao_aceita_o_parametro_rolar(self):
        p = inspect.signature(Sessao.__init__).parameters
        self.assertIn("rolar", p)
        self.assertIs(p["rolar"].default, False)

    def test_caixa_de_selecao_do_rolavel_e_um_retangulo(self):
        self.assertEqual(caixa_selecao("rolavel", (10, 10), (60, 50), [], 200, 200),
                         caixa_selecao("ret", (10, 10), (60, 50), [], 200, 200))


class Limites(unittest.TestCase):
    def test_altura_maxima_cabe_numa_superficie_cairo(self):
        p = inspect.signature(rolagem.Rolador.__init__).parameters
        self.assertLessEqual(p["altura_maxima"].default, 32000)


class Ligacao(unittest.TestCase):
    """O app.py abre janelas, entao aqui so se le o codigo-fonte."""

    @classmethod
    def setUpClass(cls):
        cls.app = fonte("capture/app.py")

    def corpo(self, nome):
        m = re.search(r"\n    def %s\(.*?(?=\n    def |\nclass |\Z)" % re.escape(nome), self.app, re.S)
        self.assertIsNotNone(m, "metodo %s nao encontrado em app.py" % nome)
        return m.group(0)

    def test_existem_nova_rolagem_e_parar_rolagem(self):
        self.corpo("nova_rolagem")
        self.corpo("parar_rolagem")

    def test_nova_captura_desvia_o_modo_rolavel(self):
        c = self.corpo("nova_captura")
        self.assertIn('"rolavel"', c)
        self.assertIn("nova_rolagem", c)

    def test_gravar_com_modo_rolavel_vira_retangulo(self):
        c = self.corpo("nova_gravacao")
        self.assertIn("rolavel", c)

    def test_rolagem_usa_a_selecao_de_area_e_o_laco_fora_da_tela(self):
        c = self.corpo("nova_rolagem")
        self.assertIn("apenas_area=True", c)
        self.assertIn("rolar=True", c)
        self.assertIn("threading", self.app)
        self.assertIn("idle_add", self.app)
        self.assertIn("rolar_regiao", self.app)

    def test_resultado_abre_numa_aba_como_qualquer_captura(self):
        self.assertRegex(self.app, r"\.superficie\(\)")
        self.assertIn("self.abrir(", self.app)

    def test_ajuda_da_linha_de_comando_cita_o_modo(self):
        i = self.app.index('add_main_option("modo"')
        self.assertIn("rolavel", self.app[i:i + 400])


if __name__ == "__main__":
    unittest.main()
