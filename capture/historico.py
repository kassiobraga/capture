"""Historico de capturas, cache de miniaturas e preferencias em JSON."""
import datetime
import json
import os
import uuid

import cairo
from gi.repository import GLib

from . import APP_ID
from .gravar import FORMATOS_GRAVACAO, extrair_quadro_cairo

RETENCOES = [("manter", "Manter histórico"), ("diaria", "Limpar a lista todo dia")]
LARGURA_MINI = 200
ALTURA_MINI = 130


def _tipo_arquivo(caminho):
    ext = os.path.splitext(caminho or "")[1].lstrip(".").lower()
    return ext if ext in ("png", "mp4", "gif") else "png"


def _carrega_imagem_item(caminho):
    if _tipo_arquivo(caminho) in ("mp4", "gif"):
        return extrair_quadro_cairo(caminho)
    try:
        return cairo.ImageSurface.create_from_png(caminho)
    except Exception:
        return None


def pastas_padrao(app_id=None):
    """Pastas (dados, cache, config) do aplicativo."""
    est = os.environ.get("CAPTURE_ESTADO")
    if est:
        return (os.path.join(est, "dados"), os.path.join(est, "cache"), os.path.join(est, "config"))
    dados = GLib.get_user_data_dir()
    cache = GLib.get_user_cache_dir()
    config = GLib.get_user_config_dir()
    if os.path.exists("/.flatpak-info") and not os.environ.get("CAPTURE_APP_ID") and not app_id:
        return dados, cache, config
    aid = app_id or os.environ.get("CAPTURE_APP_ID") or APP_ID
    return os.path.join(dados, aid), os.path.join(cache, aid), os.path.join(config, aid)


def _le_json(caminho, padrao):
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return padrao


def _grava_json(caminho, dados):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    os.replace(tmp, caminho)


def gera_miniatura(img, destino, max_w=LARGURA_MINI, max_h=ALTURA_MINI):
    """Grava em `destino` uma miniatura PNG proporcional de `img`."""
    w, h = img.get_width(), img.get_height()
    if w < 1 or h < 1:
        return False
    esc = min(1.0, max_w / w, max_h / h)
    mw, mh = max(1, round(w * esc)), max(1, round(h * esc))
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, mw, mh)
    cr = cairo.Context(out)
    cr.scale(mw / w, mh / h)
    cr.set_source_surface(img, 0, 0)
    cr.get_source().set_filter(cairo.FILTER_GOOD)
    cr.paint()
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    tmp = destino + ".tmp"
    out.write_to_png(tmp)
    os.replace(tmp, destino)
    return True


def rotulo_data(iso_str, hoje=None):
    """Data e hora legiveis para exibir no painel lateral."""
    try:
        dt = datetime.datetime.fromisoformat(iso_str)
    except (TypeError, ValueError):
        return iso_str or ""
    d_hoje = (hoje or datetime.date.today())
    if isinstance(d_hoje, datetime.datetime):
        d_hoje = d_hoje.date()
    hora = dt.strftime("%H:%M")
    if dt.date() == d_hoje:
        return "Hoje, %s" % hora
    if dt.date() == d_hoje - datetime.timedelta(days=1):
        return "Ontem, %s" % hora
    return "%s, %s" % (dt.strftime("%d/%m/%Y"), hora)


class Registro:
    """Lista persistente de capturas e preferencias, sem dependencia de GTK."""

    def __init__(self, pasta_dados=None, pasta_cache=None, pasta_config=None, agora=None):
        if pasta_dados is None or pasta_cache is None or pasta_config is None:
            pd, pc, pcfg = pastas_padrao()
            pasta_dados = pasta_dados or pd
            pasta_cache = pasta_cache or pc
            pasta_config = pasta_config or pcfg
        self.pasta_dados = pasta_dados
        self.pasta_mini = os.path.join(pasta_cache, "miniaturas")
        self.pasta_config = pasta_config
        self.arq_registro = os.path.join(self.pasta_dados, "historico.json")
        self.arq_prefs = os.path.join(self.pasta_config, "preferencias.json")
        prefs = _le_json(self.arq_prefs, {})
        if not isinstance(prefs, dict):
            prefs = {}
        ret = prefs.get("retencao", "manter")
        self.retencao = ret if ret in dict(RETENCOES) else "manter"
        self.anonimo = bool(prefs.get("anonimo", False))
        fmt = str(prefs.get("formato_gravacao", "mp4")).lower()
        self.formato_gravacao = fmt if fmt in dict(FORMATOS_GRAVACAO) else "mp4"
        self.audio_gravacao = bool(prefs.get("audio_gravacao", True))
        bruto = _le_json(self.arq_registro, [])
        self._itens = [x for x in bruto if isinstance(x, dict)] if isinstance(bruto, list) else []
        self.sincronizar(agora=agora)

    def _salva_prefs(self):
        _grava_json(self.arq_prefs, {
            "retencao": self.retencao,
            "anonimo": self.anonimo,
            "formato_gravacao": self.formato_gravacao,
            "audio_gravacao": self.audio_gravacao,
        })

    def _salva_registro(self):
        _grava_json(self.arq_registro, self._itens)

    def _apaga_mini(self, nome):
        if not nome:
            return
        try:
            os.unlink(os.path.join(self.pasta_mini, nome))
        except OSError:
            pass

    def definir_retencao(self, modo, agora=None):
        """Define a politica ('manter' ou 'diaria') e aplica imediatamente."""
        if modo not in dict(RETENCOES):
            raise ValueError("retencao desconhecida: %s" % modo)
        self.retencao = modo
        self._salva_prefs()
        self.sincronizar(agora=agora)

    def definir_anonimo(self, ativo):
        """Liga ou desliga o modo anonimo e persiste nas preferencias."""
        self.anonimo = bool(ativo)
        self._salva_prefs()

    def definir_formato_gravacao(self, formato):
        """Define o formato padrao da gravacao ('mp4' ou 'gif') e persiste."""
        fmt = (formato or "").lower()
        if fmt not in dict(FORMATOS_GRAVACAO):
            raise ValueError("formato de gravacao desconhecido: %s" % formato)
        self.formato_gravacao = fmt
        self._salva_prefs()

    def definir_audio_gravacao(self, ativo):
        """Liga ou desliga a captura do microfone nas gravacoes MP4 e persiste."""
        self.audio_gravacao = bool(ativo)
        self._salva_prefs()

    def sincronizar(self, agora=None):
        """Remove itens cujo arquivo sumiu e, no modo diario, itens de dias anteriores."""
        hoje = (agora or datetime.datetime.now()).strftime("%Y-%m-%d")
        vivos = []
        mudou = False
        for it in self._itens:
            cam = it.get("caminho")
            criado = str(it.get("criado_em", ""))
            if not isinstance(cam, str) or not cam or not os.path.isfile(cam):
                self._apaga_mini(it.get("miniatura"))
                mudou = True
                continue
            if self.retencao == "diaria" and criado[:10] != hoje:
                self._apaga_mini(it.get("miniatura"))
                mudou = True
                continue
            vivos.append(it)
        self._itens = vivos
        if mudou and (os.path.exists(self.arq_registro) or vivos):
            self._salva_registro()
        return list(self._itens)

    def listar(self, agora=None):
        """Itens validos, do mais novo para o mais antigo."""
        return self.sincronizar(agora=agora)

    def adicionar(self, caminho, img=None, agora=None, tipo=None, duracao=None, audio=None):
        """Registra `caminho` no topo do historico; no modo anonimo nao faz nada."""
        self.sincronizar(agora=agora)
        if self.anonimo:
            return None
        cam = os.path.abspath(caminho)
        if not os.path.isfile(cam):
            return None
        tipo_item = (tipo or _tipo_arquivo(cam)).lower()
        if img is None:
            img = _carrega_imagem_item(cam)
        restantes = []
        for it in self._itens:
            if it.get("caminho") == cam:
                self._apaga_mini(it.get("miniatura"))
            else:
                restantes.append(it)
        ident = uuid.uuid4().hex[:12]
        nome_mini = ident + ".png"
        if img is not None:
            try:
                if not gera_miniatura(img, os.path.join(self.pasta_mini, nome_mini)):
                    nome_mini = None
            except Exception:
                nome_mini = None
        else:
            nome_mini = None
        instante = (agora or datetime.datetime.now()).replace(microsecond=0).isoformat()
        novo = {
            "id": ident,
            "caminho": cam,
            "tipo": tipo_item,
            "criado_em": instante,
            "largura": img.get_width() if img is not None else 0,
            "altura": img.get_height() if img is not None else 0,
            "miniatura": nome_mini,
        }
        if duracao is not None:
            novo["duracao"] = round(max(0.0, float(duracao)), 2)
        if audio is not None:
            novo["audio"] = bool(audio)
        self._itens = [novo] + restantes
        self._salva_registro()
        return dict(novo)

    def remover(self, ident):
        """Remove um item da lista (pelo id ou caminho), mantendo o arquivo original."""
        novos = []
        removido = False
        for it in self._itens:
            if not removido and (it.get("id") == ident or it.get("caminho") == ident):
                self._apaga_mini(it.get("miniatura"))
                removido = True
            else:
                novos.append(it)
        if removido:
            self._itens = novos
            self._salva_registro()
        return removido

    def limpar(self):
        """Esvazia toda a lista e as miniaturas em cache, mantendo os arquivos salvos."""
        for it in self._itens:
            self._apaga_mini(it.get("miniatura"))
        if os.path.isdir(self.pasta_mini):
            for arq in os.listdir(self.pasta_mini):
                if arq.endswith(".png"):
                    self._apaga_mini(arq)
        self._itens = []
        self._salva_registro()

    def caminho_miniatura(self, item):
        """Caminho do PNG da miniatura; recria no cache se tiver sido apagado."""
        nome = item.get("miniatura") or ("%s.png" % item.get("id", "mini"))
        destino = os.path.join(self.pasta_mini, nome)
        if os.path.isfile(destino):
            return destino
        cam = item.get("caminho")
        if cam and os.path.isfile(cam):
            img = _carrega_imagem_item(cam)
            if img is not None:
                try:
                    if gera_miniatura(img, destino):
                        item["miniatura"] = nome
                        return destino
                except Exception:
                    return None
        return None
