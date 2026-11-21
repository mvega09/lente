"""Lectura de noticias desde su enlace (sin internet: el sitio web se simula)."""

import asyncio

import httpx
import pytest

from app.core.errores import DatoInvalido
from app.services import extraccion, textos_service
from tests.conftest import ConexionFalsa

PARRAFOS = [f"Párrafo {i} de la noticia sobre el parque central de Manizales y lo que dijeron los vecinos." * 2
            for i in range(1, 6)]
HTML = ("<html><head><title>Noticia</title></head><body>"
        "<nav>Inicio · Deportes · Política · Suscríbase</nav>"
        "<article><h1>El parque central</h1>" + "".join(f"<p>{p}</p>" for p in PARRAFOS) + "</article>"
        "<footer>© Periódico · Publicidad</footer></body></html>")


def _transporte(respuestas: dict[str, httpx.Response]):
    def manejar(peticion: httpx.Request):
        return respuestas[str(peticion.url)]
    return httpx.MockTransport(manejar)


# ---------------------------------------------------------------- seguridad (SSRF)

@pytest.mark.parametrize("url", [
    "ftp://ejemplo.com/noticia", "file:///etc/passwd", "noticia sin enlace",
    "http://127.0.0.1:8000/admin", "http://localhost/", "http://10.60.14.181:11434/api/tags",
    "http://10.60.14.183:5432", "http://169.254.169.254/latest/meta-data", "http://[::1]/",
    "http://usuario:clave@93.184.216.34/",
])
def test_rechaza_destinos_no_publicos(url):
    with pytest.raises(extraccion.NoSePudoLeer):
        asyncio.run(extraccion.validar_destino(url))


def test_acepta_una_direccion_publica():
    asyncio.run(extraccion.validar_destino("http://93.184.216.34/noticia"))


def test_una_redireccion_hacia_la_red_interna_se_rechaza():
    t = _transporte({"http://93.184.216.34/noticia": httpx.Response(302, headers={"location": "http://10.60.14.183:5432/"})})
    with pytest.raises(extraccion.NoSePudoLeer, match="dirección interna"):
        asyncio.run(extraccion.descargar("http://93.184.216.34/noticia", transport=t))


def test_sigue_redirecciones_publicas_y_rechaza_lo_que_no_es_html():
    t = _transporte({
        "http://93.184.216.34/a": httpx.Response(301, headers={"location": "/b"}),
        "http://93.184.216.34/b": httpx.Response(200, headers={"content-type": "text/html"}, text=HTML),
        "http://93.184.216.34/pdf": httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF"),
        "http://93.184.216.34/caido": httpx.Response(404, headers={"content-type": "text/html"}),
    })
    assert b"<article>" in asyncio.run(extraccion.descargar("http://93.184.216.34/a", transport=t))
    with pytest.raises(extraccion.NoSePudoLeer, match="PDF"):
        asyncio.run(extraccion.descargar("http://93.184.216.34/pdf", transport=t))
    with pytest.raises(extraccion.NoSePudoLeer, match="404"):
        asyncio.run(extraccion.descargar("http://93.184.216.34/caido", transport=t))


# ---------------------------------------------------------------- extracción

def test_extrae_solo_el_articulo_en_parrafos():
    texto = extraccion.extraer(HTML)
    assert "Suscríbase" not in texto and "Publicidad" not in texto
    assert texto.count("\n\n") >= 4                    # párrafos separados por una línea en blanco
    assert PARRAFOS[0].strip() in texto


TWEET = ('<blockquote class="twitter-tweet"><p lang="es">Así fue como un hombre dejó amenazas en la cárcel. '
         '<a href="https://t.co/f0wz5K8LNE">https://t.co/f0wz5K8LNE</a></p>&mdash; Revista Semana '
         '(@RevistaSemana) <a href="https://twitter.com/x/status/1">November 20, 2026</a></blockquote>')


@pytest.mark.parametrize("como", [str, lambda h: h.encode("utf-8")])
def test_quita_publicaciones_de_redes_sociales_incrustadas(como):
    html = HTML.replace(f"<p>{PARRAFOS[2]}</p>", f"<p>{PARRAFOS[2]}</p>{TWEET}")
    texto = extraccion.extraer(como(html))
    assert "t.co" not in texto and "@RevistaSemana" not in texto and "dejó amenazas" not in texto
    assert PARRAFOS[3].strip() in texto


@pytest.mark.parametrize(("parrafo", "es_del_articulo"), [
    ("Así fue como un hombre dejó una cava. https://t.co/f0wz5K8LNE https://t.co/AetGYhIPKs", False),
    ("— Revista Semana (@RevistaSemana) November 20, 2026", False),
    ("Mire el video en https://x.com/RevistaSemana/status/1", False),
    ("El Inpec alertó este viernes sobre un presunto plan contra sus sedes.", True),
    ("La exdecana dijo: «Esa no es mi firma» — 20 de noviembre de 2026.", True),
])
def test_restos_de_tweets_se_descartan(parrafo, es_del_articulo):
    assert extraccion._es_del_articulo(parrafo) is es_del_articulo


def test_leer_la_misma_noticia_varias_veces_da_el_mismo_texto():
    primero = extraccion.extraer(HTML)
    for _ in range(4):                             # antes, a la tercera lectura se perdían párrafos
        assert extraccion.extraer(HTML) == primero


def test_parrafos_repetidos_en_la_pagina_quedan_una_vez():
    html = HTML.replace(f"<p>{PARRAFOS[1]}</p>", f"<p>{PARRAFOS[1]}</p><p>{PARRAFOS[1]}</p>")
    assert extraccion.extraer(html).count(PARRAFOS[1].strip()) == 1


def test_pagina_sin_articulo_pide_pegar_el_texto():
    with pytest.raises(extraccion.NoSePudoLeer, match="suscripción"):
        extraccion.extraer("<html><body><p>Contenido exclusivo para suscriptores.</p></body></html>")


def test_noticia_muy_larga_se_corta_en_un_parrafo(monkeypatch):
    monkeypatch.setattr(extraccion, "MAX_CARACTERES", 500)
    texto = extraccion.extraer(HTML)
    assert len(texto) <= 500 and not texto.endswith(" ")


# ---------------------------------------------------------------- uso al crear y preparar

TEXTO_LEIDO = "Texto de la noticia leído de la página. " * 20


def _texto(cuerpo=None, enlace="https://www.lapatria.com/noticia", estado="borrador"):
    return {"id": 9, "tipo": "noticia", "titulo": "Fallecido", "cuerpo": cuerpo, "enlace": enlace, "fuente": "La Patria",
            "nota": None, "estado": estado, "idea_principal": None, "elementos_clave": [], "consejo_macro": None,
            "consejo_super": None, "consejo_micro": None, "preparado_por_ia": False, "aprobado_en": None,
            "creado_en": "2026-11-19T10:00:00Z"}


def test_crear_solo_con_enlace_lee_la_noticia_y_la_manda_a_la_ia(monkeypatch):
    async def leer(url):
        return TEXTO_LEIDO
    monkeypatch.setattr(extraccion, "texto_desde_enlace", leer)
    conn = ConexionFalsa({"id": 9}, _texto(TEXTO_LEIDO, estado="preparando"), [], [])
    asyncio.run(textos_service.crear(conn, 7, {"titulo": "Fallecido", "enlace": "https://www.lapatria.com/noticia",
                                               "cuerpo": None, "preparar_con_ia": True, "tipo": "noticia",
                                               "fuente": "La Patria", "nota": None}))
    insertado = conn.consultas[0][1]
    assert insertado["cuerpo"] == TEXTO_LEIDO and insertado["estado"] == "preparando"


def test_crear_con_enlace_ilegible_queda_en_borrador_con_aviso(monkeypatch):
    async def falla(url):
        raise extraccion.NoSePudoLeer("la página respondió con el código 403")
    monkeypatch.setattr(extraccion, "texto_desde_enlace", falla)
    conn = ConexionFalsa({"id": 9}, _texto(), [], [])
    asyncio.run(textos_service.crear(conn, 7, {"titulo": "Fallecido", "enlace": "https://x.com/n", "cuerpo": None,
                                               "preparar_con_ia": True, "tipo": "noticia", "fuente": None, "nota": None}))
    insertado = conn.consultas[0][1]
    assert insertado["estado"] == "borrador" and insertado["cuerpo"] is None
    assert "403" in insertado["nota"] and len(insertado["nota"]) <= 300


def test_preparar_un_texto_que_solo_tiene_enlace(monkeypatch):
    async def leer(url):
        return TEXTO_LEIDO
    monkeypatch.setattr(extraccion, "texto_desde_enlace", leer)
    conn = ConexionFalsa(_texto(), {"id": 9}, {"id": 9}, _texto(TEXTO_LEIDO, "preparando"), [], [])
    asyncio.run(textos_service.preparar(conn, 7, 9))
    sql = [s for s, _ in conn.consultas]
    assert textos_service.SQL_PONER_CUERPO in sql
    assert sql.index(textos_service.SQL_PONER_CUERPO) < sql.index(textos_service.SQL_CAMBIAR_ESTADO)


def test_preparar_con_enlace_ilegible_explica_que_pegue_el_texto(monkeypatch):
    async def falla(url):
        raise extraccion.NoSePudoLeer("no se encontró el texto de la noticia en la página (puede requerir suscripción)")
    monkeypatch.setattr(extraccion, "texto_desde_enlace", falla)
    with pytest.raises(DatoInvalido, match="Pegue el texto"):
        asyncio.run(textos_service.preparar(ConexionFalsa(_texto()), 7, 9))
