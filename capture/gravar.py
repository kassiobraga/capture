"""Gravacao de tela em MP4 e GIF via FFmpeg, sem dependencia de GTK."""
import io
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time

import cairo

FORMATOS_GRAVACAO = [("mp4", "MP4"), ("gif", "GIF")]
FPS_PADRAO = {"mp4": 24, "gif": 12}
FONTE_AUDIO_PADRAO = "default"

_CACHE_ENCODERS = {}
_CACHE_DISPOSITIVOS = {}


def tem_ffmpeg(binario="ffmpeg"):
    """True se o executavel do FFmpeg esta disponivel no PATH."""
    return shutil.which(binario) is not None


def formatar_duracao(segundos):
    """Segundos -> 'MM:SS' (ou 'H:MM:SS' acima de uma hora)."""
    total = max(0, int(segundos))
    h, resto = divmod(total, 3600)
    m, s = divmod(resto, 60)
    if h:
        return "%d:%02d:%02d" % (h, m, s)
    return "%02d:%02d" % (m, s)


def _intercepta(a, b, folga=0):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b[0] - folga, b[1] - folga, b[2] + 2 * folga, b[3] + 2 * folga
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


def _dentro(c, mon, borda=8):
    cx, cy, cw, ch = c
    mx, my, mw, mh = mon
    return (cx >= mx + borda and cy >= my + borda
            and cx + cw <= mx + mw - borda and cy + ch <= my + mh - borda)


def _area_comum(a, b):
    x0 = max(a[0], b[0])
    y0 = max(a[1], b[1])
    x1 = min(a[0] + a[2], b[0] + b[2])
    y1 = min(a[1] + a[3], b[1] + b[3])
    return max(0, x1 - x0) * max(0, y1 - y0)


def posicionar_barra(area, monitores, barra_w, barra_h, margem=14):
    """Escolhe (x, y) para a barra de Parar ficar fora da `area` gravada.

    Ordem de preferencia no monitor da gravacao: abaixo, acima, direita,
    esquerda e cantos livres. Se nao couber sem invadir a area gravada,
    procura outro monitor livre. So cai dentro da area quando a gravacao
    cobre todos os monitores inteiros (caso de tela cheia em monitor unico).
    """
    rx, ry, rw, rh = [int(round(v)) for v in area]
    bw, bh = max(1, int(round(barra_w))), max(1, int(round(barra_h)))
    mons = [tuple(int(round(v)) for v in m) for m in (monitores or []) if m[2] > 0 and m[3] > 0]
    if not mons:
        mons = [(0, 0, max(rx + rw, bw + 40), max(ry + rh, bh + 80))]

    mons_ord = sorted(mons, key=lambda m: _area_comum((rx, ry, rw, rh), m), reverse=True)
    mp = mons_ord[0]
    mx, my, mw, mh = mp
    borda = 8

    def prende(v, ini, fim):
        return max(ini, min(v, max(ini, fim)))

    xm = prende(rx + (rw - bw) // 2, mx + borda, mx + mw - bw - borda)
    ym = prende(ry + (rh - bh) // 2, my + borda, my + mh - bh - borda)

    candidatos_local = [
        (xm, ry + rh + margem),
        (xm, ry - bh - margem),
        (rx + rw + margem, ym),
        (rx - bw - margem, ym),
        (mx + mw - bw - 20, my + mh - bh - 48),
        (mx + mw - bw - 20, my + 24),
        (mx + 20, my + mh - bh - 48),
        (mx + 20, my + 24),
    ]
    for cx, cy in candidatos_local:
        ret = (cx, cy, bw, bh)
        if _dentro(ret, mp, borda) and not _intercepta(ret, (rx, ry, rw, rh), folga=4):
            return cx, cy

    for m2 in mons_ord[1:]:
        m2x, m2y, m2w, m2h = m2
        xm2 = prende(m2x + (m2w - bw) // 2, m2x + borda, m2x + m2w - bw - borda)
        opcoes = [
            (xm2, m2y + m2h - bh - 48),
            (xm2, m2y + 24),
            (m2x + m2w - bw - 20, m2y + m2h - bh - 48),
            (m2x + 20, m2y + m2h - bh - 48),
        ]
        for cx, cy in opcoes:
            ret = (cx, cy, bw, bh)
            if _dentro(ret, m2, borda) and not _intercepta(ret, (rx, ry, rw, rh), folga=4):
                return cx, cy

    # Tela cheia cobrindo todos os monitores: canto inferior direito discreto
    return prende(mx + mw - bw - 20, mx, mx + mw - bw), prende(my + mh - bh - 48, my, my + mh - bh)


def _saida_encoders(binario="ffmpeg"):
    if binario not in _CACHE_ENCODERS:
        try:
            r = subprocess.run([binario, "-hide_banner", "-encoders"],
                               capture_output=True, text=True, timeout=6)
            _CACHE_ENCODERS[binario] = r.stdout or ""
        except Exception:
            _CACHE_ENCODERS[binario] = ""
    return _CACHE_ENCODERS[binario]


def _encoders_disponiveis(saida_encoders=None, binario="ffmpeg", tipo="V"):
    if saida_encoders is None:
        saida_encoders = _saida_encoders(binario=binario)
    padrao = r"^\s*%s[\.A-Z]{5}\s+([A-Za-z0-9_\-]+)" % re.escape(tipo)
    nomes = set()
    for ln in saida_encoders.splitlines():
        m = re.match(padrao, ln)
        if m:
            nomes.add(m.group(1))
    return nomes


def escolher_encoder_mp4(saida_encoders=None, binario="ffmpeg"):
    """Devolve (nome, argumentos_ffmpeg) para gravar MP4 compativel."""
    disp = _encoders_disponiveis(saida_encoders, binario=binario, tipo="V")
    if "libx264" in disp:
        return ("libx264", ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                            "-pix_fmt", "yuv420p", "-movflags", "+faststart"])
    if "libopenh264" in disp:
        return ("libopenh264", ["-c:v", "libopenh264", "-pix_fmt", "yuv420p",
                                "-movflags", "+faststart"])
    return ("mpeg4", ["-c:v", "mpeg4", "-q:v", "4", "-pix_fmt", "yuv420p",
                      "-movflags", "+faststart"])


def escolher_encoder_audio(saida_encoders=None, binario="ffmpeg"):
    """Devolve (nome, argumentos_ffmpeg) para a trilha de voz do MP4."""
    disp = _encoders_disponiveis(saida_encoders, binario=binario, tipo="A")
    if "aac" in disp:
        return ("aac", ["-c:a", "aac", "-b:a", "128k"])
    if "libopus" in disp:
        return ("libopus", ["-c:a", "libopus", "-b:a", "96k"])
    if "libmp3lame" in disp:
        return ("libmp3lame", ["-c:a", "libmp3lame", "-b:a", "128k"])
    return ("aac", ["-c:a", "aac", "-b:a", "128k"])


def tem_entrada_pulse(saida_dispositivos=None, binario="ffmpeg"):
    """True se o FFmpeg tem o demuxer de entrada 'pulse' (PulseAudio / PipeWire)."""
    if saida_dispositivos is None:
        if binario not in _CACHE_DISPOSITIVOS:
            try:
                r = subprocess.run([binario, "-hide_banner", "-devices"],
                                   capture_output=True, text=True, timeout=6)
                _CACHE_DISPOSITIVOS[binario] = r.stdout or ""
            except Exception:
                _CACHE_DISPOSITIVOS[binario] = ""
        saida_dispositivos = _CACHE_DISPOSITIVOS[binario]
    for ln in saida_dispositivos.splitlines():
        if re.match(r"^\s*D[E\.]\s+pulse\b", ln):
            return True
    return False


def escolher_encoder_temp_gif(saida_encoders=None, binario="ffmpeg"):
    """Devolve (extensao, argumentos_ffmpeg) sem perda para o arquivo temporario do GIF."""
    disp = _encoders_disponiveis(saida_encoders, binario=binario, tipo="V")
    if "qtrle" in disp:
        return (".mov", ["-c:v", "qtrle", "-pix_fmt", "rgb24"])
    if "ffv1" in disp:
        return (".mkv", ["-c:v", "ffv1", "-pix_fmt", "bgr0"])
    return (".avi", ["-c:v", "rawvideo", "-pix_fmt", "bgr0"])


def _bgr0_para_cairo(dados, w, h):
    img = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h)
    destino, passo = img.get_data(), img.get_stride()
    linha = w * 4
    if passo == linha:
        destino[:h * passo] = dados[:h * passo]
    else:
        for i in range(h):
            destino[i * passo:i * passo + linha] = dados[i * linha:i * linha + linha]
    img.mark_dirty()
    return img


def extrair_quadro_cairo(caminho, binario="ffmpeg"):
    """Extrai o primeiro quadro de um MP4 ou GIF como cairo.ImageSurface."""
    if not caminho or not os.path.isfile(caminho):
        return None
    try:
        r = subprocess.run(
            [binario, "-v", "error", "-i", caminho, "-frames:v", "1",
             "-f", "image2pipe", "-vcodec", "png", "-"],
            capture_output=True, timeout=10, check=True,
        )
        if not r.stdout:
            return None
        return cairo.ImageSurface.create_from_png(io.BytesIO(r.stdout))
    except Exception:
        return None


class Gravador:
    """Captura quadros BGR0 num compasso fixo e grava MP4 (com ou sem voz) ou GIF via FFmpeg."""

    def __init__(self, largura, altura, destino, formato="mp4", fps=None,
                 fonte_quadros=None, para_superficie=None, binario="ffmpeg",
                 audio=False, fonte_audio=FONTE_AUDIO_PADRAO, env=None):
        fmt = (formato or "mp4").lower()
        if fmt not in dict(FORMATOS_GRAVACAO):
            raise ValueError("formato de gravacao desconhecido: %s" % formato)
        if fonte_quadros is None:
            raise ValueError("fonte_quadros e obrigatoria")
        self.largura = max(1, int(largura))
        self.altura = max(1, int(altura))
        self.destino = os.path.abspath(destino)
        self.formato = fmt
        self.fps = int(fps or FPS_PADRAO[fmt])
        self.fonte_quadros = fonte_quadros
        self._para_sup = para_superficie or (lambda b: _bgr0_para_cairo(b, self.largura, self.altura))
        self.binario = binario
        self.env = env

        self.audio_solicitado = bool(audio) and fmt == "mp4"
        self.fonte_audio = str(fonte_audio or FONTE_AUDIO_PADRAO)
        self.audio_ativo = False
        self.aviso_audio = None

        self.primeiro_quadro_img = None
        self._ultimo_quadro = None
        self._quadros = 0
        self._inicio = None
        self._fim = None
        self._erro_loop = None
        self._parar = threading.Event()
        self._thread = None
        self._proc = None
        self._pasta_tmp = None
        self._arq_captura = None
        self._encerrado = False

    def _montar_cmd(self, usar_audio=False):
        if self.formato == "mp4":
            _, args_enc = escolher_encoder_mp4(binario=self.binario)
            self._arq_captura = os.path.join(self._pasta_tmp, "saida.mp4")
            if usar_audio:
                _, args_aud = escolher_encoder_audio(binario=self.binario)
                return [
                    self.binario, "-y", "-hide_banner", "-loglevel", "error",
                    "-thread_queue_size", "512",
                    "-f", "rawvideo", "-pix_fmt", "bgr0",
                    "-s", "%dx%d" % (self.largura, self.altura),
                    "-r", str(self.fps), "-i", "-",
                    "-thread_queue_size", "512",
                    "-f", "pulse", "-i", self.fonte_audio,
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                    *args_enc, *args_aud, "-shortest", self._arq_captura,
                ]
            return [
                self.binario, "-y", "-hide_banner", "-loglevel", "error",
                "-f", "rawvideo", "-pix_fmt", "bgr0",
                "-s", "%dx%d" % (self.largura, self.altura),
                "-r", str(self.fps), "-i", "-",
                "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                *args_enc, self._arq_captura,
            ]
        ext_tmp, args_enc = escolher_encoder_temp_gif(binario=self.binario)
        self._arq_captura = os.path.join(self._pasta_tmp, "bruto" + ext_tmp)
        return [
            self.binario, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "bgr0",
            "-s", "%dx%d" % (self.largura, self.altura),
            "-r", str(self.fps), "-i", "-",
            *args_enc, self._arq_captura,
        ]

    @staticmethod
    def _fecha_proc_morto(proc):
        for p in (proc.stdin, proc.stderr):
            if p is not None:
                try:
                    p.close()
                except Exception:
                    pass
        try:
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def _iniciar_ffmpeg(self, primeiro, usar_audio):
        cmd = self._montar_cmd(usar_audio=usar_audio)
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE, env=self.env)
        t0 = time.monotonic()
        try:
            proc.stdin.write(primeiro)
            proc.stdin.flush()
        except BrokenPipeError:
            self._fecha_proc_morto(proc)
            return None, None
        if usar_audio:
            # Se o servidor de audio nao estiver acessivel ou nao houver microfone,
            # o FFmpeg encerra nos primeiros ~80 ms ao abrir a entrada pulse.
            for _ in range(18):
                if proc.poll() is not None:
                    self._fecha_proc_morto(proc)
                    return None, None
                time.sleep(0.01)
        return proc, t0

    def iniciar(self):
        """Captura o primeiro quadro, abre o FFmpeg e inicia a thread de gravacao."""
        if self._inicio is not None:
            raise RuntimeError("a gravacao ja foi iniciada")
        if not tem_ffmpeg(self.binario):
            raise RuntimeError("O FFmpeg não foi encontrado no sistema.")
        esperado = self.largura * self.altura * 4
        primeiro = self.fonte_quadros()
        if not isinstance(primeiro, (bytes, bytearray, memoryview)) or len(primeiro) != esperado:
            raise RuntimeError("quadro com tamanho invalido (%d != %d)" % (len(primeiro or b""), esperado))
        primeiro = bytes(primeiro)
        self._ultimo_quadro = primeiro
        try:
            self.primeiro_quadro_img = self._para_sup(primeiro)
        except Exception:
            self.primeiro_quadro_img = None

        self._pasta_tmp = tempfile.mkdtemp(prefix="capture-grav-")
        try:
            tentar_audio = False
            if self.audio_solicitado:
                if tem_entrada_pulse(binario=self.binario):
                    tentar_audio = True
                else:
                    self.aviso_audio = "Suporte a áudio indisponível no FFmpeg: gravando sem som"

            proc, t0 = (None, None)
            if tentar_audio:
                proc, t0 = self._iniciar_ffmpeg(primeiro, usar_audio=True)
                if proc is not None:
                    self.audio_ativo = True
                else:
                    self.aviso_audio = "Microfone indisponível: gravando sem áudio"
                    if self._arq_captura and os.path.exists(self._arq_captura):
                        try:
                            os.unlink(self._arq_captura)
                        except OSError:
                            pass

            if proc is None:
                proc, t0 = self._iniciar_ffmpeg(primeiro, usar_audio=False)
                if proc is None:
                    raise RuntimeError("Não foi possível iniciar o processo do FFmpeg.")

            self._proc = proc
            self._quadros = 1
            self._inicio = t0
        except Exception:
            self._limpa_tmp()
            raise

        self._thread = threading.Thread(target=self._loop, name="capture-gravador", daemon=True)
        self._thread.start()

    def duracao(self):
        """Tempo gravado em segundos."""
        if self._inicio is None:
            return 0.0
        fim = self._fim if self._fim is not None else time.monotonic()
        return max(0.0, fim - self._inicio)

    def _loop(self):
        passo = 1.0 / self.fps
        while not self._parar.is_set():
            alvo = self._inicio + self._quadros * passo
            falta = alvo - time.monotonic()
            if falta > 0:
                if self._parar.wait(falta):
                    break
            if self._parar.is_set():
                break
            try:
                quadro = bytes(self.fonte_quadros())
                self._ultimo_quadro = quadro
                agora = time.monotonic()
                atrasados = max(1, int((agora - self._inicio) * self.fps) - self._quadros + 1)
                repeticoes = min(atrasados, self.fps)
                for _ in range(repeticoes):
                    self._proc.stdin.write(quadro)
                    self._quadros += 1
            except Exception as e:
                self._erro_loop = e
                break

    def _limpa_tmp(self):
        if self._pasta_tmp and os.path.isdir(self._pasta_tmp):
            shutil.rmtree(self._pasta_tmp, ignore_errors=True)
        self._pasta_tmp = None

    def parar(self, cancelar=False):
        """Encerra a gravacao e gera o arquivo final (ou descarta se cancelar=True)."""
        if self._encerrado:
            return None
        self._encerrado = True
        self._fim = time.monotonic()
        self._parar.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

        if self._proc is None:
            self._limpa_tmp()
            return None

        try:
            if cancelar:
                try:
                    self._proc.stdin.close()
                except Exception:
                    pass
                self._proc.kill()
                self._proc.wait(timeout=5)
                return None

            # Garante pelo menos 2 quadros para reprodutores e conversao GIF
            if self._quadros < 2 and self._ultimo_quadro is not None:
                try:
                    self._proc.stdin.write(self._ultimo_quadro)
                    self._quadros += 1
                except Exception:
                    pass

            try:
                self._proc.stdin.close()
            except Exception:
                pass
            err_bytes = self._proc.stderr.read() if self._proc.stderr else b""
            rc = self._proc.wait(timeout=30)
            if self._proc.stderr:
                self._proc.stderr.close()
            if rc != 0 or not os.path.isfile(self._arq_captura):
                detalhe = err_bytes.decode("utf-8", errors="replace").strip()
                raise RuntimeError("FFmpeg falhou ao gravar (%s)" % (detalhe or ("codigo %d" % rc)))

            arq_pronto = self._arq_captura
            if self.formato == "gif":
                arq_gif = os.path.join(self._pasta_tmp, "saida.gif")
                filtro = ("split[s0][s1];"
                          "[s0]palettegen=stats_mode=diff[p];"
                          "[s1][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle")
                r = subprocess.run(
                    [self.binario, "-y", "-hide_banner", "-loglevel", "error",
                     "-i", self._arq_captura, "-vf", filtro, "-loop", "0", arq_gif],
                    capture_output=True, text=True, timeout=60,
                )
                if r.returncode != 0 or not os.path.isfile(arq_gif):
                    raise RuntimeError("FFmpeg falhou ao gerar o GIF (%s)" % (r.stderr.strip() or r.returncode))
                arq_pronto = arq_gif

            os.makedirs(os.path.dirname(self.destino), exist_ok=True)
            shutil.move(arq_pronto, self.destino)
            return {
                "caminho": self.destino,
                "formato": self.formato,
                "duracao": max(0.1, round(self.duracao(), 2)),
                "quadros": self._quadros,
                "largura": self.largura,
                "altura": self.altura,
                "miniatura_img": self.primeiro_quadro_img,
                "audio": self.audio_ativo,
                "aviso_audio": self.aviso_audio,
            }
        finally:
            self._limpa_tmp()
