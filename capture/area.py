"""Area de transferencia X11 em segundo plano, no lugar do xclip.

Uso: `python3 -m capture.area` com o PNG na entrada padrao. O processo vira dono
da selecao CLIPBOARD, escreve "ok" na saida padrao e continua servindo a imagem
(inclusive em pedacos, pelo protocolo INCR) ate outro programa copiar algo.
Assim a imagem continua colavel depois que a janela do Capture fecha.
"""
import os
import select
import subprocess
import sys

TIPO = "image/png"
PEDACO = 1 << 16  # bytes por pedaco no INCR (bem abaixo do limite de uma requisicao)


def servir(dados, avisar=None):
    from Xlib import X, Xatom
    from Xlib.protocol import event

    from .x11 import _abre

    d = _abre()
    a = d.intern_atom
    CLIP, TARGETS, TIMESTAMP, INCR = a("CLIPBOARD"), a("TARGETS"), a("TIMESTAMP"), a("INCR")
    PNG = a(TIPO)
    raiz = d.screen().root
    jan = raiz.create_window(0, 0, 1, 1, 0, X.CopyFromParent, event_mask=X.PropertyChangeMask)
    # Carimbo de tempo real (o ICCCM pede): muda uma propriedade e espera o evento.
    jan.change_property(Xatom.WM_NAME, Xatom.STRING, 8, b"capture-area")
    d.flush()
    while True:
        ev = d.next_event()
        if ev.type == X.PropertyNotify:
            hora = ev.time
            break
    jan.set_selection_owner(CLIP, hora)
    d.flush()
    if d.get_selection_owner(CLIP) != jan:
        raise RuntimeError("nao foi possivel ficar com a area de transferencia")
    if avisar:
        avisar()

    envios = {}  # (janela, propriedade) -> posicao ja enviada, nas transferencias INCR

    def responde(ev, prop):
        nota = event.SelectionNotify(time=ev.time, requestor=ev.requestor, selection=ev.selection,
                                     target=ev.target, property=prop)
        ev.requestor.send_event(nota, event_mask=0)

    while True:
        ev = d.next_event()
        if ev.type == X.SelectionClear and ev.atom == CLIP:
            break
        if ev.type == X.SelectionRequest:
            prop = ev.property or ev.target  # clientes antigos mandam None
            req = ev.requestor
            try:
                if ev.target == TARGETS:
                    req.change_property(prop, Xatom.ATOM, 32, [TARGETS, TIMESTAMP, PNG])
                elif ev.target == TIMESTAMP:
                    req.change_property(prop, Xatom.INTEGER, 32, [hora])
                elif ev.target == PNG and len(dados) <= PEDACO:
                    req.change_property(prop, PNG, 8, dados)
                elif ev.target == PNG:
                    req.change_attributes(event_mask=X.PropertyChangeMask)
                    req.change_property(prop, INCR, 32, [len(dados)])
                    envios[(req.id, prop)] = (req, 0)
                else:  # outros alvos (MULTIPLE inclusive): recusa
                    prop = X.NONE
                responde(ev, prop)
            except Exception:
                envios.pop((req.id, prop), None)
            d.flush()
        elif ev.type == X.PropertyNotify and ev.state == X.PropertyDelete:
            chave = (ev.window.id, ev.atom)
            if chave not in envios:
                continue
            req, pos = envios[chave]
            parte = dados[pos:pos + PEDACO]
            try:
                req.change_property(ev.atom, PNG, 8, parte)
            except Exception:
                parte = b""
            if parte:
                envios[chave] = (req, pos + len(parte))
            else:  # pedaco vazio: fim da transferencia
                del envios[chave]
            d.flush()
    d.close()


def copiar(dados, espera=5):
    """Copia `dados` (PNG) num processo separado. True se ele assumiu a area."""
    p = subprocess.Popen([sys.executable, "-m", "capture.area"], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True,
                         env=dict(os.environ, PYTHONPATH=os.pathsep.join(
                             [os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
                             + [c for c in os.environ.get("PYTHONPATH", "").split(os.pathsep) if c])))
    try:
        p.stdin.write(dados)
        p.stdin.close()
        pronto, _, _ = select.select([p.stdout], [], [], espera)
        ok = bool(pronto) and p.stdout.readline().strip() == b"ok"
    finally:
        p.stdout.close()
    if not ok:
        p.kill()
    return ok


def principal():
    dados = sys.stdin.buffer.read()
    sys.stdin.close()

    def avisar():
        sys.stdout.write("ok\n")
        sys.stdout.flush()
        sys.stdout.close()
        os.dup2(os.open(os.devnull, os.O_WRONLY), 1)
    servir(dados, avisar)


if __name__ == "__main__":
    principal()
