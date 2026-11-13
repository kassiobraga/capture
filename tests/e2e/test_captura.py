"""Captura na tela real: sobreposicao, selecao com o mouse e arquivos gerados."""
import os
import subprocess
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

import cairo  # noqa: E402

from tests.e2e import x  # noqa: E402


def le_png(caminho):
    """Le o PNG, esperando o app terminar de grava-lo."""
    fim = time.time() + 5
    while True:
        try:
            return cairo.ImageSurface.create_from_png(caminho)
        except (cairo.Error, OSError):
            if time.time() > fim:
                raise
            time.sleep(0.15)


def alfa(img, px, py):
    img.flush()
    return img.get_data()[py * img.get_stride() + px * 4 + 3]


class Captura(x.CasoE2E):
    def setUp(self):
        super().setUp()
        self.mons = x.Janelas()
        self.limpeza.append(self.mons.fecha)
        # area de teste: o primeiro monitor, longe do cantos e da barra de modos do alto
        self.m = self.mons.monitores()[0]
        self.n_monitores = len(self.mons.monitores())

    def abre_sobreposicao(self, *args):
        app = self.instancia("--novo", *args)
        app.espera_janelas(self.n_monitores)
        time.sleep(0.6)  # deixa a janela ficar pronta para receber o mouse
        return app

    # ---- cancelar
    def test_partida_a_frio_abre_uma_sobreposicao_por_monitor_e_esc_cancela(self):
        app = self.instancia("--novo")
        wins = x.espera(lambda: len(app.do_app()) >= self.n_monitores and app.do_app(), 12, msg="sobreposicoes")
        self.assertEqual(len(wins), self.n_monitores)
        time.sleep(0.5)
        with self.entrada() as ent:
            ent.tecla("Escape")
        app.espera_fim()
        self.assertEqual(app.p.returncode, 0)
        self.assertEqual(app.do_app(), [])
        self.assertFalse(os.path.exists(app.saida) and os.listdir(app.saida), "nao devia salvar nada")

    # ---- fechar pelo gerenciador de janelas (Alt+F4)
    def fecha_pelo_gerenciador(self, wids):
        for w in wids:
            subprocess.run(["wmctrl", "-ic", hex(w)], check=False)
        time.sleep(0.5)

    def test_fechar_a_sobreposicao_pelo_gerenciador_encerra_a_partida_a_frio(self):
        app = self.abre_sobreposicao()
        self.fecha_pelo_gerenciador(app.do_app()[:1])   # fechar uma so cancela todas
        app.espera_fim()
        self.assertEqual(app.p.returncode, 0)
        self.assertEqual(app.do_app(), [])

    def test_fechar_a_sobreposicao_pelo_gerenciador_nao_trava_a_proxima_captura(self):
        png = os.path.join(self.pasta_img(), "base.png")
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 300, 200)
        s.write_to_png(png)
        app = self.instancia("--abrir", png, geom=True)
        principal = app.geometria()["xid"]
        for volta in (1, 2):
            r = app.comando("--novo")
            self.assertEqual(r.returncode, 0, r.stderr)
            wins = x.espera(lambda: [w for w in app.do_app() if w != principal]
                            if len([w for w in app.do_app() if w != principal]) >= self.n_monitores else None,
                            12, msg="sobreposicoes (volta %d)" % volta)
            time.sleep(0.5)
            self.fecha_pelo_gerenciador(wins)
            x.espera(lambda: principal in app.do_app() and len(app.do_app()) == 1, 8,
                     msg="so a janela principal depois de fechar (volta %d)" % volta)
        self.assertIsNone(app.p.poll())

    def pasta_img(self):
        import shutil
        import tempfile
        d = tempfile.mkdtemp(prefix="capture-e2e-img-")
        self.limpeza.append(lambda: shutil.rmtree(d, ignore_errors=True))
        return d

    # ---- modos
    def test_retangulo_tem_exatamente_o_tamanho_arrastado(self):
        mx, my = self.m[0], self.m[1]
        app = self.abre_sobreposicao("--modo", "ret")
        with self.entrada() as ent:
            ent.arrastar([(mx + 300, my + 250), (mx + 520, my + 400), (mx + 637, my + 483)])
        img = le_png(app.espera_saida())
        self.assertEqual((img.get_width(), img.get_height()), (337, 233))

    def test_tela_cheia_tem_o_tamanho_da_tela_x(self):
        app = self.instancia("--novo", "--modo", "tela")
        img = le_png(app.espera_saida())
        self.assertEqual((img.get_width(), img.get_height()), self.mons.tamanho_tela())

    def test_forma_livre_caixa_e_cantos_transparentes(self):
        mx, my = self.m[0], self.m[1]
        app = self.abre_sobreposicao("--modo", "livre")
        a, b, c = (mx + 500, my + 400), (mx + 800, my + 400), (mx + 500, my + 650)
        with self.entrada() as ent:
            ent.arrastar([a, b, c])
        img = le_png(app.espera_saida())
        self.assertEqual((img.get_width(), img.get_height()), (300, 250))
        self.assertEqual(alfa(img, 5, 5), 255)         # dentro do triangulo
        self.assertEqual(alfa(img, 299 - 5, 249 - 5), 0)  # canto oposto, fora
        self.assertEqual(alfa(img, 5, 200), 255)       # ao longo do cateto vertical, dentro
        self.assertEqual(alfa(img, 250, 150), 0)       # do outro lado da hipotenusa, fora

    def test_modo_janela_captura_a_janela_clicada(self):
        j = x.Janelas()
        self.limpeza.append(j.fecha)
        d = j.d
        mx, my = self.m[0], self.m[1]
        win = j.raiz.create_window(mx + 200, my + 200, 420, 260, 0, d.screen().root_depth,
                                   X.InputOutput, X.CopyFromParent, background_pixel=0x3366aa,
                                   event_mask=0)
        win.set_wm_name("capture-e2e-janela")
        win.set_wm_class("capture-e2e", "capture-e2e")
        from Xlib import Xutil
        win.set_wm_normal_hints(flags=Xutil.USPosition | Xutil.USSize, x=mx + 200, y=my + 200,
                                width=420, height=260)
        win.map()
        d.sync()
        self.limpeza.append(lambda: (win.destroy(), d.sync()))
        x.espera(lambda: win.get_attributes().map_state == X.IsViewable, 5, msg="janela de teste visivel")
        time.sleep(0.8)
        ox, oy = j.origem(win.id)
        net = win.get_full_property(d.intern_atom("_NET_FRAME_EXTENTS"), X.AnyPropertyType)
        e, dr, t, bx = list(net.value) if net else (0, 0, 0, 0)
        esperado = (420 + e + dr, 260 + t + bx)

        app = self.abre_sobreposicao("--modo", "janela")
        with self.entrada() as ent:
            ent.mover(ox + 150, oy + 120)
            time.sleep(0.3)
            ent.arrastar([(ox + 210, oy + 130), (ox + 210, oy + 130)])
        img = le_png(app.espera_saida())
        self.assertEqual((img.get_width(), img.get_height()), esperado)

    # ---- tecla Print do Cinnamon
    def test_tecla_print_abre_a_sobreposicao(self):
        try:
            cmd = subprocess.run(["gsettings", "get", "org.cinnamon.desktop.keybindings.custom-keybinding:"
                                  "/org/cinnamon/desktop/keybindings/custom-keybindings/custom0/", "command"],
                                 capture_output=True, text=True, timeout=5).stdout.strip()
            lista = subprocess.run(["gsettings", "get", "org.cinnamon.desktop.keybindings", "custom-list"],
                                   capture_output=True, text=True, timeout=5).stdout
        except Exception:
            self.skipTest("sem gsettings")
        achou = None
        for e in __import__("re").findall(r"'([^']+)'", lista):
            c = subprocess.run(["gsettings", "get", "org.cinnamon.desktop.keybindings.custom-keybinding:"
                                "/org/cinnamon/desktop/keybindings/custom-keybindings/%s/" % e, "command"],
                               capture_output=True, text=True).stdout.strip()
            if c == "'%s --novo'" % x.LANCADOR:
                achou = e
        del cmd
        if not achou:
            self.skipTest("a tecla Print nao esta vinculada a esta instalacao (./install.sh --bind-print)")
        if self.mons.da_classe("capture"):
            self.skipTest("ja existe uma janela do Capture aberta")
        self.limpeza.append(lambda: [subprocess.run(["wmctrl", "-ic", hex(w)]) for w in self.mons.da_classe("capture")])
        with self.entrada() as ent:
            ent.tecla("Print")
            wins = x.espera(lambda: len(self.mons.da_classe("capture")) >= self.n_monitores
                            and self.mons.da_classe("capture"), 12, msg="sobreposicoes do Print")
            time.sleep(0.5)
            ent.tecla("Escape")
        x.espera(lambda: not self.mons.da_classe("capture"), 8, msg="sobreposicoes fecharem")
        self.assertEqual(len(wins), self.n_monitores)


X = x.X

if __name__ == "__main__":
    unittest.main()
