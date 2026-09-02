# Booklet A5 — Template em Markdown

Livrinho A5 com diagramação **fixa** (cores, fontes, posições). Você só edita
**textos, páginas e fotos** — no Markdown **ou** no editor visual.

## Editor visual (recomendado)

Abra **`index.html`** no navegador (Edge/Chrome):

- Edite ficha, apresentação, conto (adicione/remova páginas) e sobre a autora
- Preview das páginas A5 em tempo real
- **Imprimir / PDF** → salva o PDF A5 (texto vetorial, ideal)
- **Exportar .md** / **Importar .md** → mantém compatibilidade com o `gerar_booklet.py`
- **Histórico salvo no navegador** (IndexedDB) — vários booklets, com fotos, auto-salvo

## Fluxo com Markdown

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
| `## Ilustradores` (com `### Nome`, foto, função, bio) | 1 página com os ilustradores |
| `## A equipe` | Foto de todos + símbolo de Guaramiranga |

## Dicas

- **Mais páginas no conto:** separe novos trechos com `---`.
- **Texto longo na apresentação:** escreva mais parágrafos — o fluxo abre páginas novas sozinho.
- **Créditos da contracapa e assinatura:** os créditos de ilustração vêm da seção `## Ilustradores`; a assinatura da Apresentação vem de `pedagogico` na ficha — edite só nesses lugares.
- **Fotos:** troque os arquivos em `ilustracoes/` (mesmos nomes).

## Arquivos

```
booklet_A5_projeto/
├── index.html            <- EDITOR VISUAL (abra no navegador)
├── template_booklet.md   <- EDITAR AQUI (fluxo markdown)
├── gerar_booklet.py      <- fixo (gerador)
├── booklet_A5.pdf        <- resultado
├── origem.pdf            <- documento fonte
└── ilustracoes/          <- fotos (troque pelos seus arquivos)
```

## Personalização (opcional)

Cores e fontes estão no bloco `CSS` dentro de `gerar_booklet.py`. Não precisa mexer
para usar o template.