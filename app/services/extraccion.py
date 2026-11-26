"""Lee una noticia desde su enlace y extrae solo el texto del artículo (RF-09).

Así el profesor puede cargar una noticia pegando el enlace, sin copiar el texto.

Protección contra SSRF: el servidor solo abre direcciones PÚBLICAS de internet.
Un enlace hacia la red interna (la base de datos, Ollama, 127.0.0.1, 10.x…) se
rechaza, también si llega por una redirección. Además hay límite de tiempo, de
tamaño y de redirecciones.
"""

import asyncio
import ipaddress
import re
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


def mensaje_por_codigo(codigo: int) -> str:
    """El código HTTP del sitio, dicho en palabras del profesor (sin «código 403»)."""
    if codigo in (401, 402, 403, 429, 451):
        return "Este sitio no permite que LENTE lea sus noticias automáticamente."
    if codigo in (404, 410):
        return "La página del enlace no existe; revisa que esté bien copiado."
    if codigo >= 500:
        return "El sitio de la noticia no está respondiendo en este momento."
    return f"El sitio de la noticia no entregó la página (respuesta {codigo})."


async def validar_destino(url: str) -> None:
    """Solo http/https hacia direcciones públicas (nunca la red interna)."""
    partes = urlsplit(url)
    if partes.scheme not in ("http", "https") or not partes.hostname:
        raise NoSePudoLeer("El enlace debe empezar por http:// o https://.")
    if partes.username or partes.password:
        raise NoSePudoLeer("El enlace no puede llevar usuario ni contraseña.")
    puerto = partes.port or (443 if partes.scheme == "https" else 80)
    try:
        direcciones = await asyncio.get_running_loop().getaddrinfo(partes.hostname, puerto, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise NoSePudoLeer("No se encontró el sitio web del enlace; revisa que esté bien escrito.") from None
    for *_, destino in direcciones:
        ip = ipaddress.ip_address(destino[0])
        if not ip.is_global:
            raise NoSePudoLeer("El enlace apunta a una dirección interna; solo se aceptan sitios públicos.")


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
                        raise NoSePudoLeer(mensaje_por_codigo(r.status_code))
                    if "html" not in r.headers.get("content-type", "html"):
                        raise NoSePudoLeer("El enlace no es una página web (¿es un PDF o una imagen?).")
                    contenido = bytearray()
                    async for trozo in r.aiter_bytes():
                        contenido += trozo
                        if len(contenido) > MAX_BYTES:
                            raise NoSePudoLeer("La página es demasiado grande.")
                    return bytes(contenido)
            except httpx.TimeoutException:
                raise NoSePudoLeer(f"La página no respondió en {TIEMPO_MAXIMO_S} segundos.") from None
            except httpx.HTTPError:
                raise NoSePudoLeer("No se pudo conectar con el sitio web de la noticia.") from None
    raise NoSePudoLeer("El enlace redirige demasiadas veces.")


# Publicaciones de redes sociales incrustadas en la noticia: no son parte del artículo
_EMBEBIDOS = (r"<blockquote[^>]*class=[\"'][^\"']*(?:twitter-tweet|twitter-video|instagram-media|tiktok-embed)"
              r"[^\"']*[\"'][^>]*>.*?</blockquote>")
EMBEBIDOS = re.compile(_EMBEBIDOS, re.IGNORECASE | re.DOTALL)
# La página llega en bytes: se limpia sin decodificar para que trafilatura detecte la codificación
EMBEBIDOS_BYTES = re.compile(_EMBEBIDOS.encode(), re.IGNORECASE | re.DOTALL)
# Restos de un tweet que a veces quedan como párrafo: enlaces de la red social y la firma
ENLACE_RED_SOCIAL = re.compile(r"https?://(?:t\.co|pic\.twitter\.com|(?:www\.)?(?:x|twitter)\.com)/\S*",
                               re.IGNORECASE)
FIRMA_TWEET = re.compile(r"^[—–-]\s*.{1,80}\(@\w{1,30}\)\s+\w+\s+\d{1,2},\s+\d{4}$")


def _sin_embebidos(html: bytes | str) -> bytes | str:
    if isinstance(html, bytes):
        return EMBEBIDOS_BYTES.sub(b" ", html)
    return EMBEBIDOS.sub(" ", html)


def _es_del_articulo(parrafo: str) -> bool:
    return not (ENLACE_RED_SOCIAL.search(parrafo) or FIRMA_TWEET.match(parrafo))


def extraer(html: bytes | str) -> str:
    """Solo el artículo: sin menús, publicidad, comentarios ni publicaciones de redes
    sociales incrustadas. Párrafos separados por una línea en blanco, como los espera
    el frontend."""
    # deduplicate=False: la deduplicación de trafilatura recuerda párrafos ENTRE llamadas
    # (caché global del proceso); al leer la misma noticia por tercera vez borraba párrafos.
    # Los repetidos dentro de la misma página se quitan aquí.
    texto = trafilatura.extract(_sin_embebidos(html), include_comments=False, include_tables=False,
                                favor_precision=True, deduplicate=False) or ""
    parrafos = [" ".join(p.split()) for p in texto.split("\n") if p.strip()]
    parrafos = list(dict.fromkeys(p for p in parrafos if _es_del_articulo(p)))
    resultado = "\n\n".join(parrafos)
    if len(resultado) < MIN_CARACTERES:
        raise NoSePudoLeer("No se encontró el texto de la noticia en la página (puede requerir suscripción).")
    if len(resultado) > MAX_CARACTERES:
        corte = resultado.rfind("\n\n", 0, MAX_CARACTERES)
        resultado = resultado[:corte if corte > 0 else MAX_CARACTERES]
    return resultado


async def texto_desde_enlace(url: str) -> str:
    html = await descargar(url.strip())
    return await asyncio.to_thread(extraer, html)
