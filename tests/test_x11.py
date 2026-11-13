"""listar_janelas com a saida de xprop/xwininfo gravada, sem servidor X."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from capture.x11 import listar_janelas  # noqa: E402


def info(x, y, w, h, visivel=True):
    return ("xwininfo: Window id: 0x1\n  Absolute upper-left X:  %d\n  Absolute upper-left Y:  %d\n"
            "  Relative upper-left X:  0\n  Width: %d\n  Height: %d\n  Depth: 24\n  Map State: %s\n"
            % (x, y, w, h, "IsViewable" if visivel else "IsUnMapped"))


def prop(desktop=1, gtk=None, net=None, estado=None):
    linhas = ["_NET_WM_DESKTOP(CARDINAL) = %d" % desktop]
    linhas.append("_GTK_FRAME_EXTENTS(CARDINAL) = %s" % gtk if gtk else "_GTK_FRAME_EXTENTS:  not found.")
    linhas.append("_NET_FRAME_EXTENTS(CARDINAL) = %s" % net if net else "_NET_FRAME_EXTENTS:  not found.")
    linhas.append("_NET_WM_STATE(ATOM) = %s" % estado if estado else "_NET_WM_STATE:  not found.")
    return "\n".join(linhas) + "\n"


def falso(janelas, atual=1):
    ids = ", ".join(janelas)
    raiz = ("_NET_CLIENT_LIST_STACKING(WINDOW): window id # %s\n_NET_CURRENT_DESKTOP(CARDINAL) = %d\n"
            % (ids, atual))

    def executa(args):
        if args[0] == "xprop" and args[1] == "-root":
            return raiz
        wid = args[args.index("-id") + 1]
        return janelas[wid][0 if args[0] == "xwininfo" else 1]
    return executa


class ListarJanelas(unittest.TestCase):
    def um(self, i, p):
        return listar_janelas(falso({"0x10": (i, p)}))

    def test_janela_simples(self):
        self.assertEqual(self.um(info(100, 50, 800, 600), prop()), [(100, 50, 800, 600)])

    def test_sombra_do_cliente_gtk_encolhe(self):
        r = self.um(info(100, 50, 800, 600), prop(gtk="10, 12, 8, 14"))
        self.assertEqual(r, [(110, 58, 800 - 22, 600 - 22)])

    def test_moldura_do_gerenciador_aumenta(self):
        # _NET_FRAME_EXTENTS e esquerda, direita, topo, base
        r = self.um(info(100, 50, 800, 600), prop(net="1, 2, 30, 4"))
        self.assertEqual(r, [(99, 20, 803, 634)])

    def test_gtk_tem_prioridade_sobre_net(self):
        r = self.um(info(100, 50, 800, 600), prop(gtk="10, 10, 10, 10", net="1, 1, 30, 1"))
        self.assertEqual(r, [(110, 60, 780, 580)])

    def test_minimizada_e_ignorada(self):
        self.assertEqual(self.um(info(0, 0, 800, 600), prop(estado="_NET_WM_STATE_HIDDEN")), [])

    def test_nao_visivel_e_ignorada(self):
        self.assertEqual(self.um(info(0, 0, 800, 600, visivel=False), prop()), [])

    def test_outra_area_de_trabalho_e_ignorada(self):
        self.assertEqual(listar_janelas(falso({"0x10": (info(0, 0, 800, 600), prop(desktop=0))}, atual=2)), [])

    def test_janela_em_todas_as_areas_de_trabalho_vale(self):
        r = listar_janelas(falso({"0x10": (info(0, 0, 800, 600), prop(desktop=0xFFFFFFFF))}, atual=3))
        self.assertEqual(r, [(0, 0, 800, 600)])

    def test_janelas_minusculas_sao_ignoradas(self):
        self.assertEqual(self.um(info(0, 0, 20, 500), prop()), [])
        self.assertEqual(self.um(info(0, 0, 500, 20), prop()), [])

    def test_ordem_de_baixo_para_cima_e_coordenadas_negativas(self):
        jan = {"0x1": (info(0, 0, 1920, 1080), prop()), "0x2": (info(-30, -20, 400, 300), prop())}
        self.assertEqual(listar_janelas(falso(jan)), [(0, 0, 1920, 1080), (-30, -20, 400, 300)])

    def test_falha_do_xprop_devolve_lista_vazia(self):
        def quebra(args):
            raise OSError("sem xprop")
        self.assertEqual(listar_janelas(quebra), [])


if __name__ == "__main__":
    unittest.main()
