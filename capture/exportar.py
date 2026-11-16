"""Gravacao das capturas em PNG, JPEG ou PDF, e PDF com varias imagens (uma por pagina)."""
import os

import cairo
import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf  # noqa: E402

# Extensao -> nome do formato. A extensao do arquivo escolhido decide o formato.
FORMATOS = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".pdf": "PDF"}
EXTENSAO = {"PNG": ".png", "JPEG": ".jpg", "PDF": ".pdf"}
PT_POR_PX = 0.75  # 96 px por polegada: uma captura de 1280 px vira 960 pt (33,9 cm) no PDF
QUALIDADE_JPEG = 92


def formato(caminho):
    """'PNG', 'JPEG' ou 'PDF' conforme a extensao; None se ela nao for conhecida."""
    return FORMATOS.get(os.path.splitext(caminho)[1].lower())


def com_extensao(caminho, fmt="PNG"):
    """O caminho, com a extensao de `fmt` acrescentada se ele nao tiver uma conhecida."""
    return caminho if formato(caminho) else caminho + EXTENSAO[fmt]


def salvar(img, caminho):
    """Grava a imagem (cairo.ImageSurface) no formato indicado pela extensao (PNG se nenhuma)."""
    fmt = formato(caminho) or "PNG"
    if fmt == "JPEG":
        _jpeg(img, caminho)
    elif fmt == "PDF":
        pdf([img], caminho)
    else:
        img.write_to_png(caminho)


def _sem_transparencia(img):
    """Copia sobre fundo branco (JPEG nao tem transparencia)."""
    out = cairo.ImageSurface(cairo.FORMAT_RGB24, img.get_width(), img.get_height())
    cr = cairo.Context(out)
    cr.set_source_rgb(1, 1, 1)
    cr.paint()
    cr.set_source_surface(img, 0, 0)
    cr.paint()
    return out


def _jpeg(img, caminho, qualidade=QUALIDADE_JPEG):
    import io
    dados = io.BytesIO()
    _sem_transparencia(img).write_to_png(dados)
    carga = GdkPixbuf.PixbufLoader.new_with_type("png")
    carga.write(dados.getvalue())
    carga.close()
    carga.get_pixbuf().savev(caminho, "jpeg", ["quality"], [str(qualidade)])


def pdf(imagens, caminho):
    """Um PDF com uma pagina por imagem, cada pagina do tamanho da sua imagem."""
    if not imagens:
        raise ValueError("nenhuma imagem para o PDF")
    w0, h0 = imagens[0].get_width(), imagens[0].get_height()
    sup = cairo.PDFSurface(caminho, w0 * PT_POR_PX, h0 * PT_POR_PX)
    cr = cairo.Context(sup)
    for img in imagens:
        sup.set_size(img.get_width() * PT_POR_PX, img.get_height() * PT_POR_PX)
        cr.save()
        cr.scale(PT_POR_PX, PT_POR_PX)
        cr.set_source_surface(img, 0, 0)
        cr.paint()
        cr.restore()
        cr.show_page()
    sup.finish()
