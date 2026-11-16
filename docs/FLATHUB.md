# Publicar e atualizar o Capture

Há dois caminhos, e eles se completam.

## 1. Release no GitHub (já funciona)

Cada envio ao GitHub gera `Capture.flatpak` (aba **Actions**, artefato do
workflow "Flatpak"). Para criar uma versão que qualquer pessoa baixa:

1. Atualize `__version__` em `capture/__init__.py` e acrescente um `<release>`
   no topo de `<releases>` em `data/io.github.kassiobraga.Capture.metainfo.xml`.
2. Crie e envie a tag:

   ```sh
   git tag v1.0.0
   git push origin v1.0.0
   ```

O workflow anexa `Capture.flatpak` ao release `v1.0.0`. Quem baixar dá dois
cliques e instala. **Limite:** um arquivo baixado assim não se atualiza
sozinho; a pessoa baixa a versão nova e instala de novo por cima.

## 2. Flathub: a loja, com atualização automática

O Flathub é a loja de aplicativos Flatpak. Ela aparece dentro do Gerenciador de
Aplicativos do Linux Mint, do GNOME Software (Ubuntu, Fedora) e do Discover
(KDE). Publicado lá, o Capture pode ser buscado pelo nome, instalado com um
clique e atualizado junto com o resto do sistema.

### Primeira submissão (uma vez)

1. Faça o merge deste trabalho na `main` e crie a tag `v1.0.0` (passo acima).
   As imagens de `docs/` precisam estar na `main`: a loja as mostra.
2. No GitHub, faça um fork de <https://github.com/flathub/flathub>, crie um
   branch a partir de `new-pr` e acrescente na raiz o arquivo
   `io.github.kassiobraga.Capture.yml`: uma cópia de
   `flatpak/io.github.kassiobraga.Capture.yml` em que a fonte do módulo
   `capture` (o bloco `type: dir`) vira:

   ```yaml
       sources:
         - type: git
           url: https://github.com/kassiobraga/capture.git
           tag: v1.0.0
           commit: <hash completo do commit da tag>   # git rev-parse v1.0.0^{commit}
   ```

3. Abra um pull request para o branch `new-pr` do `flathub/flathub`, com o
   título "Add io.github.kassiobraga.Capture". O robô de lá constrói o pacote
   e os revisores comentam no PR.
4. Pontos que os revisores costumam perguntar, já com as respostas:
   - **Por que `--socket=x11`, sem Wayland?** O Capture fotografa a tela e
     desenha a seleção por cima de todas as janelas, o que o Wayland não
     permite a aplicativos comuns. O suporte a Wayland, pelo portal de
     captura, está no roadmap.
   - **Por que `--filesystem=xdg-pictures`?** Toda captura é salva
     automaticamente em `~/Imagens/Capturas`.
   - **O id `io.github.kassiobraga`** corresponde à conta do GitHub dona do
     repositório; o Flathub pede para verificar isso no site dele depois da
     aprovação.
5. Aprovado, o Flathub cria o repositório
   `github.com/flathub/io.github.kassiobraga.Capture` e dá acesso a você.

### Cada versão nova

1. Faça o passo 1 da seção anterior (versão, `<release>` e tag).
2. No repositório `flathub/io.github.kassiobraga.Capture`, troque `tag` e
   `commit` no manifesto e abra um pull request. Quando o build passar, faça o
   merge: em algumas horas todos os usuários recebem a atualização.

## Limitações conhecidas do pacote Flatpak

- Precisa de sessão X11 (o padrão do Linux Mint com Cinnamon).
- A tecla Print não é configurada automaticamente: crie um atalho para
  `flatpak run io.github.kassiobraga.Capture --novo`.
- `capture --abrir ARQUIVO` só enxerga arquivos dentro da pasta de imagens.
  "Salvar como..." usa o diálogo do sistema e grava em qualquer pasta.
