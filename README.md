# Booklet A5 — Template em Markdown

Livrinho A5 com diagramação **fixa** (cores, fontes, posições). Você só edita
**textos, páginas e fotos** — tudo no `template_booklet.md`.

## Fluxo de uso

1. Abra **`template_booklet.md`** em qualquer editor.
2. Edite:
   - a **ficha** no topo (entre `---`): título, autora, local, ano, créditos e foto da capa — ela alimenta capa, rosto, assinatura e contracapa;
   - os textos das seções **Apresentação**, **Conto** e **Sobre a autora**;
   - as **fotos** na pasta `ilustracoes/` (mantenha o mesmo caminho no `.md`).
3. Gere o PDF:
   ```
   python gerar_booklet.py
   ```
4. O resultado sai em **`booklet_A5.pdf`**.

## O que cada parte vira

| Fonte | Onde aparece |
|-------|--------------|
| Ficha (front matter) | Capa, Rosto, assinatura da Apresentação, contracapa |
| `## Apresentação` | 1+ páginas (fluxo automático; assinatura = `pedagogico`) |
| `## Conto` (blocos separados por `---` ou `###`) | 1 página por bloco |
| `## Sobre a autora` | Bio + foto (opcional) |

## Dicas

- **Mais páginas no conto:** separe novos trechos com `---`.
- **Texto longo na apresentação:** escreva mais parágrafos — o fluxo abre páginas novas sozinho.
- **Créditos da contracapa e assinatura:** vêm de `capa` e `pedagogico` na ficha — edite só lá.
- **Fotos:** troque os arquivos em `ilustracoes/` (mesmos nomes).

## Arquivos

```
booklet_A5_projeto/
├── template_booklet.md   <- EDITAR AQUI
├── gerar_booklet.py      <- fixo (gerador)
├── booklet_A5.pdf        <- resultado
├── origem.pdf            <- documento fonte
└── ilustracoes/          <- fotos (troque pelos seus arquivos)
```

## Personalização (opcional)

Cores e fontes estão no bloco `CSS` dentro de `gerar_booklet.py`. Não precisa mexer
para usar o template.