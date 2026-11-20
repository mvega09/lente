"""Lee una noticia desde su enlace y extrae solo el texto del artículo (RF-09).

Así el profesor puede cargar una noticia pegando el enlace, sin copiar el texto.

Protección contra SSRF: el servidor solo abre direcciones PÚBLICAS de internet.
Un enlace hacia la red interna (la base de datos, Ollama, 127.0.0.1, 10.x…) se
rechaza, también si llega por una redirección. Además hay límite de tiempo, de
tamaño y de redirecciones.
"""

import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx
import trafilatura

TIEMPO_MAXIMO_S = 15
MAX_BYTES = 3_000_000
MAX_REDIRECCIONES = 5
MIN_CARACTERES = 300       # menos que esto suele ser un muro de pago o una página sin artículo
MAX_CARACTERES = 15_000    # una noticia larga; más alargaría mucho la preparación con IA
AGENTE = "Mozilla/5.0 (compatible; LENTE/1.0; herramienta educativa de la Universidad de Manizales)"


class NoSePudoLeer(Exception):
    """El enlace no se pudo abrir o no tiene un artículo legible."""

    def __init__(self, mensaje: str):
        super().__init__(mensaje)
        self.mensaje = mensaje


async def validar_destino(url: str) -> None:
    """Solo http/https hacia direcciones públicas (nunca la red interna)."""
    partes = urlsplit(url)
    if partes.scheme not in ("http", "https") or not partes.hostname:
        raise NoSePudoLeer("el enlace debe empezar por http:// o https://")
    if partes.username or partes.password:
        raise NoSePudoLeer("el enlace no puede llevar usuario ni contraseña")
    puerto = partes.port or (443 if partes.scheme == "https" else 80)
    try:
        direcciones = await asyncio.get_running_loop().getaddrinfo(partes.hostname, puerto, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise NoSePudoLeer("no se encontró el sitio web del enlace") from None
    for *_, destino in direcciones:
        ip = ipaddress.ip_address(destino[0])
        if not ip.is_global:
            raise NoSePudoLeer("el enlace apunta a una dirección interna; solo se aceptan sitios públicos")


async def descargar(url: str, transport: httpx.AsyncBaseTransport | None = None) -> bytes:
    """Descarga la página validando cada redirección. `transport` es solo para las pruebas."""
    encabezados = {"User-Agent": AGENTE, "Accept": "text/html,application/xhtml+xml"}
    async with httpx.AsyncClient(timeout=TIEMPO_MAXIMO_S, follow_redirects=False,
                                 headers=encabezados, transport=transport) as cliente:
        for _ in range(MAX_REDIRECCIONES + 1):
            await validar_destino(url)
            try:
                async with cliente.stream("GET", url) as r:
                    if r.is_redirect:
                        url = urljoin(url, r.headers.get("location", ""))
                        continue
                    if r.status_code != 200:
                        raise NoSePudoLeer(f"la página respondió con el código {r.status_code}")
                    if "html" not in r.headers.get("content-type", "html"):
                        raise NoSePudoLeer("el enlace no es una página web (¿es un PDF o una imagen?)")
                    contenido = bytearray()
                    async for trozo in r.aiter_bytes():
                        contenido += trozo
                        if len(contenido) > MAX_BYTES:
                            raise NoSePudoLeer("la página es demasiado grande")
                    return bytes(contenido)
            except httpx.TimeoutException:
                raise NoSePudoLeer(f"la página no respondió en {TIEMPO_MAXIMO_S} segundos") from None
            except httpx.HTTPError:
                raise NoSePudoLeer("no se pudo conectar con el sitio web") from None
    raise NoSePudoLeer("el enlace redirige demasiadas veces")


def extraer(html: bytes | str) -> str:
    """Solo el artículo: sin menús, publicidad ni comentarios. Párrafos separados por una
    línea en blanco, como los espera el frontend."""
    texto = trafilatura.extract(html, include_comments=False, include_tables=False,
                                favor_precision=True, deduplicate=True) or ""
    parrafos = [" ".join(p.split()) for p in texto.split("\n") if p.strip()]
    resultado = "\n\n".join(parrafos)
    if len(resultado) < MIN_CARACTERES:
        raise NoSePudoLeer("no se encontró el texto de la noticia en la página (puede requerir suscripción)")
    if len(resultado) > MAX_CARACTERES:
        corte = resultado.rfind("\n\n", 0, MAX_CARACTERES)
        resultado = resultado[:corte if corte > 0 else MAX_CARACTERES]
    return resultado


async def texto_desde_enlace(url: str) -> str:
    html = await descargar(url.strip())
    return await asyncio.to_thread(extraer, html)
