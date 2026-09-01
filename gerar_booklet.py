# -*- coding: utf-8 -*-
# Gera o booklet A5 a partir do template_booklet.md (layout fixo).
# Uso: python gerar_booklet.py
import io
import os
import re
import subprocess
import sys

import markdown
from PIL import ImageFont

BASE   = os.path.dirname(os.path.abspath(__file__))
MD     = os.path.join(BASE, 'template_booklet.md')
OUT    = os.path.join(BASE, 'booklet_A5.pdf')
BUILD  = os.path.join(BASE, '_build.html')

F_REG  = r'C:\Windows\Fonts\georgia.ttf'
F_BOLD = r'C:\Windows\Fonts\georgiab.ttf'
F_ITAL = r'C:\Windows\Fonts\georgiai.ttf'

CW_PT  = 112 * 2.83465          # largura util do texto (112mm em pt)
FIRST_AVAIL = 505.0             # altura util pagina 3 (apos cabecalho)
NEXT_AVAIL  = 505.0             # altura util demais paginas
LEADING = 1.6

MD_CONV = markdown.Markdown(extensions=['extra'])


# ------------------------------------------------------------------ parsing
def parse_frontmatter(text):
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ':' in line:
            k, v = line.split(':', 1)
            meta[k.strip().lower()] = v.strip()
    return meta, text[m.end():]


def split_sections(body):
    sections, cur = {}, None
    for raw in body.splitlines():
        if raw.startswith('## '):
            cur = raw[3:].strip().lower()
            sections.setdefault(cur, [])
        elif cur is not None:
            sections[cur].append(raw)
    return {k: '\n'.join(v) for k, v in sections.items()}


def split_parts(text):
    """Separa o conto em blocos: por '### Título' ou por linhas ---/***/___."""
    parts, cur = [], None
    for raw in text.splitlines():
        s = raw.strip()
        if s.startswith('### '):
            cur = s[4:]
            parts.append([cur, []])
        elif s in ('---', '***', '___'):
            cur = ''
            parts.append(['', []])
        elif cur is None:
            cur = ''
            parts.append(['', []])
            parts[-1][1].append(raw)
        else:
            parts[-1][1].append(raw)
    return [(t, '\n'.join(b)) for t, b in parts]


def blocks(text):
    """blocos separados por linha em branco (mantem comentarios HTML)."""
    return [b.strip() for b in re.split(r'\n\s*\n', text.strip()) if b.strip()]


def conv(block):
    """markdown -> html do bloco. ('image', html) para imagens, ('skip', '') para ignorar."""
    html = MD_CONV.reset().convert(block).strip()
    if html in ('<hr />', '<hr>') or html.startswith('<blockquote>'):
        return ('skip', '')
    if html.startswith('<p><img') and html.endswith('</p>'):
        return ('image', html[3:-4])
    return ('text', html)


def img_src(html):
    m = re.search(r'src="([^"]+)"', html)
    return m.group(1) if m else None


# ------------------------------------------------------------------ medicao
def para_height(text, size, bold=False):
    font = ImageFont.truetype(F_BOLD if bold else F_REG, int(size * 4))
    lines, cur = 1, ''
    for w in text.split():
        trial = (cur + ' ' + w).strip()
        if font.getlength(trial) / 4.0 <= CW_PT:
            cur = trial
        else:
            lines += 1
            cur = w
    return lines * size * LEADING + size * 0.6


def paginate(paras):
    """paras: lista de (html, texto_medir, size, bold). Pagina sem cortar paragrafo."""
    pages, cur_h, avail = [[]], 0.0, FIRST_AVAIL
    for html, meas, size, bold in paras:
        h = para_height(meas, size, bold)
        if cur_h + h > avail:
            pages.append([])
            cur_h, avail = 0.0, NEXT_AVAIL
        pages[-1].append(html)
        cur_h += h
    return pages


# ------------------------------------------------------------------ CSS fixo
CSS = """
@page { size: 148mm 210mm; margin: 0; }
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: Georgia, 'Times New Roman', serif; background: #e9e4da; }
.page { width: 148mm; height: 210mm; background: #f8f2e6; position: relative;
        overflow: hidden; page-break-after: always; margin: 0 auto 4mm; }
.page-inner { padding: 14mm 18mm 16mm; height: 100%; }
.ink { color: #29201a; } .red { color: #94241f; }
.gold { color: #b3923f; }
.title-line { text-align: center; font-weight: bold; color: #29201a; }
.title-line.big { font-size: 28pt; line-height: 1.22; }
.title-line.med { font-size: 22pt; line-height: 1.25; }
.author-small { text-align: center; font-size: 11pt; }
.rule { border: none; border-top: 1.2pt solid #b3923f; width: 42%; margin: 4mm auto; }
.rule.short { width: 22%; margin: 2.5mm auto; }
.heading { text-align: center; font-weight: bold; font-size: 14pt; letter-spacing: 1pt; }
.heading.big { font-size: 16pt; }
.sc { font-variant-caps: small-caps; }
.body-text { font-size: 11pt; line-height: 1.6; text-align: justify; orphans: 3; widows: 3; }
.body-text.center { text-align: center; }
.dropcap::first-letter { initial-letter: 2; color: #94241f; font-weight: bold;
                         margin-right: 2mm; }
.signature { text-align: center; font-style: italic; font-size: 12pt; }
.fim { text-align: center; color: #94241f; font-size: 11pt; margin-top: 8mm; }
.page-num { position: absolute; bottom: 6mm; width: 100%; text-align: center;
            font-style: italic; font-size: 8.5pt; color: #8a7f80; letter-spacing: 2pt; }
.frame { border: 1.5pt solid #b3923f; padding: 2mm; }
.frame-inner { display: block; border: 0.6pt solid #b3923f; padding: 1.5mm; }
.foto-place { border: 1.5pt solid #b3923f; color: #9a8f80; font-style: italic;
              display: flex; align-items: center; justify-content: center; }
.band-top { position: absolute; top: 0; left: 0; width: 100%; height: 3mm; background: #94241f; }
.band-bottom { position: absolute; bottom: 0; left: 0; width: 100%; height: 3mm; background: #94241f; }
.content img { max-width: 95mm; display: block; margin: 0 auto; }
.content p { font-size: 11pt; line-height: 1.6; text-align: justify; margin: 0 0 4.5mm 0; orphans: 3; widows: 3; }
.content .heading { text-align: center; }
.conto-content p { font-size: 13pt; line-height: 1.65; }
.content .imgwrap { text-align: center; }
.orn { display: block; margin: 3mm auto; }
"""


# ------------------------------------------------------------------ paginas
def orn(color='#b3923f'):
    return (f'<svg class="orn" width="30mm" height="5mm" viewBox="0 0 120 20">'
            f'<line x1="4" y1="10" x2="46" y2="10" stroke="{color}" stroke-width="1.2"/>'
            f'<circle cx="60" cy="10" r="2.4" fill="{color}"/>'
            f'<line x1="74" y1="10" x2="116" y2="10" stroke="{color}" stroke-width="1.2"/>'
            f'</svg>')


def split_title(titulo):
    """Divide o título em duas linhas balanceadas (corte mais próximo do meio)."""
    words = (titulo or '').split()
    if not words:
        return '', ''
    if len(words) == 1:
        return words[0], ''
    best = 1
    best_cost = None
    for k in range(1, len(words)):
        l1 = len(' '.join(words[:k]))
        l2 = len(' '.join(words[k:]))
        cost = abs(l1 - l2)
        if best_cost is None or cost < best_cost:
            best_cost, best = cost, k
    return ' '.join(words[:best]), ' '.join(words[best:])


def page_capa(m):
    t1, t2 = split_title(m.get('titulo', ''))
    return f"""
<div class="page cream">
  <div class="band-top"></div><div class="band-bottom"></div>
  <div class="page-inner">
    <p class="author-small red" style="margin-top:2mm">{m['autora']}</p>
    {orn()}
    <p class="title-line big">{t1}<br>{t2}</p>
    <hr class="rule short">
    <div style="text-align:center; margin:6mm 0">
      <span class="frame" style="display:inline-block">
        <span class="frame-inner">
          <img src="{m['foto_capa']}" style="width:82mm; display:block" alt="capa">
        </span>
      </span>
    </div>
    <hr class="rule">
    <p class="subtitle" style="text-align:center; font-style:italic; color:#6b6157; font-size:10.5pt">{m['local']}</p>
    <p class="subtitle" style="text-align:center; font-size:9.5pt; margin-top:1mm; color:#6b6157">Projeto editorial</p>
  </div>
</div>"""


def page_rosto(m, num):
    t1, t2 = split_title(m.get('titulo', ''))
    return f"""
<div class="page cream">
  <div class="page-inner" style="display:flex; flex-direction:column">
    <div style="flex:1"></div>
    <p class="title-line med">{t1}<br>{t2}</p>
    <hr class="rule">
    <p class="author-small red" style="font-size:13pt">{m['autora']}</p>
    <p class="subtitle" style="text-align:center; font-style:italic; color:#6b6157; font-size:10.5pt; margin-top:1.5mm">{m['local']}</p>
    <div style="flex:1"></div>
    <div style="border-top:0.6pt solid #b3923f; padding-top:3mm">
      <p class="body-text center" style="font-size:8.5pt; line-height:1.6; color:#6b6157; margin:0 0 6mm 0">
        <span class="sc">Capa</span><br>{m['capa']}
      </p>
      <p class="body-text center" style="font-size:8.5pt; line-height:1.6; color:#6b6157; margin:0 0 6mm 0">
        <span class="sc">Acompanhamento Pedagógico</span><br>{m['pedagogico']}
      </p>
      <p class="body-text center" style="font-size:8.5pt; color:#6b6157">
        Projeto editorial &ndash; {m['local']} &middot; {m['ano']}
      </p>
    </div>
  </div>
  <span class="page-num">&middot; {num} &middot;</span>
</div>"""


def page_apresentacao(page_htmls):
    return """
<div class="page cream">
  <div class="page-inner"><div class="content">%s</div></div>
  <span class="page-num">&middot; {num} &middot;</span>
</div>""" % '\n'.join(page_htmls)


def page_conto(content, num=None):
    num_html = f'<span class="page-num">&middot; {num} &middot;</span>' if num else ''
    return f"""
<div class="page cream">
  <div class="page-inner" style="display:flex; flex-direction:column; justify-content:center">
    <div class="content conto-content" style="width:100%">{content}</div>
  </div>
  {num_html}
</div>"""


def page_sobre(bio_html, foto_html):
    return f"""
<div class="page cream">
  <div class="page-inner">
    <p class="heading red big sc">Sobre a autora</p>
    <hr class="rule" style="width:34%">
    {foto_html}
    <div class="content" style="margin-top:6mm">{bio_html}</div>
  </div>
  <span class="page-num">&middot; {{num}} &middot;</span>
</div>"""


def page_contracapa(m):
    t1, t2 = split_title(m.get('titulo', ''))
    credits = (f'<p style="margin:0 0 6mm 0"><span class="sc">Capa</span><br>{m["capa"]}</p>'
               f'<p style="margin:0"><span class="sc">Acompanhamento Pedagógico</span><br>{m["pedagogico"]}</p>')
    return f"""
<div class="page" style="background:#94241f">
  <div class="page-inner" style="display:flex; flex-direction:column; align-items:center; justify-content:center">
    <p class="title-line" style="font-size:20pt; color:#ffffff">{t1}<br>{t2}</p>
    <hr class="rule">
    <p class="author-small" style="color:#fdf6f2">{m['autora']}</p>
    {orn('#b3923f')}
    <div class="body-text center" style="color:#f6e7e0; font-size:9.5pt; margin-top:4mm">{credits}</div>
    <p class="subtitle" style="color:#e9d2c8; font-size:9pt; margin-top:10mm; text-align:center; font-style:italic">{m['local']} &middot; {m['ano']}</p>
  </div>
</div>"""


# ------------------------------------------------------------------ main
def main():
    raw = io.open(MD, encoding='utf-8').read()
    meta, body = parse_frontmatter(raw)
    sections = split_sections(body)

    pages = []
    pages.append(page_capa(meta))                       # 1 capa
    pages.append(page_rosto(meta, 2))                   # 2 rosto+ficha

    # ---- apresentacao (pagina 3 em diante, fluxo automatico)
    apres = sections.get('apresentação', sections.get('apresentacao', ''))
    aps = blocks(apres)
    paras = []
    heading_html = None
    for b in aps:
        if b.startswith('<!--'):
            continue
        kind, html = conv(b)
        if kind == 'text':
            mstrong = re.match(r'^<p><strong>(.*?)</strong></p>$', html, re.S)
            text = re.sub(r'<[^>]+>', '', html)
            if mstrong:
                heading_html = f'{orn()}<p class="heading red sc">{mstrong.group(1)}</p>\n<hr class="rule" style="width:30%">'
                continue
            paras.append((html, text, 11, False))
    if meta.get('pedagogico'):
        paras.append((f'<p class="signature red">{meta["pedagogico"]}</p>',
                      meta['pedagogico'], 12, False))
    # pagina 1 da apresentacao recebe cabecalho
    pages_html = paginate(paras)
    for i, ph in enumerate(pages_html):
        if i == 0 and heading_html:
            ph = [heading_html] + ph
        pages.append(page_apresentacao(ph).replace('{num}', str(3 + i)))

    # ---- conto (cada ### = uma pagina)
    conto = sections.get('conto', '')
    parts = split_parts(conto)
    conto_pages = []
    for idx, (title, content) in enumerate(parts):
        html_parts = []
        first_text = True
        for b in blocks(content):
            if b.startswith('<!--'):
                continue
            kind, html = conv(b)
            if kind == 'skip':
                continue
            if kind == 'image':
                html_parts.append(f'<div class="imgwrap">{html}</div>')
            elif kind == 'text':
                if idx == 0 and first_text and html.startswith('<p>'):
                    html = '<p class="dropcap">' + html[3:]
                    first_text = False
                html_parts.append(html)
        conto_pages.append((idx, '\n'.join(html_parts)))
    for idx, html in conto_pages:
        num = 3 + len(pages_html) + idx
        pages.append(page_conto(html, num=num))

    # ---- sobre a autora
    sobre = sections.get('sobre a autora', sections.get('sobre', ''))
    bio_parts, foto_html = [], None
    for b in blocks(sobre):
        kind, html = conv(b)
        if kind == 'skip':
            continue
        if kind == 'image':
            src = img_src(html)
            foto_html = (f'<div style="text-align:center; margin-top:8mm">'
                         f'<span class="frame" style="display:inline-block">'
                         f'<img src="{src}" style="width:70mm; display:block" alt="foto"></span></div>')
            continue
        bio_parts.append(html)
    if foto_html is None:
        foto_html = '<div class="foto-place" style="height:32mm; margin-top:10mm">espaço para foto</div>'
    pages.append(page_sobre('\n'.join(bio_parts), foto_html).replace('{num}', str(len(pages) + 1)))

    # ---- contracapa (créditos vêm do front matter)
    pages.append(page_contracapa(meta))

    html_doc = (f'<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
                f'<title>Booklet A5</title><style>{CSS}</style></head><body>'
                + ''.join(pages) + '</body></html>')

    with io.open(BUILD, 'w', encoding='utf-8') as f:
        f.write(html_doc)

    edge = next((p for p in [
        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files\Google\Chrome\Application\chrome.exe'] if os.path.exists(p)), None)
    if not edge:
        sys.exit('Edge/Chrome nao encontrado.')

    profile = os.path.join(os.environ['TEMP'], 'edge_booklet_' + os.urandom(4).hex())
    if os.path.exists(OUT):
        os.remove(OUT)
    uri = 'file:///' + BUILD.replace('\\', '/')
    cmd = [edge, '--headless=new', '--disable-gpu', '--no-pdf-header-footer',
           '--user-data-dir=' + profile, '--print-to-pdf=' + OUT, uri]
    subprocess.run(cmd, capture_output=True)
    for p in [BUILD, profile]:
        if os.path.isdir(p):
            import shutil
            shutil.rmtree(p, ignore_errors=True)
        elif os.path.exists(p):
            os.remove(p)
    if os.path.exists(OUT):
        print('OK ->', OUT)
    else:
        sys.exit('Falha ao gerar PDF.')


if __name__ == '__main__':
    main()