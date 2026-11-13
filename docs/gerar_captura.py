#!/usr/bin/env python3
"""Gera docs/captura-editor.png: a janela do editor com uma imagem sintetica e algumas marcacoes.

Usa o Capture instalado e os auxiliares dos testes e2e (mouse simulado). So a janela do
aplicativo e capturada (maim -i), nunca a tela inteira. Uso:  python3 docs/gerar_captura.py
"""
import os
import subprocess
import sys
import tempfile
import time

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, RAIZ)

import cairo  # noqa: E402

from tests.e2e import x  # noqa: E402


def imagem_base(caminho, w=640, h=400):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(s)
    cr.set_source_rgb(0.95, 0.96, 0.98)
    cr.paint()
    cr.set_source_rgb(0.20, 0.30, 0.45)           # barra de titulo de uma janela ficticia
    cr.rectangle(0, 0, w, 44)
    cr.fill()
    for i, (cx, cor) in enumerate([(30, (0.9, 0.4, 0.4)), (58, (0.95, 0.75, 0.3)), (86, (0.4, 0.8, 0.5))]):
        cr.set_source_rgb(*cor)
        cr.arc(cx, 22, 8, 0, 6.3)
        cr.fill()
    for i in range(6):                            # linhas de texto ficticias
        cr.set_source_rgb(0.72, 0.75, 0.80)
        cr.rectangle(40, 90 + i * 28, 300 + (i % 3) * 60, 12)
        cr.fill()
    cr.set_source_rgb(0.25, 0.55, 0.85)           # um botao e um grafico ficticios
    cr.rectangle(440, 90, 150, 44)
    cr.fill()
    for i, alt in enumerate((60, 110, 80, 150, 120)):
        cr.set_source_rgb(0.55, 0.62, 0.72)
        cr.rectangle(420 + i * 36, 360 - alt, 24, alt)
        cr.fill()
    s.write_to_png(caminho)


def main():
    if x.PULAR:
        sys.exit("nao da para gerar: " + x.PULAR)
    pasta = tempfile.mkdtemp(prefix="capture-doc-")
    base = os.path.join(pasta, "base.png")
    imagem_base(base)
    app = x.Instancia("--abrir", base, geom=True)
    try:
        g = app.geometria()
        x.ativa(g["xid"])
        time.sleep(0.8)
        g = app.geometria()
        jan = x.Janelas()

        def tela(ix, iy):
            e = g["editor"]
            ox, oy = jan.origem(g["xid"])
            return (ox + g["transform"][0] + e["caixa"][0] + e["ox"] + ix * e["zoom"],
                    oy + g["transform"][1] + e["caixa"][1] + e["oy"] + iy * e["zoom"])

        def centro(nome):
            bx, by, bw, bh = g["botoes"][nome]
            ox, oy = jan.origem(g["xid"])
            return ox + g["transform"][0] + bx + bw / 2, oy + g["transform"][1] + by + bh / 2

        with x.Entrada() as ent:
            ent.clicar(*centro("marca"))
            ent.arrastar([tela(40, 98), tela(320, 98)])
            ent.tecla("r")
            ent.arrastar([tela(425, 80), tela(605, 144)])
            ent.tecla("a")
            ent.arrastar([tela(300, 240), tela(430, 128)])
            ent.tecla("t")
            ent.clicar(*tela(250, 250))
            time.sleep(0.5)
            ent.digitar("clique aqui")
            ent.tecla("Return")
            ent.tecla("p")
            ent.arrastar([tela(40, 330), tela(120, 350), tela(200, 325), tela(280, 350)])
            ent.mover(*ent.origem)   # tira o ponteiro de cima da janela
            time.sleep(0.8)
            destino = os.path.join(RAIZ, "docs", "captura-editor.png")
            subprocess.run(["maim", "-u", "-i", str(g["xid"]), destino], check=True)
        jan.fecha()
        print("gravado", destino)
    finally:
        app.encerra()
        subprocess.run(["rm", "-rf", pasta])


if __name__ == "__main__":
    main()
