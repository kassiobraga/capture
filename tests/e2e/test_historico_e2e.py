"""Painel lateral de historico e modo anonimo na interface real (XTest)."""
import os
import subprocess
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from tests.e2e import x  # noqa: E402


def clip(*args):
    return subprocess.run(["xclip", "-selection", "clipboard", *args], capture_output=True, timeout=5)


class HistoricoE2E(x.CasoE2E):
    def setUp(self):
        super().setUp()
        self.jan = x.Janelas()
        self.limpeza.append(self.jan.fecha)
        self.m = self.jan.monitores()[0]

    def centro(self, g, nome):
        bx, by, bw, bh = g["botoes"][nome]
        ox, oy = self.jan.origem(g["xid"])
        return ox + g["transform"][0] + bx + bw / 2, oy + g["transform"][1] + by + bh / 2

    def test_abrir_painel_e_reabrir_captura_numa_aba(self):
        mx, my = self.m[0], self.m[1]
        app = self.instancia("--novo", "--modo", "ret", geom=True)
        app.espera_janelas(len(self.jan.monitores()))
        time.sleep(0.6)
        with self.entrada() as ent:
            ent.arrastar([(mx + 250, my + 220), (mx + 570, my + 430)])
            arq = app.espera_saida()
            g = app.geometria()
            x.ativa(g["xid"])
            time.sleep(0.5)
            self.assertEqual(g["estado"]["abas"], 1)
            self.assertEqual(g["estado"]["historico_itens"], 1)
            self.assertFalse(g["estado"]["historico_aberto"])

            # fecha a aba: volta para a tela inicial vazia
            ent.tecla("w", "Control_L")
            x.espera(lambda: app.geometria(com_imagem=False)["estado"]["abas"] == 0, 6, 0.2, "aba fechada")
            self.assertEqual(app.geometria(com_imagem=False)["estado"]["tela"], "vazio")

            # abre o painel lateral pelo botao do cabecalho
            g2 = app.geometria(com_imagem=False)
            ent.clicar(*self.centro(g2, "historico"))
            g3 = x.espera(lambda: (d := app.geometria(com_imagem=False))
                          and d["estado"]["historico_aberto"]
                          and "hist_abrir_0" in d["botoes"] and d,
                          6, 0.2, "painel de historico aberto")

            # reabre a captura clicando no item do painel lateral
            ent.clicar(*self.centro(g3, "hist_abrir_0"))
            g4 = x.espera(lambda: (d := app.geometria(com_imagem=False))
                          and d["estado"]["abas"] == 1
                          and d["editor"]["imagem"] == [320, 210] and d,
                          6, 0.2, "captura reaberta numa aba")
            self.assertEqual(g4["estado"]["tela"], "editor")

            # Ctrl+H fecha e reabre o painel
            ent.tecla("h", "Control_L")
            x.espera(lambda: not app.geometria()["estado"]["historico_aberto"], 6, 0.2, "painel fechado")
            ent.tecla("h", "Control_L")
            x.espera(lambda: app.geometria()["estado"]["historico_aberto"], 6, 0.2, "painel reaberto")
            self.assertTrue(os.path.isfile(arq))

    def test_copiar_e_remover_item_mantendo_o_arquivo_salvo(self):
        app = self.instancia("--novo", "--modo", "tela", geom=True)
        arq = app.espera_saida()
        g = app.geometria()
        x.ativa(g["xid"])
        time.sleep(0.5)
        with self.entrada() as ent:
            # abre o painel com Ctrl+H
            ent.tecla("h", "Control_L")
            g2 = x.espera(lambda: (d := app.geometria())
                          and d["estado"]["historico_aberto"]
                          and "hist_copiar_0" in d["botoes"] and d,
                          6, 0.2, "botoes do item no historico")
            subprocess.run(["xclip", "-selection", "clipboard"], input=b"limpo", timeout=5)
            ent.clicar(*self.centro(g2, "hist_copiar_0"))
            time.sleep(0.6)
            alvos = clip("-t", "TARGETS", "-o").stdout.decode(errors="replace").split()
            self.assertIn("image/png", alvos)

            # remove da lista: some do historico mas o PNG continua em Capturas
            ent.clicar(*self.centro(g2, "hist_remover_0"))
            x.espera(lambda: app.geometria()["estado"]["historico_itens"] == 0, 6, 0.2, "item removido")
            self.assertTrue(os.path.isfile(arq), "remover da lista nao deve apagar o arquivo salvo")

    def test_modo_anonimo_nao_salva_em_disco_nem_entra_no_historico(self):
        app = self.instancia(geom=True)
        g = app.geometria(com_imagem=False)
        x.ativa(g["xid"])
        time.sleep(0.4)
        g = app.geometria(com_imagem=False)
        subprocess.run(["xclip", "-selection", "clipboard"], input=b"antes", timeout=5)
        with self.entrada() as ent:
            ent.clicar(*self.centro(g, "anonimo"))
            x.espera(lambda: app.geometria(com_imagem=False)["estado"]["anonimo"], 6, 0.2, "modo anonimo ativo")
            ent.clicar(*self.centro(g, "modo_tela"))
            time.sleep(0.3)
            ent.clicar(*self.centro(g, "capturar"))
            g2 = x.espera(lambda: (d := app.geometria(com_imagem=False))
                          and d["estado"]["abas"] == 1
                          and d["editor"]["imagem"] is not None and d,
                          10, 0.2, "captura anonima na aba")
            self.assertEqual(g2["estado"]["historico_itens"], 0)
            self.assertFalse(os.path.exists(app.saida) and os.listdir(app.saida),
                             "modo anonimo nao deve gravar arquivo automatico")
            alvos = clip("-t", "TARGETS", "-o").stdout.decode(errors="replace").split()
            self.assertIn("image/png", alvos)


if __name__ == "__main__":
    unittest.main()
