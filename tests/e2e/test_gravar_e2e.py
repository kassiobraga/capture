"""Gravacao de tela (MP4 e GIF), barra fora da area e historico na interface real (XTest)."""
import json
import os
import subprocess
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from tests.e2e import x  # noqa: E402


def clip(*args):
    return subprocess.run(["xclip", "-selection", "clipboard", *args], capture_output=True, timeout=5)


def intercepta(a, b):
    return (a[0] < b[0] + b[2] and a[0] + a[2] > b[0]
            and a[1] < b[1] + b[3] and a[1] + a[3] > b[1])


class GravacaoE2E(x.CasoE2E):
    def setUp(self):
        super().setUp()
        self.jan = x.Janelas()
        self.limpeza.append(self.jan.fecha)
        self.m = self.jan.monitores()[0]

    def centro(self, g, nome):
        bx, by, bw, bh = g["botoes"][nome]
        ox, oy = self.jan.origem(g["xid"])
        return ox + g["transform"][0] + bx + bw / 2, oy + g["transform"][1] + by + bh / 2

    def barra_grav(self, app, tempo=10):
        arq = app.geom_arq + ".grav"

        def le():
            try:
                with open(arq) as f:
                    d = json.load(f)
            except (OSError, ValueError):
                return None
            if d.get("xid") and "parar" in d.get("botoes", {}):
                return d

        return x.espera(le, tempo, 0.15, "barra flutuante de gravacao")

    def espera_arquivo_gravado(self, app, ext, tempo=15):
        def achou():
            if os.path.isdir(app.saida):
                arqs = sorted(f for f in os.listdir(app.saida) if f.endswith("." + ext))
                if arqs:
                    cam = os.path.join(app.saida, arqs[0])
                    if os.path.getsize(cam) > 0:
                        return cam

        return x.espera(achou, tempo, 0.2, "gravacao .%s salva" % ext)

    def test_gravar_regiao_mp4_com_barra_fora_da_area_e_historico(self):
        mx, my = self.m[0], self.m[1]
        app = self.instancia(geom=True)
        g = app.geometria(com_imagem=False)
        x.ativa(g["xid"])
        time.sleep(0.4)
        g = app.geometria(com_imagem=False)
        self.assertEqual(g["estado"]["formato_gravacao"], "mp4")

        with self.entrada() as ent:
            ent.clicar(*self.centro(g, "gravar"))
            gp = x.espera(lambda: (d := app.geometria(com_imagem=False))
                         and "formato_mp4" in d.get("botoes", {}) and d,
                         5, 0.1, "popover de gravacao aberto")
            ent.clicar(*self.centro(gp, "formato_mp4"))
            app.espera_janelas(len(self.jan.monitores()))
            time.sleep(0.5)
            ent.arrastar([(mx + 220, my + 160), (mx + 560, my + 380)])

            bg = self.barra_grav(app)
            self.assertEqual(bg["formato"], "MP4")
            ox, oy = self.jan.origem(bg["xid"])
            bw, bh = bg["janela"]
            area_grav = bg["area_gravada"]
            self.assertEqual(area_grav, [mx + 220, my + 160, 340, 220])
            self.assertFalse(
                intercepta((ox, oy, bw, bh), area_grav),
                "a barra de Parar (%s) nao pode ficar dentro da area gravada (%s)"
                % ((ox, oy, bw, bh), area_grav),
            )

            # espera o contador avancar pelo menos 1 segundo
            x.espera(lambda: (b := self.barra_grav(app, tempo=2)) and b["tempo"] != "00:00",
                     5, 0.2, "contador de tempo avancar")

            bg2 = self.barra_grav(app)
            ent.clicar(*self.centro(bg2, "parar"))

            arq = self.espera_arquivo_gravado(app, "mp4")
            with open(arq, "rb") as f:
                self.assertIn(b"ftyp", f.read(32))

            gf = x.espera(
                lambda: (d := app.geometria(com_imagem=False))
                and not d["estado"]["gravando"]
                and d["estado"]["historico_itens"] == 1
                and d["estado"]["historico_aberto"]
                and "hist_copiar_0" in d["botoes"] and d,
                10, 0.2, "gravacao listada no historico",
            )
            subprocess.run(["xclip", "-selection", "clipboard"], input=b"limpo", timeout=5)
            ent.clicar(*self.centro(gf, "hist_copiar_0"))
            time.sleep(0.5)
            alvos = clip("-t", "TARGETS", "-o").stdout.decode(errors="replace").split()
            self.assertIn("text/uri-list", alvos)

    def test_gravar_janela_em_gif_pela_linha_de_comando(self):
        from Xlib import X, Xutil
        d = self.jan.d
        mx, my = self.m[0], self.m[1]
        win = self.jan.raiz.create_window(
            mx + 200, my + 180, 360, 220, 0, d.screen().root_depth,
            X.InputOutput, X.CopyFromParent, background_pixel=0x22AA66, event_mask=0,
        )
        win.set_wm_name("capture-e2e-janela-grav")
        win.set_wm_class("capture-e2e", "capture-e2e")
        win.set_wm_normal_hints(flags=Xutil.USPosition | Xutil.USSize,
                                x=mx + 200, y=my + 180, width=360, height=220)
        win.map()
        d.sync()
        self.limpeza.append(lambda: (win.destroy(), d.sync()))
        x.espera(lambda: win.get_attributes().map_state == X.IsViewable, 5, msg="janela de teste visivel")
        time.sleep(0.6)
        wx, wy = self.jan.origem(win.id)
        self.jan.traz_para_cima(win.id, wx + 120, wy + 100)
        net = win.get_full_property(d.intern_atom("_NET_FRAME_EXTENTS"), X.AnyPropertyType)
        fe, fd, ft, fb = list(net.value) if net else (0, 0, 0, 0)
        esperado = [360 + fe + fd, 220 + ft + fb]

        app = self.instancia("--gravar", "--modo", "janela", "--formato", "gif", geom=True)
        app.espera_janelas(len(self.jan.monitores()))
        time.sleep(0.5)

        with self.entrada() as ent:
            ent.mover(wx + 120, wy + 100)
            time.sleep(0.25)
            ent.clicar(wx + 160, wy + 110)

            bg = self.barra_grav(app)
            self.assertEqual(bg["formato"], "GIF")
            self.assertEqual(bg["area_gravada"][2:], esperado)
            ox, oy = self.jan.origem(bg["xid"])
            bw, bh = bg["janela"]
            self.assertFalse(intercepta((ox, oy, bw, bh), bg["area_gravada"]))
            time.sleep(0.5)
            ent.clicar(*self.centro(bg, "parar"))

            arq = self.espera_arquivo_gravado(app, "gif")
            with open(arq, "rb") as f:
                self.assertEqual(f.read(6), b"GIF89a")

    def test_modo_anonimo_nao_salva_gravacao_em_capturas_nem_no_historico(self):
        app = self.instancia(geom=True, salvar=True)
        # ajusta o destino de teste para extensao .mp4
        g = app.geometria(com_imagem=False)
        x.ativa(g["xid"])
        time.sleep(0.4)
        g = app.geometria(com_imagem=False)

        with self.entrada() as ent:
            ent.clicar(*self.centro(g, "anonimo"))
            x.espera(lambda: app.geometria(com_imagem=False)["estado"]["anonimo"], 6, 0.2, "anonimo ativo")
            ent.clicar(*self.centro(g, "modo_tela"))
            time.sleep(0.2)
            ent.clicar(*self.centro(g, "gravar"))
            gp = x.espera(lambda: (d := app.geometria(com_imagem=False))
                         and "formato_mp4" in d.get("botoes", {}) and d,
                         5, 0.1, "popover de gravacao aberto")
            ent.clicar(*self.centro(gp, "formato_mp4"))

            bg = self.barra_grav(app)
            time.sleep(0.4)
            ent.clicar(*self.centro(bg, "parar"))

            gf = x.espera(
                lambda: (d := app.geometria(com_imagem=False))
                and not d["estado"]["gravando"]
                and os.path.isfile(app.salvar_arq) and d,
                10, 0.2, "gravacao anonima finalizada",
            )
            self.assertEqual(gf["estado"]["historico_itens"], 0)
            self.assertFalse(
                os.path.exists(app.saida) and os.listdir(app.saida),
                "modo anonimo nao deve gravar arquivo automatico na pasta Capturas",
            )


if __name__ == "__main__":
    unittest.main()
