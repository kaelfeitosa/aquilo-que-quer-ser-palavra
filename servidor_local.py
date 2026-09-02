# -*- coding: utf-8 -*-
"""Servidor local para acessar o booklet_editor.html na rede local.
HTTP em :8000 e HTTPS em :8443 (cert autoassinado -> permite o histórico/IndexedDB).
Uso: python servidor_local.py
"""
import functools
import http.server
import io
import os
import socket
import ssl
import sys
import threading

BASE = os.path.dirname(os.path.abspath(__file__))
CERT_DIR = os.path.join(BASE, 'certs')
CERT = os.path.join(CERT_DIR, 'server.pem')
KEY = os.path.join(CERT_DIR, 'key.pem')
CA_CERT = os.path.join(CERT_DIR, 'ca.crt')
IP_FILE = os.path.join(CERT_DIR, 'ips.txt')
HTTP_PORT = 8000
HTTPS_PORT = 8443


def local_ips():
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith('127.'):
                ips.add(ip)
    except OSError:
        pass
    return sorted(ips)


def ensure_cert():
    import trustme
    os.makedirs(CERT_DIR, exist_ok=True)
    ips = local_ips()
    stale = True
    if os.path.exists(IP_FILE):
        try:
            stale = io.open(IP_FILE, encoding='utf-8').read().strip() != ','.join(ips)
        except OSError:
            stale = True
    if os.path.exists(CERT) and os.path.exists(KEY) and os.path.exists(CA_CERT) and not stale:
        return
    names = ips + ['localhost']
    ca = trustme.CA()
    server = ca.issue_cert(*names)
    server.cert_chain_pems[0].write_to_path(CERT)
    server.private_key_pem.write_to_path(KEY)
    ca.cert_pem.write_to_path(CA_CERT)
    io.open(IP_FILE, 'w', encoding='utf-8').write(','.join(ips))


class BookletHandler(http.server.SimpleHTTPRequestHandler):
    """Serva o editor e as ilustrações, mas bloqueia certs/ e arquivos sensíveis."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE, **kwargs)

    def _blocked(self):
        p = self.path.split('?', 1)[0]
        low = p.lower()
        if p.startswith('/certs/') or p == '/certs':
            return True
        if low.endswith('.pem') or low.endswith('.crt') or low.endswith('.key') or low.endswith('.py'):
            return True
        return False

    def do_GET(self):
        if self._blocked():
            self.send_error(404, 'Não encontrado')
            return
        super().do_GET()

    def do_HEAD(self):
        if self._blocked():
            self.send_error(404, 'Não encontrado')
            return
        super().do_HEAD()


def make_server(port, use_https):
    handler = BookletHandler
    httpd = http.server.ThreadingHTTPServer(('0.0.0.0', port), handler)
    if use_https:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(CERT, KEY)
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    return httpd


def main():
    ips = local_ips()
    ensure_cert()
    try:
        s1 = make_server(HTTP_PORT, False)
        s2 = make_server(HTTPS_PORT, True)
    except OSError as e:
        print(f'ERRO: não foi possível abrir as portas {HTTP_PORT}/{HTTPS_PORT}: {e}')
        print('Verifique se o servidor já não está rodando (execute apenas uma vez).')
        sys.exit(1)
    threading.Thread(target=s1.serve_forever, daemon=True).start()
    threading.Thread(target=s2.serve_forever, daemon=True).start()
    print('Servidor local do Booklet A5 ativo.')
    print()
    for ip in ips or ['SEU_IP']:
        print(f'  HTTP :  http://{ip}:{HTTP_PORT}/')
        print(f'  HTTPS:  https://{ip}:{HTTPS_PORT}/')
    print()
    print('HTTPS usa certificado autoassinado: o navegador avisa -> "Avançar/Continuar".')
    print('O histórico/IndexedDB só funciona em HTTPS (ou localhost).')
    print('Pressione Ctrl+C para encerrar.')
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print('\nEncerrado.')
        sys.exit(0)


if __name__ == '__main__':
    main()