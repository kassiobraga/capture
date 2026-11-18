"""Onde e com que nome as capturas sao salvas."""
import datetime
import os

from gi.repository import GLib  # noqa: E402


def pasta_capturas():
    """Pasta das capturas: CAPTURE_DIR, ou 'Capturas' dentro da pasta de imagens do usuario."""
    env = os.environ.get("CAPTURE_DIR")
    if env:
        return env
    base = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES) or os.path.expanduser("~")
    return os.path.join(base, "Capturas")


def nome_livre(caminho):
    """O proprio caminho se nao existe; senao 'nome (2).ext', 'nome (3).ext'..."""
    if not os.path.exists(caminho):
        return caminho
    raiz, ext = os.path.splitext(caminho)
    n = 2
    while os.path.exists("%s (%d)%s" % (raiz, n, ext)):
        n += 1
    return "%s (%d)%s" % (raiz, n, ext)


def nome_captura(pasta, agora=None):
    """Caminho livre para uma captura nova dentro de `pasta` (cria a pasta)."""
    os.makedirs(pasta, exist_ok=True)
    agora = agora or datetime.datetime.now()
    return nome_livre(os.path.join(pasta, "Captura de tela %s.png" % agora.strftime("%Y-%m-%d %H%M%S")))


def nome_gravacao(pasta, ext="mp4", agora=None):
    """Caminho livre para uma gravacao nova dentro de `pasta` (cria a pasta)."""
    os.makedirs(pasta, exist_ok=True)
    agora = agora or datetime.datetime.now()
    limpa = (ext or "mp4").lstrip(".").lower() or "mp4"
    return nome_livre(os.path.join(pasta, "Gravação de tela %s.%s" % (agora.strftime("%Y-%m-%d %H%M%S"), limpa)))


def pasta_para_exibir(caminho):
    """Troca o diretorio pessoal por ~ para mostrar na interface."""
    home = os.path.expanduser("~")
    return "~" + caminho[len(home):] if caminho.startswith(home + os.sep) else caminho
