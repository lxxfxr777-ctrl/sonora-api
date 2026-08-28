"""
Fuerza a que TODAS las conexiones salientes hechas con `socket`/`urllib`
en este proceso usen únicamente IPv4.

Por qué existe esto:
Render (y muchos hosts de contenedores) no tienen ruta de salida IPv6
configurada, pero el DNS de muchos hosts (instancias Piped, CDN de
Google/YouTube, Invidious, Cobalt, etc.) sigue devolviendo un registro
AAAA. Python, por defecto, intenta conectar usando la PRIMERA dirección
que devuelve `getaddrinfo`, que en muchos resolutores es la IPv6.
Como no hay ruta, el `connect()` falla inmediatamente con:

    OSError: [Errno 101] Network is unreachable

...y como el fallo es instantáneo (no es un timeout), se repite muy
rápido para cada instancia/host de la lista de fallback, dando la
apariencia de que "todos" los servidores están caídos cuando en
realidad ninguno fue alcanzado nunca por IPv4.

Importar este módulo (una sola vez, al inicio del proceso, antes de
cualquier otro import que abra sockets) parchea `socket.getaddrinfo`
para que sólo devuelva resultados IPv4 (AF_INET), evitando el problema
por completo sin tener que tocar cada llamada a `urlopen`.
"""

from __future__ import annotations

import socket

_original_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    # Si alguien pide explícitamente IPv6, respetamos esa intención;
    # en cualquier otro caso (el 99% de los casos, family=0/AF_UNSPEC),
    # forzamos IPv4.
    if family in (0, socket.AF_UNSPEC):
        family = socket.AF_INET
    return _original_getaddrinfo(host, port, family, type, proto, flags)


def patch() -> None:
    """Aplica el parche de forma idempotente (seguro llamarlo más de una vez)."""
    if socket.getaddrinfo is not _ipv4_only_getaddrinfo:
        socket.getaddrinfo = _ipv4_only_getaddrinfo
        print("=== SONORA: net_ipv4 patch aplicado (DNS forzado a IPv4) ===", flush=True)


# Aplicar automáticamente con sólo importar el módulo.
patch()
