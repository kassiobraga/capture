"""Capture: captura de tela e anotação para Linux (X11), em GTK 4 / libadwaita."""

__version__ = "1.0.0"

APP_ID = "io.github.kassiobraga.Capture"
ICONE = APP_ID  # nome do icone no tema
NOME = "Capture"
PRGNAME = "capture"
MODOS = [("ret", "Retângulo"), ("janela", "Janela"), ("tela", "Tela cheia"), ("livre", "Forma livre")]
ATRASOS = [(0, "Sem atraso"), (3, "3 segundos"), (5, "5 segundos"), (10, "10 segundos")]
CORES = [(0.85, 0.23, 0.0), (0.93, 0.11, 0.14), (1.0, 0.88, 0.3), (0.13, 0.69, 0.3),
         (0.06, 0.42, 0.74), (0.55, 0.27, 0.8), (0.1, 0.1, 0.1), (1.0, 1.0, 1.0)]
