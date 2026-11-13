"""Paleta do Capture: a unica fonte das cores, usada pelo CSS da interface e pela sobreposicao."""

ESCURO = {"surface": "#1C1C1E", "raised": "#242426", "canvas": "#141416", "text": "#ECECEE",
          "accent": "#2DD4A7", "accent_fg": "#06231B", "edge": "rgba(255, 255, 255, 0.10)"}
CLARO = {"surface": "#F7F7F8", "raised": "#FFFFFF", "canvas": "#EDEDEF", "text": "#1C1C1E",
         "accent": "#0E9F7C", "accent_fg": "#FFFFFF", "edge": "rgba(28, 28, 30, 0.10)"}


def rgb(hexa):
    """'#RRGGBB' -> (r, g, b) de 0 a 1, para o cairo."""
    return tuple(int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5))


def tokens_css(paleta):
    """Linhas @define-color cap_* de uma paleta."""
    return "".join("@define-color cap_%s %s;\n" % (k, v) for k, v in paleta.items())
