"""Paleta do Capture: a unica fonte das cores, usada pelo CSS da interface e pela sobreposicao."""

ESCURO = {"surface": "#121A26", "raised": "#1A2433", "canvas": "#0C121B", "text": "#E8EEF5",
          "accent": "#2DD4A7", "accent_fg": "#06231B", "edge": "rgba(255, 255, 255, 0.10)"}
CLARO = {"surface": "#F4F7FA", "raised": "#FFFFFF", "canvas": "#E6EBF1", "text": "#17202E",
         "accent": "#0E9F7C", "accent_fg": "#FFFFFF", "edge": "rgba(18, 26, 38, 0.10)"}


def rgb(hexa):
    """'#RRGGBB' -> (r, g, b) de 0 a 1, para o cairo."""
    return tuple(int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5))


def tokens_css(paleta):
    """Linhas @define-color cap_* de uma paleta."""
    return "".join("@define-color cap_%s %s;\n" % (k, v) for k, v in paleta.items())
