"""Consultas ao servidor X11: foto da tela e janelas visiveis.

Usa python-xlib quando ele esta disponivel (e o caso do pacote Flatpak, que nao
tem maim, xprop nem xwininfo). Sem ele, cai nos programas externos.
"""
import re
import subprocess

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


# ---------------------------------------------------------------- foto da tela

def foto_da_tela():
    """cairo.ImageSurface (RGB24) com todos os monitores, sem o cursor.

    Levanta excecao se nao for possivel (sem python-xlib, sem display, formato de
    pixel inesperado); quem chama pode entao tentar o maim.
    """
    import cairo
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
        img = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h)
        destino, passo = img.get_data(), img.get_stride()
        # Em faixas: uma resposta do X tem tamanho limitado e faixas aliviam a memoria.
        faixa = max(1, (8 << 20) // (w * 4))
        for y in range(0, h, faixa):
            fh = min(faixa, h - y)
            dados = raiz.get_image(0, y, w, fh, X.ZPixmap, 0xFFFFFFFF).data
            if passo == w * 4:
                destino[y * passo:(y + fh) * passo] = dados
            else:
                for i in range(fh):
                    destino[(y + i) * passo:(y + i) * passo + w * 4] = dados[i * w * 4:(i + 1) * w * 4]
        img.mark_dirty()
        return img
    finally:
        d.close()


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
