"""Consultas ao servidor X11: foto da tela e janelas visiveis.

Usa python-xlib quando ele esta disponivel (e o caso do pacote Flatpak, que nao
tem maim, xprop nem xwininfo). Sem ele, cai nos programas externos.
"""
import ctypes
import ctypes.util
import re
import subprocess
import sys

try:
    from Xlib import X, display as xdisplay, xauth
except ImportError:  # sem python-xlib: so os programas externos
    X = None

FAMILIA_QUALQUER = 0xFFFF  # FamilyWild do Xauthority


def _abre():
    """Conexao com o display X. Aceita cookies 'FamilyWild', que o python-xlib ignora."""
    try:
        return xdisplay.Display()
    except Exception:
        original = xauth.Xauthority.get_best_auth

        def com_coringa(self, family, address, dispno, types=(b"MIT-MAGIC-COOKIE-1",)):
            try:
                return original(self, family, address, dispno, types)
            except Exception:
                for efam, _eaddr, enum, ename, edata in self.entries:
                    if efam == FAMILIA_QUALQUER and enum in (b"", dispno) and ename in types:
                        return ename, edata
                raise
        xauth.Xauthority.get_best_auth = com_coringa
        try:
            return xdisplay.Display()
        finally:
            xauth.Xauthority.get_best_auth = original


def tem_xlib():
    return X is not None


def tem_captura():
    """Ha como fotografar a tela sem o maim (libX11 ou python-xlib)?"""
    if X is not None:
        return True
    try:
        _libx11()
        return True
    except OSError:
        return False


# ---------------------------------------------------------------- foto da tela

class _XImage(ctypes.Structure):
    _fields_ = [("width", ctypes.c_int), ("height", ctypes.c_int), ("xoffset", ctypes.c_int),
                ("format", ctypes.c_int), ("data", ctypes.c_void_p), ("byte_order", ctypes.c_int),
                ("bitmap_unit", ctypes.c_int), ("bitmap_bit_order", ctypes.c_int),
                ("bitmap_pad", ctypes.c_int), ("depth", ctypes.c_int), ("bytes_per_line", ctypes.c_int),
                ("bits_per_pixel", ctypes.c_int), ("red_mask", ctypes.c_ulong),
                ("green_mask", ctypes.c_ulong), ("blue_mask", ctypes.c_ulong),
                ("obdata", ctypes.c_void_p), ("f", ctypes.c_void_p * 6)]


_erro_x = []
_TRATA_ERRO = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)(
    lambda _d, _e: _erro_x.append(1) or 0)  # sem isto, um erro do X encerraria o processo


def _libx11():
    nome = ctypes.util.find_library("X11") or "libX11.so.6"
    x = ctypes.CDLL(nome)
    x.XOpenDisplay.restype = ctypes.c_void_p
    x.XOpenDisplay.argtypes = [ctypes.c_char_p]
    for f in ("XDefaultScreen", "XCloseDisplay", "XSync"):
        getattr(x, f).argtypes = [ctypes.c_void_p] + ([ctypes.c_int] if f == "XSync" else [])
    x.XRootWindow.restype = ctypes.c_ulong
    x.XRootWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    x.XDisplayWidth.argtypes = x.XDisplayHeight.argtypes = [ctypes.c_void_p, ctypes.c_int]
    x.XGetImage.restype = ctypes.POINTER(_XImage)
    x.XGetImage.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_uint,
                            ctypes.c_uint, ctypes.c_ulong, ctypes.c_int]
    x.XSetErrorHandler.restype = ctypes.c_void_p
    x.XSetErrorHandler.argtypes = [ctypes.c_void_p]
    return x


def _para_cairo(dados, w, h, passo_origem):
    import cairo
    img = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h)
    destino, passo = img.get_data(), img.get_stride()
    if passo == passo_origem:
        destino[:h * passo] = dados[:h * passo]
    else:
        n = w * 4
        for i in range(h):
            destino[i * passo:i * passo + n] = dados[i * passo_origem:i * passo_origem + n]
    img.mark_dirty()
    return img


def _foto_libx11():
    """Tela inteira num unico XGetImage, pela libX11 (rapido; a mesma que o GTK usa)."""
    x = _libx11()
    d = x.XOpenDisplay(None)
    if not d:
        raise RuntimeError("nao foi possivel abrir o display X")
    anterior = x.XSetErrorHandler(ctypes.cast(_TRATA_ERRO, ctypes.c_void_p))
    try:
        tela = x.XDefaultScreen(d)
        w, h = x.XDisplayWidth(d, tela), x.XDisplayHeight(d, tela)
        del _erro_x[:]
        im = x.XGetImage(d, x.XRootWindow(d, tela), 0, 0, w, h, ctypes.c_ulong(-1).value, 2)  # ZPixmap
        x.XSync(d, 0)
        if not im or _erro_x:
            raise RuntimeError("o servidor X recusou a captura")
        try:
            r = im.contents
            if r.bits_per_pixel != 32 or r.byte_order != 0 or r.depth not in (24, 32):
                raise RuntimeError("formato de pixel nao suportado (%d bpp)" % r.bits_per_pixel)
            dados = ctypes.string_at(r.data, r.bytes_per_line * h)
            return _para_cairo(dados, w, h, r.bytes_per_line)
        finally:
            ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p)(im.contents.f[1])(im)  # destroy_image
    finally:
        x.XSetErrorHandler(anterior)
        x.XCloseDisplay(d)


def _foto_xlib():
    """Mesma coisa pelo python-xlib: mais lento em telas grandes, usado se a libX11 falhar."""
    if X is None:
        raise RuntimeError("python-xlib nao esta instalado")
    d = _abre()
    try:
        raiz = d.screen().root
        geo = raiz.get_geometry()
        w, h = geo.width, geo.height
        bpp = {f.depth: f.bits_per_pixel for f in d.display.info.pixmap_formats}.get(geo.depth)
        if geo.depth not in (24, 32) or bpp != 32 or d.display.info.image_byte_order != X.LSBFirst:
            raise RuntimeError("formato de pixel nao suportado (profundidade %d)" % geo.depth)
        # Um unico pedido: o servidor copia a tela de uma vez (em faixas, cada faixa saia de
        # um instante diferente e um redesenho no meio deixava listras na captura).
        dados = raiz.get_image(0, 0, w, h, X.ZPixmap, 0xFFFFFFFF).data
        return _para_cairo(dados, w, h, w * 4)
    finally:
        d.close()


def foto_da_tela():
    """cairo.ImageSurface (RGB24) com todos os monitores, sem o cursor.

    Levanta excecao se nao for possivel; quem chama pode entao tentar o maim.
    """
    try:
        return _foto_libx11()
    except Exception as e:
        if X is None:
            raise
        print("libX11 nao capturou a tela (%s); usando python-xlib" % e, file=sys.stderr)
        return _foto_xlib()


# ---------------------------------------------------------------- janelas

def _ajusta(x, y, w, h, gtk, net):
    """Desconta a sombra do cliente (GTK) ou soma a moldura do gerenciador."""
    if gtk:  # sombra do cliente: encolhe
        l, r, t, b = gtk
        return x + l, y + t, w - l - r, h - t - b
    if net:  # moldura do gerenciador: inclui
        l, r, t, b = net
        return x - l, y - t, w + l + r, h + t + b
    return x, y, w, h


def _executa(args):
    return subprocess.run(args, capture_output=True, text=True, timeout=2).stdout


def listar_janelas(executa=None):
    """Retangulos (x, y, w, h) das janelas visiveis, de baixo para cima.

    Sem `executa`, usa python-xlib se houver. `executa(args)` devolve a saida de
    texto de xprop/xwininfo; e o caminho sem python-xlib, trocavel nos testes.
    """
    if executa is None and X is not None:
        try:
            return _listar_xlib()
        except Exception:
            pass
    return _listar_comandos(executa or _executa)


def _listar_xlib():
    d = _abre()
    try:
        raiz = d.screen().root
        atomo = d.intern_atom

        def prop(jan, nome):
            p = jan.get_full_property(atomo(nome), X.AnyPropertyType)
            return list(p.value) if p is not None else None

        ids = prop(raiz, "_NET_CLIENT_LIST_STACKING") or []
        atual = (prop(raiz, "_NET_CURRENT_DESKTOP") or [None])[0]
        escondida = atomo("_NET_WM_STATE_HIDDEN")
        res = []
        for wid in ids:
            try:
                jan = d.create_resource_object("window", wid)
                if jan.get_attributes().map_state != X.IsViewable:
                    continue
                if escondida in (prop(jan, "_NET_WM_STATE") or []):
                    continue
                mesa = prop(jan, "_NET_WM_DESKTOP")
                if mesa and atual is not None and mesa[0] not in (atual, 0xFFFFFFFF):
                    continue
                geo = jan.get_geometry()
                pos = raiz.translate_coords(jan, 0, 0)
                gtk = prop(jan, "_GTK_FRAME_EXTENTS")
                net = prop(jan, "_NET_FRAME_EXTENTS")
            except Exception:  # a janela pode sumir no meio da consulta
                continue
            x, y, w, h = _ajusta(pos.x, pos.y, geo.width, geo.height,
                                 gtk if gtk and len(gtk) == 4 else None,
                                 net if net and len(net) == 4 else None)
            if w > 20 and h > 20:
                res.append((x, y, w, h))
        return res
    finally:
        d.close()


def _listar_comandos(executa):
    try:
        raiz = executa(["xprop", "-root", "_NET_CLIENT_LIST_STACKING", "_NET_CURRENT_DESKTOP"])
    except Exception:
        return []
    ids, atual = [], None
    for ln in raiz.splitlines():
        if ln.startswith("_NET_CLIENT_LIST_STACKING"):
            ids = re.findall(r"0x[0-9a-fA-F]+", ln)
        elif ln.startswith("_NET_CURRENT_DESKTOP"):
            m = re.search(r"= (\d+)", ln)
            atual = int(m.group(1)) if m else None
    res = []
    for wid in ids:
        try:
            info = executa(["xwininfo", "-id", wid])
            prop = executa(["xprop", "-id", wid, "_NET_WM_DESKTOP", "_GTK_FRAME_EXTENTS",
                            "_NET_FRAME_EXTENTS", "_NET_WM_STATE"])
        except Exception:
            continue
        if "IsViewable" not in info or "_NET_WM_STATE_HIDDEN" in prop:
            continue

        def num(rot, txt=info):
            m = re.search(rot + r"\s*(-?\d+)", txt)
            return int(m.group(1)) if m else 0

        m = re.search(r"_NET_WM_DESKTOP\(CARDINAL\) = (\d+)", prop)
        if m and atual is not None and int(m.group(1)) not in (atual, 0xFFFFFFFF):
            continue
        g = re.search(r"_GTK_FRAME_EXTENTS\(CARDINAL\) = (\d+), (\d+), (\d+), (\d+)", prop)
        n = re.search(r"_NET_FRAME_EXTENTS\(CARDINAL\) = (\d+), (\d+), (\d+), (\d+)", prop)
        x, y, w, h = _ajusta(num("Absolute upper-left X:"), num("Absolute upper-left Y:"),
                             num("Width:"), num("Height:"),
                             tuple(map(int, g.groups())) if g else None,
                             tuple(map(int, n.groups())) if n else None)
        if w > 20 and h > 20:
            res.append((x, y, w, h))
    return res
