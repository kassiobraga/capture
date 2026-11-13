"""Editor na tela real: ferramentas com o mouse, desfazer, corte, salvar e copiar."""
import io
import os
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

import cairo  # noqa: E402

from tests.e2e import x  # noqa: E402

BASE = (51, 128, 204)      # azul liso da imagem sintetica
LARANJA = (217, 59, 0)     # cor padrao das formas
VERMELHO = (237, 28, 36)   # cor padrao da caneta e do texto
MARCA = (133, 166, 153)    # amarelo a 40 % sobre o azul


def png_sintetico(caminho, w=600, h=400):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(s)
    cr.set_source_rgb(BASE[0] / 255, BASE[1] / 255, BASE[2] / 255)
    cr.paint()
    s.write_to_png(caminho)


def le(caminho):
    fim = time.time() + 5
    while True:
        try:
            return cairo.ImageSurface.create_from_png(caminho)
        except (cairo.Error, OSError):
            if time.time() > fim:
                raise
            time.sleep(0.15)


def rgb(img, px, py):
    img.flush()
    d = img.get_data()
    o = py * img.get_stride() + px * 4
    return d[o + 2], d[o + 1], d[o]


def perto(a, b, tol=14):
    return all(abs(p - q) <= tol for p, q in zip(a, b))


def tem_cor(img, cx, cy, cor, raio=2, tol=14):
    """Algum pixel num quadrado de lado 2*raio+1 em volta de (cx, cy) tem a cor."""
    for yy in range(cy - raio, cy + raio + 1):
        for xx in range(cx - raio, cx + raio + 1):
            if 0 <= xx < img.get_width() and 0 <= yy < img.get_height() and perto(rgb(img, xx, yy), cor, tol):
                return True
    return False


def clip(*args):
    return subprocess.run(["xclip", "-selection", "clipboard", *args], capture_output=True, timeout=5)


class Editor(x.CasoE2E):
    def setUp(self):
        super().setUp()
        self.jan = x.Janelas()
        self.limpeza.append(self.jan.fecha)
        self.pasta = tempfile.mkdtemp(prefix="capture-e2e-img-")
        self.addCleanup(lambda: __import__("shutil").rmtree(self.pasta, ignore_errors=True))
        self.png = os.path.join(self.pasta, "base.png")
        png_sintetico(self.png)

    # ---- posicoes
    def geom(self, app, espera=0.8):
        time.sleep(espera)
        return app.geometria()

    def centro(self, g, nome):
        bx, by, bw, bh = g["botoes"][nome]
        ox, oy = self.jan.origem(g["xid"])
        return ox + g["transform"][0] + bx + bw / 2, oy + g["transform"][1] + by + bh / 2

    def tela(self, g, ix, iy):
        """Ponto da imagem (ix, iy) -> coordenadas da tela."""
        e = g["editor"]
        ox, oy = self.jan.origem(g["xid"])
        return (ox + g["transform"][0] + e["caixa"][0] + e["ox"] + ix * e["zoom"],
                oy + g["transform"][1] + e["caixa"][1] + e["oy"] + iy * e["zoom"])

    def desenha(self, ent, g, pts):
        ent.arrastar([self.tela(g, *p) for p in pts], passo=6)

    def abre(self, **kw):
        app = self.instancia("--abrir", self.png, geom=True, salvar=True)
        g = app.geometria()
        x.ativa(g["xid"])
        return app, self.geom(app, 0.5)

    def salva(self, app, ent):
        if os.path.exists(app.salvar_arq):
            os.unlink(app.salvar_arq)
        ent.tecla("s", "Control_L")
        x.espera(lambda: os.path.exists(app.salvar_arq), 6, msg="arquivo salvo (Ctrl+S)")
        return le(app.salvar_arq)

    def itens(self, app):
        time.sleep(0.8)
        return app.geometria()["editor"]["itens"]

    # ---- testes
    def test_abrir_mostra_a_imagem_no_editor(self):
        app, g = self.abre()
        self.assertEqual(g["editor"]["imagem"], [600, 400])
        self.assertTrue({"caneta", "marca", "borracha", "texto", "cortar", "desfazer", "refazer"} <= set(g["botoes"]))
        classes = self.jan.da_classe("capture")
        self.assertIn(g["xid"], classes)
        self.assertEqual(g["estado"]["tela"], "editor")
        self.assertTrue(g["estado"]["dock"])
        self.assertEqual(g["estado"]["chip"], "600 × 400 px")
        # o dock flutuante nao cobre a borda de baixo da imagem
        e = g["editor"]
        base_img = e["caixa"][1] + e["oy"] + 400 * e["zoom"]
        topo_dock = g["botoes"]["caneta"][1]
        self.assertLess(base_img, topo_dock)

    def test_ferramentas_desfazer_borracha_corte_salvar_e_copiar(self):
        app, g = self.abre()
        with self.entrada() as ent:
            # marca-texto e caneta: botoes da barra, clicados com o mouse
            ent.clicar(*self.centro(g, "marca"))
            self.desenha(ent, g, [(50, 50), (250, 50)])
            ent.clicar(*self.centro(g, "caneta"))
            self.desenha(ent, g, [(100, 150), (100, 250)])
            # formas e texto: atalhos de teclado
            ent.tecla("r")
            self.desenha(ent, g, [(300, 100), (450, 200)])
            ent.tecla("o")
            self.desenha(ent, g, [(300, 230), (450, 330)])
            ent.tecla("a")
            self.desenha(ent, g, [(60, 330), (230, 330)])
            ent.tecla("t")
            ent.clicar(*self.tela(g, 60, 360))
            time.sleep(0.5)
            ent.digitar("ok")
            ent.tecla("Return")
            self.assertEqual(self.itens(app), 6)

            # desfazer / refazer pelos botoes e pelo teclado
            ent.clicar(*self.centro(g, "desfazer"))
            self.assertEqual(self.itens(app), 5)
            ent.clicar(*self.centro(g, "refazer"))
            self.assertEqual(self.itens(app), 6)
            ent.tecla("z", "Control_L")
            self.assertEqual(self.itens(app), 5)
            ent.tecla("y", "Control_L")
            self.assertEqual(self.itens(app), 6)

            # imagem exportada
            img = self.salva(app, ent)
            self.assertEqual((img.get_width(), img.get_height()), (600, 400))
            self.assertTrue(perto(rgb(img, 5, 5), BASE), "fundo intacto")
            # dock, chip de tamanho e avisos sao so da interface: nao aparecem na imagem exportada
            for ponto in ((10, 392), (590, 392), (300, 395), (590, 5), (300, 5)):
                self.assertTrue(perto(rgb(img, *ponto), BASE), "fora das marcacoes: %s" % (ponto,))
            self.assertTrue(perto(rgb(img, 150, 50), MARCA), "marca-texto semitransparente sobre o azul")
            self.assertTrue(perto(rgb(img, 150, 100), BASE), "longe da marca, fundo")
            self.assertTrue(tem_cor(img, 100, 200, VERMELHO), "caneta")
            self.assertTrue(perto(rgb(img, 140, 200), BASE))
            self.assertTrue(tem_cor(img, 375, 100, LARANJA), "lado de cima do retangulo")
            self.assertTrue(tem_cor(img, 300, 150, LARANJA), "lado esquerdo do retangulo")
            self.assertTrue(perto(rgb(img, 375, 150), BASE), "miolo do retangulo vazio")
            self.assertTrue(tem_cor(img, 450, 280, LARANJA), "extremo da elipse")
            self.assertTrue(perto(rgb(img, 375, 280), BASE), "miolo da elipse vazio")
            self.assertTrue(tem_cor(img, 145, 330, LARANJA), "haste da seta")
            self.assertTrue(tem_cor(img, 223, 334, LARANJA, 3) or tem_cor(img, 223, 326, LARANJA, 3),
                            "ponta da seta")
            self.assertTrue(perto(rgb(img, 145, 350), BASE), "longe da seta")
            vermelhos = sum(1 for yy in range(355, 400) for xx in range(55, 140) if perto(rgb(img, xx, yy), VERMELHO, 20))
            self.assertGreater(vermelhos, 30, "texto")

            # borracha: o miolo do retangulo nao apaga; o lado apaga; desfazer traz de volta
            ent.tecla("e")
            ent.clicar(*self.tela(g, 375, 150))
            self.assertEqual(self.itens(app), 6)
            ent.clicar(*self.tela(g, 375, 100))
            self.assertEqual(self.itens(app), 5)
            ent.tecla("z", "Control_L")
            self.assertEqual(self.itens(app), 6)

            # copiar
            ent.tecla("c", "Control_L")
            time.sleep(0.6)
            alvos = clip("-t", "TARGETS", "-o").stdout.decode(errors="replace").split()
            self.assertIn("image/png", alvos)
            copiada = cairo.ImageSurface.create_from_png(io.BytesIO(clip("-t", "image/png", "-o").stdout))
            self.assertEqual((copiada.get_width(), copiada.get_height()), (600, 400))
            self.assertTrue(tem_cor(copiada, 450, 280, LARANJA), "a copia leva as marcacoes")

            # cortar: aplica as marcacoes na imagem nova; desfazer volta ao tamanho original
            ent.tecla("x")
            self.desenha(ent, g, [(20, 20), (520, 360)])
            time.sleep(0.8)
            g2 = app.geometria()
            self.assertEqual(g2["editor"]["imagem"], [500, 340])
            self.assertEqual(g2["editor"]["itens"], 0)
            img2 = self.salva(app, ent)
            self.assertEqual((img2.get_width(), img2.get_height()), (500, 340))
            self.assertTrue(tem_cor(img2, 450 - 20, 280 - 20, LARANJA), "elipse deslocada pelo corte")
            self.assertTrue(perto(rgb(img2, 5, 5), BASE))
            ent.tecla("z", "Control_L")
            time.sleep(0.8)
            self.assertEqual(app.geometria()["editor"]["imagem"], [600, 400])
            self.assertEqual(app.geometria()["editor"]["itens"], 6)

    def test_aviso_de_copiar_nao_cobre_o_dock(self):
        """O toast fica no alto: logo depois de copiar, o desfazer do dock ainda responde ao clique."""
        app, g = self.abre()
        with self.entrada() as ent:
            ent.tecla("r")
            self.desenha(ent, g, [(300, 100), (450, 200)])
            self.assertEqual(self.itens(app), 1, app.geometria()["editor"]["tipos"])
            ent.tecla("c", "Control_L")       # mostra o aviso "Copiado para a area de transferencia"
            time.sleep(1.2)                   # o aviso ja esta inteiro na tela
            ent.clicar(*self.centro(g, "desfazer"))
            self.assertEqual(self.itens(app), 0, app.geometria()["editor"]["tipos"])
            ent.clicar(*self.centro(g, "refazer"))   # com o aviso ainda na tela
            self.assertEqual(self.itens(app), 1, app.geometria()["editor"]["tipos"])

    def test_aviso_pode_ser_fechado_no_x_e_a_faixa_so_recebe_cliques_com_aviso(self):
        app, g = self.abre()
        self.assertFalse(g["estado"]["faixa_alvo"], "sem aviso a faixa nao pode capturar cliques")
        with self.entrada() as ent:
            ent.tecla("c", "Control_L")
            time.sleep(0.9)
            g2 = app.geometria()
            self.assertEqual(g2["estado"]["avisos"], 1)
            self.assertTrue(g2["estado"]["faixa_alvo"])
            fx, fy, fw, fh = g2["estado"]["faixa_avisos"]
            ox, oy = self.jan.origem(g2["xid"])
            # o "x" do aviso fica ~146 px a direita do centro da faixa, a ~41 px do topo dela
            ent.clicar(ox + g2["transform"][0] + fx + fw / 2 + 146, oy + g2["transform"][1] + fy + 41)
            time.sleep(0.9)    # antes dos 3 s do tempo normal do aviso
            g3 = app.geometria()
            self.assertEqual(g3["estado"]["avisos"], 0)
            self.assertFalse(g3["estado"]["faixa_alvo"])

    def test_janela_acompanha_o_tamanho_de_uma_nova_imagem(self):
        app, g = self.abre()
        pequena = tuple(g["janela"])
        grande = os.path.join(self.pasta, "grande.png")
        png_sintetico(grande, 1000, 700)
        r = app.comando("--abrir", grande)
        self.assertEqual(r.returncode, 0, r.stderr)
        x.espera(lambda: app.geometria()["editor"]["imagem"] == [1000, 700], 8, 0.3, "nova imagem")
        time.sleep(1.2)
        g2 = app.geometria()
        self.assertGreater(g2["janela"][0], pequena[0])
        self.assertGreater(g2["janela"][1], pequena[1])
        lim = self.jan.monitores()[0]
        self.assertLessEqual(g2["janela"][0], lim[2])
        self.assertLessEqual(g2["janela"][1], lim[3])

    def test_abrir_caminho_relativo_usa_o_diretorio_de_quem_chamou(self):
        app, g = self.abre()
        outra = os.path.join(self.pasta, "rel.png")
        png_sintetico(outra, 300, 200)
        r = subprocess.run([x.LANCADOR, "--abrir", "rel.png"], env=app.env, cwd=self.pasta,
                           capture_output=True, text=True, timeout=15)
        self.assertEqual(r.returncode, 0, r.stderr)
        x.espera(lambda: app.geometria()["editor"]["imagem"] == [300, 200], 8, 0.3, "imagem relativa")


if __name__ == "__main__":
    unittest.main()
