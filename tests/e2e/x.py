"""Apoio dos testes e2e: entrada simulada (XTest), janelas X e a instancia do app sob teste."""
import json
import math
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

try:
    from Xlib import X, XK, display
    from Xlib.ext import xtest
except ImportError:  # sem python-xlib
    X = None

APP_ID = "io.github.kassiobraga.Capture"
LANCADOR = os.environ.get("CAPTURE_BIN") or os.path.expanduser("~/.local/bin/capture")


def motivo_para_pular():
    """Texto com o motivo, ou None se o e2e pode rodar."""
    if os.environ.get("CAPTURE_E2E") != "1":
        return "defina CAPTURE_E2E=1 para rodar os testes e2e"
    if X is None:
        return "python-xlib nao esta instalado"
    if not os.environ.get("DISPLAY"):
        return "sem display X (DISPLAY vazio)"
    try:
        d = display.Display()
    except Exception as e:
        return "nao foi possivel abrir o display: %s" % e
    try:
        if not d.has_extension("XTEST"):
            return "o servidor X nao tem a extensao XTEST"
    finally:
        d.close()
    if not os.access(LANCADOR, os.X_OK):
        return "o Capture nao esta instalado (%s); rode ./install.sh" % LANCADOR
    try:
        with open(LANCADOR) as f:
            if "# capture-launcher: " + APP_ID not in f.read():
                return "%s nao e o lancador do Capture" % LANCADOR
    except OSError:
        return "nao foi possivel ler o lancador"
    return None


PULAR = motivo_para_pular()


class InterferenciaDoMouse(Exception):
    """O ponteiro nao esta onde a entrada simulada o pos: alguem mexeu no mouse de verdade."""


class Entrada:
    """Mouse e teclado simulados. Sempre chame restaura() (ou use como gerenciador de contexto)."""

    def __init__(self):
        self.d = display.Display()
        self.raiz = self.d.screen().root
        self.origem = self.posicao()
        self.botoes = set()
        self.teclas = set()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.restaura()

    def posicao(self):
        q = self.raiz.query_pointer()
        return q.root_x, q.root_y

    def _fake(self, tipo, detalhe=0, x=0, y=0):
        xtest.fake_input(self.d, tipo, detalhe, x=x, y=y)
        self.d.sync()

    def mover(self, x, y):
        self._fake(X.MotionNotify, 0, int(round(x)), int(round(y)))

    def confere_ponteiro(self, x, y, tol=2):
        """Levanta InterferenciaDoMouse se o ponteiro nao esta em (x, y)."""
        px, py = self.posicao()
        if abs(px - round(x)) > tol or abs(py - round(y)) > tol:
            raise InterferenciaDoMouse("interferência do mouse: o ponteiro estava em (%d, %d) e devia estar em "
                                       "(%d, %d)" % (px, py, round(x), round(y)))

    def botao(self, n, baixo):
        self._fake(X.ButtonPress if baixo else X.ButtonRelease, n)
        (self.botoes.add if baixo else self.botoes.discard)(n)

    def clicar(self, x, y, pausa=0.12):
        self.mover(x, y)
        time.sleep(0.08)
        self.botao(1, True)
        time.sleep(0.05)
        self.botao(1, False)
        time.sleep(pausa)

    def arrastar(self, pontos, passo=7, pausa=0.012):
        """Pressiona em pontos[0], passa por todos (interpolando) e solta no ultimo."""
        x0, y0 = pontos[0]
        self.mover(x0, y0)
        time.sleep(0.12)
        self.botao(1, True)
        time.sleep(0.08)
        for (ax, ay), (bx, by) in zip(pontos, pontos[1:]):
            n = max(1, int(math.hypot(bx - ax, by - ay) / passo))
            for i in range(1, n + 1):
                self.mover(ax + (bx - ax) * i / n, ay + (by - ay) * i / n)
                self.confere_ponteiro(ax + (bx - ax) * i / n, ay + (by - ay) * i / n, tol=3)
                time.sleep(pausa)
            time.sleep(0.07)  # o vertice precisa ser entregue (o X junta movimentos seguidos)
        time.sleep(0.08)
        self.confere_ponteiro(*pontos[-1])
        self.botao(1, False)
        time.sleep(0.15)
        self.confere_ponteiro(*pontos[-1])

    def _kc(self, nome):
        kc = self.d.keysym_to_keycode(XK.string_to_keysym(nome))
        if not kc:
            raise ValueError("tecla desconhecida: " + nome)
        return kc

    def tecla(self, nome, *mods):
        """Aperta e solta `nome`, com os modificadores (ex.: 'Control_L') pressionados."""
        for m in mods:
            self._fake(X.KeyPress, self._kc(m))
            self.teclas.add(m)
        kc = self._kc(nome)
        self._fake(X.KeyPress, kc)
        time.sleep(0.06)
        self._fake(X.KeyRelease, kc)
        for m in reversed(mods):
            self._fake(X.KeyRelease, self._kc(m))
            self.teclas.discard(m)
        time.sleep(0.2)

    def digitar(self, texto):
        for c in texto:
            self.tecla({" ": "space"}.get(c, c))

    def restaura(self):
        if getattr(self, "_fechada", False):
            return
        self._fechada = True
        for n in sorted(self.botoes):
            self._fake(X.ButtonRelease, n)
        for m in list(self.teclas):
            self._fake(X.KeyRelease, self._kc(m))
        self.botoes.clear()
        self.teclas.clear()
        self.mover(*self.origem)
        self.d.close()


class Janelas:
    """Consultas a janelas X gerenciadas."""

    def __init__(self):
        self.d = display.Display()
        self.raiz = self.d.screen().root
        self.a_lista = self.d.intern_atom("_NET_CLIENT_LIST")
        self.a_pid = self.d.intern_atom("_NET_WM_PID")

    def todas(self):
        p = self.raiz.get_full_property(self.a_lista, X.AnyPropertyType)
        return list(p.value) if p else []

    def _pid(self, wid):
        try:
            p = self.d.create_resource_object("window", wid).get_full_property(self.a_pid, X.AnyPropertyType)
            return p.value[0] if p else None
        except Exception:
            return None

    def do_processo(self, pid):
        return [w for w in self.todas() if self._pid(w) == pid]

    def da_classe(self, classe="capture"):
        out = []
        for w in self.todas():
            try:
                c = self.d.create_resource_object("window", w).get_wm_class()
            except Exception:
                c = None
            if c and c[1] == classe:
                out.append(w)
        return out

    def origem(self, wid):
        """Canto superior esquerdo da janela X na tela."""
        w = self.d.create_resource_object("window", wid)
        r = self.raiz.translate_coords(w, 0, 0)
        return r.x, r.y

    def tamanho_tela(self):
        s = self.d.screen()
        return s.width_in_pixels, s.height_in_pixels

    def monitores(self):
        try:
            from Xlib.ext import randr
            ms = randr.get_monitors(self.raiz, is_active=True).monitors
            return [(m.x, m.y, m.width_in_pixels, m.height_in_pixels) for m in ms]
        except Exception:
            return [(0, 0) + self.tamanho_tela()]

    def fecha(self):
        if not getattr(self, "_fechada", False):
            self._fechada = True
            self.d.close()


def espera(cond, tempo=10, intervalo=0.1, msg="condicao"):
    fim = time.time() + tempo
    while time.time() < fim:
        v = cond()
        if v:
            return v
        time.sleep(intervalo)
    raise AssertionError("tempo esgotado esperando: " + msg)


def ativa(wid):
    subprocess.run(["wmctrl", "-ia", hex(wid)], check=False)
    time.sleep(0.4)


class Instancia:
    """Uma execucao do Capture instalado, com id de aplicativo proprio e saida em pasta temporaria."""

    def __init__(self, *args, geom=False, salvar=False):
        self.tmp = tempfile.mkdtemp(prefix="capture-e2e-")
        self.saida = os.path.join(self.tmp, "capturas")
        self.geom_arq = os.path.join(self.tmp, "geom.json") if geom else None
        self.salvar_arq = os.path.join(self.tmp, "salvo.png") if salvar else None
        env = dict(os.environ)
        self.env = env
        env["CAPTURE_APP_ID"] = "io.github.kassiobraga.CaptureTeste" + uuid.uuid4().hex[:10]
        env["CAPTURE_DIR"] = self.saida
        if geom:
            env["CAPTURE_TEST_GEOM"] = self.geom_arq
        if salvar:
            env["CAPTURE_TEST_SALVAR"] = self.salvar_arq
        self.log = open(os.path.join(self.tmp, "log.txt"), "w")
        self.p = subprocess.Popen([LANCADOR, *map(str, args)], env=env, stdout=self.log, stderr=self.log,
                                  stdin=subprocess.DEVNULL, start_new_session=True)
        self.janelas = Janelas()

    def comando(self, *args):
        """Roda o lancador de novo com o mesmo id: o comando vai para esta instancia."""
        return subprocess.run([LANCADOR, *map(str, args)], env=self.env, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=15)

    @property
    def pid(self):
        return self.p.pid

    def do_app(self):
        return self.janelas.do_processo(self.p.pid)

    def espera_janelas(self, n, tempo=12):
        return espera(lambda: len(self.do_app()) >= n and self.do_app(), tempo, msg="%d janela(s) do app" % n)

    def espera_saida(self, tempo=12):
        """Espera aparecer um PNG em CAPTURE_DIR; devolve o caminho."""
        def achou():
            if os.path.isdir(self.saida):
                arqs = sorted(f for f in os.listdir(self.saida) if f.endswith(".png"))
                if arqs:
                    return os.path.join(self.saida, arqs[0])
        return espera(achou, tempo, msg="captura salva")

    def espera_fim(self, tempo=8):
        return espera(lambda: self.p.poll() is not None, tempo, msg="o processo terminar")

    def geometria(self, tempo=10, com_imagem=True):
        def le():
            try:
                with open(self.geom_arq) as f:
                    g = json.load(f)
            except (OSError, ValueError):
                return None
            if g.get("xid") and g["botoes"] and (g["editor"]["imagem"] or not com_imagem):
                return g
        return espera(le, tempo, 0.2, "geometria da janela")

    def encerra(self):
        try:
            if self.p.poll() is None:
                try:
                    os.killpg(self.p.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    self.p.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(self.p.pid, signal.SIGKILL)
                    self.p.wait()
        finally:
            self.janelas.fecha()
            self.log.close()
            shutil.rmtree(self.tmp, ignore_errors=True)


def _clip(*args):
    try:
        return subprocess.run(["xclip", "-selection", "clipboard", *args], capture_output=True, timeout=4)
    except subprocess.TimeoutExpired:   # dono da selecao que nao responde: trata como vazia
        return subprocess.CompletedProcess(args, 1, b"", b"")


def _clip_define(tipo, dados):
    p = subprocess.Popen(["xclip", "-selection", "clipboard", "-t", tipo, "-i"], stdin=subprocess.PIPE,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    p.stdin.write(dados)
    p.stdin.close()
    p.wait(timeout=5)


def guarda_area_de_transferencia():
    """(texto, png) atuais da area de transferencia, para restaurar depois."""
    alvos = _clip("-t", "TARGETS", "-o").stdout.decode(errors="replace").split()
    texto = _clip("-t", "UTF8_STRING", "-o").stdout if "UTF8_STRING" in alvos else b""
    png = _clip("-t", "image/png", "-o").stdout if "image/png" in alvos else b""
    return texto, png


def restaura_area_de_transferencia(estado):
    texto, png = estado
    if texto:
        _clip_define("UTF8_STRING", texto)
    elif png:
        _clip_define("image/png", png)
    else:
        _clip_define("UTF8_STRING", b"")


class CasoE2E(unittest.TestCase):
    """Base: pula sem display e cuida da limpeza (ponteiro, teclas, processos, area de transferencia).

    Nao ha nova tentativa automatica: se o teste falhar (por exemplo, por alguem mexer no mouse
    durante a execucao), ele falha, e o resultado e esse."""

    def setUp(self):
        if PULAR:
            self.skipTest(PULAR)
        self.limpeza = []
        estado = guarda_area_de_transferencia()
        self.limpeza.append(lambda: restaura_area_de_transferencia(estado))

    def tearDown(self):
        for f in reversed(self.limpeza):
            try:
                f()
            except Exception as e:
                print("limpeza falhou:", e, file=sys.stderr)

    def instancia(self, *args, **kw):
        i = Instancia(*args, **kw)
        self.addCleanup(i.encerra)
        return i

    def entrada(self):
        e = Entrada()
        self.limpeza.append(e.restaura)
        return e

    def run(self, result=None):
        """Roda o teste; se (e so se) ele terminar com InterferenciaDoMouse, repete uma unica vez,
        avisando na saida. Falhas de asserção e outros erros nunca sao repetidos."""
        resultado = result or self.defaultTestResult()
        nf, ne = len(resultado.failures), len(resultado.errors)
        super().run(resultado)
        novos = resultado.errors[ne:]
        so_interferencia = (len(resultado.failures) == nf and novos
                            and all("InterferenciaDoMouse" in tb for _, tb in novos))
        if so_interferencia and not getattr(self, "_segunda", False):
            del resultado.errors[ne:]
            self._segunda = True
            print("\n[e2e] AVISO: %s foi interrompido por interferência do mouse (%s); repetindo uma vez"
                  % (self.id(), novos[0][1].strip().splitlines()[-1]), file=sys.stderr)
            time.sleep(1.5)
            super().run(resultado)
        return resultado
