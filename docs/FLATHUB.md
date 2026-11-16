# Publicar e atualizar o Capture

Há dois caminhos, e eles se completam.

## 1. Repositório próprio (atualização automática)

O Capture tem um repositório Flatpak próprio, publicado no GitHub Pages em
<https://kassiobraga.github.io/capture/>. Quem instala pelo botão da página
(arquivo `.flatpakref`) recebe as versões novas pelo Gerenciador de
Atualizações.

Para lançar uma versão:

1. Atualize `__version__` em `capture/__init__.py` e acrescente um `<release>`
   no topo de `<releases>` em `data/io.github.kassiobraga.Capture.metainfo.xml`.
2. Envie para a `main` e crie a tag:

   ```sh
   git tag -a v1.0.2 -m "Capture 1.0.2"
   git push origin v1.0.2
   ```

O workflow "Flatpak" monta o pacote, assina com a chave do projeto (segredo
`FLATPAK_GPG_KEY` do repositório), publica no branch `gh-pages` e anexa
`Capture.flatpak` ao release.

A chave de assinatura é a identidade das atualizações: guarde uma cópia de
segurança. Se ela se perder ou for trocada, quem já instalou precisa reinstalar
pelo link.

## 2. Flathub: regras sobre IA

O Flathub (a loja que aparece no Gerenciador de Aplicativos do Mint) tem uma
[política sobre IA generativa](https://docs.flathub.org/docs/for-app-authors/requirements#generative-ai-policy):

- O manifesto enviado ao Flathub não pode ser gerado nem editado por IA.
- O pull request de submissão, o texto dele e as respostas aos revisores não
  podem ser feitos ou automatizados por IA.
- Material gerado por IA no próprio aplicativo (código, documentação, o
  manifesto deste repositório) precisa ser declarado no pedido, com as partes
  afetadas e a extensão aproximada.
- O projeto precisa ter histórico de desenvolvimento, uso real e compromisso de
  manutenção.

Por isso a submissão ao Flathub, se feita, é trabalho manual do mantenedor:
manifesto escrito à mão, pull request aberto e conduzido sem ferramentas de IA,
e a declaração do código gerado com IA neste projeto.

## Limitações conhecidas do pacote Flatpak

- Precisa de sessão X11 (o padrão do Linux Mint com Cinnamon).
- A tecla Print não é configurada automaticamente: crie um atalho para
  `flatpak run io.github.kassiobraga.Capture --novo`.
- `capture --abrir ARQUIVO` só enxerga arquivos dentro da pasta de imagens.
  "Salvar como..." usa o diálogo do sistema e grava em qualquer pasta.
