"""Consultas ao servidor X11 (janelas visiveis)."""
import re
import subprocess


def _executa(args):
    return subprocess.run(args, capture_output=True, text=True, timeout=2).stdout


def listar_janelas(executa=_executa):
    """Retangulos (x, y, w, h) das janelas visiveis, de baixo para cima.

    `executa(args)` devolve a saida de texto do comando; trocavel nos testes.
    """
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

        x, y = num("Absolute upper-left X:"), num("Absolute upper-left Y:")
        w, h = num("Width:"), num("Height:")
        m = re.search(r"_NET_WM_DESKTOP\(CARDINAL\) = (\d+)", prop)
        if m and atual is not None and int(m.group(1)) not in (atual, 0xFFFFFFFF):
            continue
        g = re.search(r"_GTK_FRAME_EXTENTS\(CARDINAL\) = (\d+), (\d+), (\d+), (\d+)", prop)
        n = re.search(r"_NET_FRAME_EXTENTS\(CARDINAL\) = (\d+), (\d+), (\d+), (\d+)", prop)
        if g:  # sombra do cliente: encolhe
            l, r, t, b = map(int, g.groups())
            x, y, w, h = x + l, y + t, w - l - r, h - t - b
        elif n:  # moldura do gerenciador: inclui
            l, r, t, b = map(int, n.groups())
            x, y, w, h = x - l, y - t, w + l + r, h + t + b
        if w > 20 and h > 20:
            res.append((x, y, w, h))
    return res
