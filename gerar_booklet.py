# -*- coding: utf-8 -*-
# Gera o booklet A5 a partir do template_booklet.md (layout fixo).
# Suporta flexibilidade de gênero, coautoria e consolidação de créditos.
# Uso: python gerar_booklet.py
import io
import os
import re
import shutil
import subprocess
import sys
import html

import markdown
from PIL import ImageFont

BASE   = os.path.dirname(os.path.abspath(__file__))
MD     = os.path.join(BASE, 'template_booklet.md')
OUT    = os.path.join(BASE, 'booklet_A5.pdf')

F_REG  = r'C:\Windows\Fonts\georgia.ttf'
F_BOLD = r'C:\Windows\Fonts\georgiab.ttf'

CW_PT  = 112 * 2.83465          # largura util do texto (112mm em pt)
FIRST_AVAIL = 445.0             # altura util pagina 3 (apos cabecalho)
NEXT_AVAIL  = 505.0             # altura util demais paginas
LEADING = 1.6

MD_CONV = markdown.Markdown(extensions=['extra'])


# ------------------------------------------------------------------ parsing
def parse_frontmatter(text):
    text = text.lstrip('\ufeff').replace('\r\n', '\n')
    m = re.match(r'^---\s*\n(.*?)\n---\s*(?:\n|$)', text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        if ':' in s:
            k, v = s.split(':', 1)
            meta[k.strip().lower()] = v.strip()
    return meta, text[m.end():]


def normalize_meta(raw_meta):
    """Garante chaves canônicas com suporte a autora/autor/autoras/autores."""
    meta = dict(raw_meta)
    autores_val = (
        meta.get('autores') or meta.get('autoras') or
        meta.get('autora') or meta.get('autor') or ''
    )
    meta['autores_str'] = autores_val
    meta['autora'] = autores_val

    for k in ('titulo', 'local', 'ano', 'pedagogico', 'escola'):
        meta.setdefault(k, '')

    if not meta.get('foto_capa'):
        meta['foto_capa'] = 'ilustracoes/foto_capa.png'

    return meta


def infer_gen(nome, fallback='f'):
    s = (nome or '').lower()
    if 'autora' in s or 'ilustradora' in s:
        return 'f'
    if 'autor' in s or 'ilustrador' in s:
        return 'm'
    return fallback


def parse_subheading(raw_heading, fallback_gen='f', is_mixed_capable=True):
    gm = re.search(r'<!--\s*([♀♂])\s*-->', raw_heading)
    clean = re.sub(r'<!--\s*[♀♂]\s*-->', '', raw_heading).strip()
    if gm:
        gen = 'f' if gm.group(1) == '♀' else 'm'
    elif is_mixed_capable:
        gen = infer_gen(clean, fallback_gen)
    else:
        gen = fallback_gen
    return clean, gen


def split_sections(body):
    """Retorna dicionário {chave_minuscula: (titulo_original, conteudo)}."""
    body = re.sub(r'<!--(?![\s]*[♀♂][\s]*-->).*?-->', '', body, flags=re.S)
    sections, cur, cur_raw = {}, None, ''
    for raw in body.splitlines():
        if raw.startswith('## '):
            cur_raw = raw[3:].strip()
            cur = cur_raw.lower()
            sections.setdefault(cur, (cur_raw, []))
        elif cur is not None:
            sections[cur][1].append(raw)
    return {k: (v[0], '\n'.join(v[1])) for k, v in sections.items()}


def find_section(sections, *patterns):
    """Busca a primeira seção cujo título coincida ou comece com algum dos padrões."""
    for pat in patterns:
        pat_l = pat.lower()
        if pat_l in sections:
            return sections[pat_l]
        for k, (raw_title, content) in sections.items():
            if k.startswith(pat_l):
                return (raw_title, content)
    return ('', '')


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
            if not s:
                continue
            cur = ''
            parts.append(['', []])
            parts[-1][1].append(raw)
        else:
            parts[-1][1].append(raw)
    return [(t, '\n'.join(b).strip()) for t, b in parts if t or '\n'.join(b).strip()]


def blocks(text):
    """blocos separados por linha em branco (imagens isoladas sempre formam bloco próprio)."""
    text = re.sub(r'(?m)^(\s*!\[[^\]]*\]\([^)]+\)\s*)$', r'\n\n\1\n\n', text)
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
_FONTS = {}


def para_height(text, size, bold=False):
    key = (bold, int(size * 4))
    if key not in _FONTS:
        _FONTS[key] = ImageFont.truetype(F_BOLD if bold else F_REG, key[1])
    font = _FONTS[key]
    lines, cur = 1, ''
    for w in text.split():
        trial = (cur + ' ' + w).strip()
        if font.getlength(trial) / 4.0 <= CW_PT:
            cur = trial
        else:
            lines += 1
            cur = w
    return lines * size * LEADING + size * 0.6


def paginate(paras, has_heading=True):
    """paras: lista de (html, texto_medir, size, bold). Pagina sem cortar paragrafo."""
    pages, cur_h, avail = [[]], 0.0, (FIRST_AVAIL if has_heading else NEXT_AVAIL)
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
* { margin: 0; padding: 0; box-sizing: border-box;
    -webkit-print-color-adjust: exact; print-color-adjust: exact; }
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
.cover-author { text-align: center; font-size: 15pt; font-variant-caps: small-caps;
                letter-spacing: 0.5pt; color: #94241f; margin-top: 6mm; }
.rule { border: none; border-top: 1.2pt solid #b3923f; width: 42%; margin: 4mm auto; }
.rule.short { width: 22%; margin: 2.5mm auto; }
.heading { text-align: center; font-weight: bold; font-size: 14pt; letter-spacing: 1pt; }
.heading.big { font-size: 16pt; }
.sc { font-variant-caps: small-caps; }
.body-text { font-size: 11pt; line-height: 1.6; text-align: justify; orphans: 3; widows: 3; }
.body-text.center { text-align: center; }
.dropcap { min-height: 3.3em; }
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
.ilustrador { display: flex; gap: 6mm; align-items: flex-start; margin-bottom: 8mm; }
.ilustrador .frame { flex: 0 0 auto; }
.ilustrador .txt { flex: 1; }
.ilustrador .nome { font-weight: bold; font-size: 12pt; color: #29201a; margin-bottom: 1.5mm; }
.ilustrador .funcao { font-variant-caps: small-caps; letter-spacing: 0.5pt; color: #94241f;
                      font-size: 10pt; margin: 1mm 0 2mm; }
.ilustrador .bio { font-size: 10pt; line-height: 1.55; text-align: justify; color: #29201a; }
.ilustrador .bio + .bio { margin-top: 2mm; }
.equipe-foto { display: block; margin: 0 auto; }
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


def loc_ano(m):
    return ' &middot; '.join(html.escape(m.get(k, '').strip()) for k in ('local', 'ano') if m.get(k, '').strip())


def page_capa(m):
    t1, t2 = split_title(m.get('titulo', ''))
    titulo_html = f"{html.escape(t1)}<br>{html.escape(t2)}" if t2 else html.escape(t1)
    autor_str = m.get('autores_str') or m.get('autora', '')
    foto = m.get('foto_capa', '')
    return f"""
<div class="page cream">
  <div class="band-top"></div><div class="band-bottom"></div>
  <div class="page-inner" style="display:flex; flex-direction:column">
    <p class="cover-author">{html.escape(autor_str)}</p>
    {orn()}
    <p class="title-line big" style="letter-spacing:0.5pt">{titulo_html}</p>
    <hr class="rule short">
    <div style="text-align:center; margin:7mm 0">
      <img src="{html.escape(foto, quote=True)}" style="width:92mm; display:block; margin:0 auto" alt="capa">
    </div>
    <div style="flex:1"></div>
    <hr class="rule">
    <p class="subtitle" style="text-align:center; font-style:italic; color:#6b6157; font-size:10.5pt">{loc_ano(m)}</p>
  </div>
</div>"""


def build_creditos(ilustradores, meta):
    """Créditos da folha de rosto e contracapa."""
    creditos = []
    if not ilustradores and not meta.get('capa'):
        creditos.append(('Texto e Ilustrações', meta.get('autores_str', '')))
    else:
        for il in ilustradores:
            creditos.append((il.get('funcao') or 'Ilustrações', il.get('nome', '')))
        if not creditos and meta.get('capa'):
            creditos.append(('Capa', meta['capa']))

    if meta.get('pedagogico'):
        creditos.append(('Acompanhamento Pedagógico', meta['pedagogico']))

    return creditos


def page_rosto(m, num, creditos):
    t1, t2 = split_title(m.get('titulo', ''))
    titulo_html = f"{html.escape(t1)}<br>{html.escape(t2)}" if t2 else html.escape(t1)
    autor_str = m.get('autores_str') or m.get('autora', '')
    cred_blocos = '\n'.join(
        f'<p class="body-text center" style="font-size:8.5pt; line-height:1.6; color:#6b6157; margin:0 0 6mm 0">'
        f'<span class="sc">{html.escape(label)}</span><br>{html.escape(valor)}</p>'
        for label, valor in creditos)
    return f"""
<div class="page cream">
  <div class="page-inner" style="display:flex; flex-direction:column">
    <div style="flex:1"></div>
    <p class="title-line med">{titulo_html}</p>
    <hr class="rule">
    <p class="author-small red" style="font-size:13pt">{html.escape(autor_str)}</p>
    <p class="subtitle" style="text-align:center; font-style:italic; color:#6b6157; font-size:10.5pt; margin-top:1.5mm">{html.escape(m['local'])}</p>
    <div style="flex:1"></div>
    <hr class="rule" style="width:35%; border-top-width:0.8pt">
    <div style="padding-top:2mm">
      {cred_blocos}
      <p class="body-text center" style="font-size:8.5pt; color:#6b6157">
        {loc_ano(m)}
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


def split_sobre(text, fallback_gen='f'):
    """
    Analisa a seção 'Sobre':
    Se contiver '### Nome', trata como múltiplos autores: lista de {nome, genero, foto, bio}.
    Caso contrário, retorna lista com 1 autor {nome: '', genero: fallback_gen, foto: '', bio: text}.
    """
    has_subheadings = any(line.strip().startswith('### ') for line in text.splitlines())
    if not has_subheadings:
        bio_parts, foto = [], None
        for b in blocks(text):
            kind, html_b = conv(b)
            if kind == 'skip':
                continue
            if kind == 'image':
                src = img_src(html_b)
                if not foto and src:
                    foto = src
                continue
            bio_parts.append(html_b)
        return [{
            'nome': '',
            'genero': fallback_gen,
            'foto': foto or '',
            'bio': '\n'.join(bio_parts)
        }]

    # Múltiplos autores com ### Nome
    result, cur = [], None
    for raw in text.splitlines():
        s = raw.strip()
        if s.startswith('### '):
            if cur:
                result.append(cur)
            nome, gen = parse_subheading(s[4:], fallback_gen, True)
            cur = {'nome': nome, 'genero': gen, 'foto': '', 'bio_parts': []}
        elif cur is not None:
            im = re.search(r'!\[[^\]]*\]\(([^)]+)\)', s)
            if im:
                if not cur['foto']:
                    cur['foto'] = im.group(1)
            elif not s.startswith('#'):
                cur['bio_parts'].append(s)
    if cur:
        result.append(cur)

    out = []
    for c in result:
        out.append({
            'nome': c['nome'],
            'genero': c['genero'],
            'foto': c['foto'],
            'bio': '\n'.join(c['bio_parts']).strip()
        })
    return out


def page_sobre(autores_sobre, titulo="Sobre a autora", num=None):
    num_str = f"&middot; {num} &middot;" if num else ""
    if len(autores_sobre) == 1 and not autores_sobre[0].get('nome'):
        # Formato clássico (1 pessoa)
        item = autores_sobre[0]
        if item.get('foto'):
            foto_html = (f'<div style="text-align:center; margin-top:8mm">'
                         f'<span class="frame" style="display:inline-block">'
                         f'<img src="{html.escape(item["foto"], quote=True)}" style="width:70mm; display:block" alt="foto"></span></div>')
        else:
            foto_html = '<div class="foto-place" style="height:32mm; margin-top:10mm">espaço para foto</div>'
        bio_html = item.get('bio', '')
        return f"""
<div class="page cream">
  <div class="page-inner">
    <p class="heading red big sc">{html.escape(titulo)}</p>
    <hr class="rule" style="width:34%">
    {foto_html}
    <div class="content" style="margin-top:6mm">{bio_html}</div>
  </div>
  <span class="page-num">{num_str}</span>
</div>"""
    else:
        # Formato coautoria (cartões A5 elegantes)
        blocos = []
        for aut in autores_sobre:
            bio_conv = MD_CONV.reset().convert(aut['bio']).strip()
            bio_conv = re.sub(r'<p>', '<p class="bio">', bio_conv)
            foto_src = html.escape(aut.get('foto') or 'ilustracoes/placeholder.png', quote=True)
            blocos.append(f"""
<div class="ilustrador">
  <span class="frame" style="display:inline-block">
    <img src="{foto_src}" style="width:34mm; display:block" alt="{html.escape(aut['nome'])}">
  </span>
  <div class="txt">
    <p class="nome">{html.escape(aut['nome'])}</p>
    {bio_conv}
  </div>
</div>""")
        return f"""
<div class="page cream">
  <div class="page-inner">
    <p class="heading red big sc">{html.escape(titulo)}</p>
    <hr class="rule" style="width:34%">
    <div style="margin-top:7mm">{''.join(blocos)}</div>
  </div>
  <span class="page-num">{num_str}</span>
</div>"""


def page_contracapa(m, creditos):
    t1, t2 = split_title(m.get('titulo', ''))
    titulo_html = f"{html.escape(t1)}<br>{html.escape(t2)}" if t2 else html.escape(t1)
    autor_str = m.get('autores_str') or m.get('autora', '')
    cred_html = '\n'.join(
        f'<p style="margin:0 0 6mm 0"><span class="sc">{html.escape(label)}</span><br>{html.escape(valor)}</p>'
        for label, valor in creditos)
    return f"""
<div class="page" style="background:#94241f">
  <div class="page-inner" style="display:flex; flex-direction:column; align-items:center; justify-content:center">
    <p class="title-line" style="font-size:20pt; color:#ffffff">{titulo_html}</p>
    <hr class="rule">
    <p class="author-small" style="color:#fdf6f2">{html.escape(autor_str)}</p>
    {orn('#b3923f')}
    <div class="body-text center" style="color:#f6e7e0; font-size:9.5pt; margin-top:4mm">{cred_html}</div>
    <p class="subtitle" style="color:#e9d2c8; font-size:9pt; margin-top:10mm; text-align:center; font-style:italic">{loc_ano(m)}</p>
  </div>
</div>"""


def split_ilustradores(text, fallback_gen='m', is_mixed_capable=True):
    """Seção '## Ilustradores' -> lista de {nome, genero, foto, funcao, bio}."""
    result, cur = [], None
    for raw in text.splitlines():
        s = raw.strip()
        if s.startswith('### '):
            if cur:
                result.append(cur)
            nome, gen = parse_subheading(s[4:], fallback_gen, is_mixed_capable)
            cur = {'nome': nome, 'genero': gen, 'foto': '', 'funcao': '', 'bio_parts': []}
        elif cur is not None:
            im = re.search(r'!\[[^\]]*\]\(([^)]+)\)', s)
            if im:
                cur['foto'] = im.group(1)
            elif s.startswith('**') and s.endswith('**') and len(s) > 4:
                cur['funcao'] = s[2:-2]
            elif not s.startswith('#'):
                cur['bio_parts'].append(s)
    if cur:
        result.append(cur)
    out = []
    for c in result:
        out.append({'nome': c['nome'], 'genero': c['genero'], 'foto': c['foto'],
                    'funcao': c['funcao'], 'bio': '\n'.join(c['bio_parts']).strip()})
    return out


def parse_equipe(text):
    """Seção '## A equipe' -> {grupo, simbolo, legenda}."""
    grupo = simbolo = ''
    legenda_parts = []
    for raw in text.splitlines():
        s = raw.strip()
        im = re.search(r'!\[[^\]]*\]\(([^)]+)\)', s)
        if im:
            if not grupo:
                grupo = im.group(1)
            elif not simbolo:
                simbolo = im.group(1)
        elif s and not s.startswith('#'):
            legenda_parts.append(s)
    return {'grupo': grupo, 'simbolo': simbolo, 'legenda': ' '.join(legenda_parts).strip()}


def page_ilustradores(ilustradores, titulo="Ilustradores", num=None):
    num_str = f"&middot; {num} &middot;" if num else ""
    blocos = []
    for il in ilustradores:
        bio = MD_CONV.reset().convert(il['bio']).strip()
        bio = re.sub(r'<p>', '<p class="bio">', bio)
        foto_src = html.escape(il.get('foto') or 'ilustracoes/placeholder.png', quote=True)
        blocos.append(f"""
<div class="ilustrador">
  <span class="frame" style="display:inline-block">
    <img src="{foto_src}" style="width:34mm; display:block" alt="{html.escape(il['nome'])}">
  </span>
  <div class="txt">
    <p class="nome">{html.escape(il['nome'])}</p>
    <p class="funcao">{html.escape(il['funcao'])}</p>
    {bio}
  </div>
</div>""")
    return f"""
<div class="page cream">
  <div class="page-inner">
    <p class="heading red big sc">{html.escape(titulo)}</p>
    <hr class="rule" style="width:34%">
    <div style="margin-top:7mm">{''.join(blocos)}</div>
  </div>
  <span class="page-num">{num_str}</span>
</div>"""


def page_equipe(eq, meta, num):
    default_leg = ' \u00b7 '.join(meta.get(k, '').strip() for k in ('local', 'ano') if meta.get(k, '').strip())
    legenda = eq.get('legenda') or default_leg
    escola = meta.get('escola', '')
    grupo = ('<span class="frame" style="display:inline-block">'
             f'<img src="{html.escape(eq["grupo"], quote=True)}" class="equipe-foto" style="width:88mm" alt="equipe"></span>') if eq.get('grupo') else ''
    simbolo = (f'<img src="{html.escape(eq["simbolo"], quote=True)}" style="width:32mm; display:inline-block; margin:0 auto" '
               f'alt="símbolo">') if eq.get('simbolo') else ''
    escola_html = (f'<p class="subtitle" style="text-align:center; font-size:9pt; color:#6b6157; margin-top:2mm">'
                   f'{html.escape(escola)}</p>') if escola else ''
    return f"""
<div class="page cream">
  <div class="page-inner" style="display:flex; flex-direction:column; align-items:center">
    <p class="heading red big sc">A equipe</p>
    <hr class="rule" style="width:34%">
    <div style="margin-top:7mm; text-align:center">{grupo}</div>
    <div style="flex:1"></div>
    <div style="text-align:center">{simbolo}</div>
    <p class="subtitle" style="text-align:center; font-style:italic; color:#6b6157; font-size:10.5pt; margin-top:2mm">{html.escape(legenda)}</p>
    {escola_html}
  </div>
  <span class="page-num">&middot; {num} &middot;</span>
</div>"""


PADROES_SOBRE = {
    'sobre a autora', 'sobre o autor', 'sobre os autores', 'sobre as autoras',
    'sobre a autora e ilustradora', 'sobre o autor e ilustrador',
    'sobre os autores e ilustradores', 'sobre as autoras e ilustradoras',
}


def resolve_titulos(meta_raw, autores_sobre, il, titulo_sobre, titulo_ilust, proprias):
    """Deduz os títulos das páginas Sobre e Ilustradores com concordância de gênero e número."""
    t_norm = (titulo_sobre or '').strip().lower()
    if not t_norm or t_norm in PADROES_SOBRE:
        is_plural = ('autores' in meta_raw or 'autoras' in meta_raw or
                     'autores' in t_norm or 'autoras' in t_norm or len(autores_sobre) > 1)
        all_fem = (bool(autores_sobre) and all(a.get('genero') != 'm' for a in autores_sobre) and
                   'autores' not in meta_raw and 'autores' not in t_norm)
        if is_plural:
            base = 'Sobre as autoras' if all_fem else 'Sobre os autores'
            suf = ' e ilustradoras' if all_fem else ' e ilustradores'
        else:
            base = 'Sobre a autora' if all_fem else 'Sobre o autor'
            suf = ' e ilustradora' if all_fem else ' e ilustrador'
        titulo_sobre = base + suf if proprias else base

    il_norm = (titulo_ilust or '').strip().lower()
    if not il_norm or il_norm in ('ilustrador', 'ilustradora', 'ilustradores', 'ilustradoras'):
        all_il_fem = bool(il) and all(x.get('genero') == 'f' for x in il)
        if len(il) == 1:
            titulo_ilust = 'Ilustradora' if all_il_fem else 'Ilustrador'
        else:
            titulo_ilust = 'Ilustradoras' if all_il_fem else 'Ilustradores'

    return titulo_sobre, titulo_ilust


# ------------------------------------------------------------------ main
def main():
    md_path = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else MD
    out_path = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else OUT
    if not os.path.exists(md_path):
        sys.exit(f'Arquivo Markdown nao encontrado: {md_path}')
    raw = io.open(md_path, encoding='utf-8-sig').read()
    meta_raw, body = parse_frontmatter(raw)
    meta = normalize_meta(meta_raw)
    sections = split_sections(body)

    pages = []

    # Localização inteligente de seções
    _, apres = find_section(sections, 'apresentação', 'apresentacao')
    _, conto = find_section(sections, 'conto')
    titulo_sobre, sobre_raw = find_section(sections, 'sobre a autora', 'sobre o autor', 'sobre os autores', 'sobre as autoras', 'sobre a autoria', 'sobre quem', 'sobre')
    titulo_ilust, il_raw = find_section(sections, 'ilustradores', 'ilustradoras', 'ilustrações', 'ilustracao', 'ilustra')
    _, equipe_sec = find_section(sections, 'a equipe', 'equipe')

    # Ilustradores e autores sobre parseados
    il_norm = titulo_ilust.strip().lower()
    def_il_gen = 'f' if il_norm in ('ilustradora', 'ilustradoras') else 'm'
    is_il_mixed_capable = il_norm not in ('ilustradora', 'ilustradoras', 'ilustrador')
    il = split_ilustradores(il_raw, fallback_gen=def_il_gen, is_mixed_capable=is_il_mixed_capable)

    t_norm = titulo_sobre.strip().lower()
    def_aut_gen = 'm' if (('autor' in meta_raw and 'autora' not in meta_raw) or 'autores' in meta_raw or ('autor' in t_norm and 'autora' not in t_norm)) else 'f'
    autores_sobre = split_sobre(sobre_raw, fallback_gen=def_aut_gen)

    if not meta.get('autores_str'):
        nomes_co = [a['nome'] for a in autores_sobre if a.get('nome')]
        if nomes_co:
            nomes_fmt = nomes_co[0] if len(nomes_co) == 1 else ', '.join(nomes_co[:-1]) + ' e ' + nomes_co[-1]
            meta['autores_str'] = meta['autora'] = nomes_fmt

    proprias = not il and not meta.get('capa')
    creditos = build_creditos(il, meta)
    titulo_sobre, titulo_ilust = resolve_titulos(meta_raw, autores_sobre, il, titulo_sobre, titulo_ilust, proprias)

    pages.append(page_capa(meta))                       # 1 capa
    pages.append(page_rosto(meta, 2, creditos))         # 2 rosto+ficha

    # ---- apresentacao (pagina 3 em diante, fluxo automatico)
    aps = blocks(apres)
    paras = []
    heading_html = None
    for b in aps:
        kind, html_b = conv(b)
        if kind == 'text':
            mstrong = re.match(r'^<p><strong>(.*?)</strong></p>$', html_b, re.S)
            text = re.sub(r'<[^>]+>', '', html_b)
            if mstrong and heading_html is None and not paras:
                heading_html = f'{orn()}<p class="heading red sc">{mstrong.group(1)}</p>\n<hr class="rule" style="width:30%">'
                continue
            paras.append((html_b, text, 11, False))
    if meta.get('pedagogico'):
        paras.append((f'<p class="signature red">{html.escape(meta["pedagogico"])}</p>',
                      meta['pedagogico'], 12, False))
    # pagina 1 da apresentacao recebe cabecalho (omite pagina se totalmente vazia)
    if heading_html or paras:
        pages_html = paginate(paras, has_heading=bool(heading_html))
        for i, ph in enumerate(pages_html):
            if i == 0 and heading_html:
                ph = [heading_html] + ph
            pages.append(page_apresentacao(ph).replace('{num}', str(3 + i)))
    else:
        pages_html = []

    # ---- conto (cada ### = uma pagina)
    parts = split_parts(conto)
    conto_pages = []
    for idx, (title, content) in enumerate(parts):
        html_parts = []
        first_text = True
        for b in blocks(content):
            kind, html_b = conv(b)
            if kind == 'skip':
                continue
            if kind == 'image':
                html_parts.append(f'<div class="imgwrap">{html_b}</div>')
            elif kind == 'text':
                if idx == 0 and first_text and html_b.startswith('<p>'):
                    html_b = '<p class="dropcap">' + html_b[3:]
                    first_text = False
                html_parts.append(html_b)
        conto_pages.append((idx, '\n'.join(html_parts)))
    for idx, html_p in conto_pages:
        num = 3 + len(pages_html) + idx
        pages.append(page_conto(html_p, num=num))

    # ---- sobre
    pages.append(page_sobre(autores_sobre, titulo=titulo_sobre, num=len(pages) + 1))

    # ---- ilustradores (apenas se houver ilustradores externos)
    if il:
        pages.append(page_ilustradores(il, titulo=titulo_ilust, num=len(pages) + 1))

    # ---- a equipe
    eq = parse_equipe(equipe_sec)
    if eq.get('grupo') or eq.get('simbolo'):
        pages.append(page_equipe(eq, meta, len(pages) + 1))

    # ---- contracapa
    pages.append(page_contracapa(meta, creditos))

    md_dir = os.path.dirname(md_path)
    asset_dir = md_dir if os.path.isdir(os.path.join(md_dir, 'ilustracoes')) else BASE
    base_href = 'file:///' + asset_dir.replace('\\', '/').rstrip('/') + '/'
    html_doc = (f'<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
                f'<base href="{html.escape(base_href, quote=True)}">'
                f'<title>Booklet A5</title><style>{CSS}</style></head><body>'
                + ''.join(pages) + '</body></html>')

    edge = next((p for p in [
        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files\Google\Chrome\Application\chrome.exe'] if os.path.exists(p)), None)
    if not edge:
        sys.exit('Edge/Chrome nao encontrado.')

    tmp_dir = os.environ.get('TEMP', BASE)
    run_id = os.urandom(4).hex()
    profile = os.path.join(tmp_dir, 'edge_booklet_' + run_id)
    build_html = os.path.join(tmp_dir, f'_build_{run_id}.html')
    try:
        with io.open(build_html, 'w', encoding='utf-8') as f:
            f.write(html_doc)
        if os.path.exists(out_path):
            os.remove(out_path)
        uri = 'file:///' + build_html.replace('\\', '/')
        cmd = [edge, '--headless=new', '--disable-gpu', '--no-pdf-header-footer',
               '--user-data-dir=' + profile, '--print-to-pdf=' + out_path, uri]
        res = subprocess.run(cmd, capture_output=True, text=True)
    finally:
        for p in [build_html, profile]:
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            elif os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
    if os.path.exists(out_path):
        print('OK ->', out_path)
    else:
        sys.exit(f"Falha ao gerar PDF. {(res.stderr or '').strip()}")


if __name__ == '__main__':
    main()
