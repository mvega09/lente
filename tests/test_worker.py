"""Worker de IA sin Ollama ni base: modelo siempre cargado y tono de la revisión."""

from types import SimpleNamespace

from worker import ia_worker, prompts
from worker.modelos import RevisionIdea


class _ConexionAjustes:
    """Responde a SELECT ajuste(...) con el valor indicado (None = sin definir)."""

    def __init__(self, valor=None):
        self.valor = valor

    def execute(self, sql, params=None):
        return SimpleNamespace(fetchone=lambda: {"valor": self.valor})


def test_revision_le_habla_al_estudiante():
    mensajes = prompts.mensajes_revisar_idea("Texto.", "Idea.", ["a"], "secundaria", "Mi idea.")
    pedido = mensajes[-1]["content"]
    assert "segunda persona" in pedido and "Nunca escribas «el estudiante»" in pedido
    assert "máximo 8 palabras" in pedido
    assert pedido.endswith("Mi idea.")          # la respuesta va al final (caché de prefijo)


def test_preguntar_usa_el_keep_alive_indicado(monkeypatch):
    llamadas = []

    def chat(**kw):
        llamadas.append(kw)
        return SimpleNamespace(message=SimpleNamespace(content=RevisionIdea(
            veredicto="coincide", faltantes="", explicacion="Bien.", cita="x").model_dump_json()))

    monkeypatch.setattr(ia_worker.cliente_revision, "chat", chat)
    ia_worker.preguntar("m", [], RevisionIdea, 10, keep_alive="-1m")
    ia_worker.preguntar("m", [], RevisionIdea, 10)
    assert llamadas[0]["keep_alive"] == "-1m"
    assert llamadas[1]["keep_alive"] == ia_worker.settings.ollama_keep_alive


def test_precalentar_carga_el_modelo_de_validacion(monkeypatch):
    pedidos = []
    monkeypatch.setattr(ia_worker.cliente_revision, "generate", lambda **kw: pedidos.append(kw))
    assert ia_worker.precalentar(_ConexionAjustes()) is True
    assert pedidos == [{"model": ia_worker.settings.ollama_modelo_validacion, "prompt": "",
                        "keep_alive": ia_worker.settings.ollama_keep_alive_validacion}]
    # Si el ajuste define otro modelo, se precarga ese
    ia_worker.precalentar(_ConexionAjustes("otro:1b"))
    assert pedidos[-1]["model"] == "otro:1b"


def test_precalentar_no_detiene_el_worker_si_ollama_falla(monkeypatch):
    def falla(**kw):
        raise ConnectionError("Ollama apagado")

    monkeypatch.setattr(ia_worker.cliente_revision, "generate", falla)
    assert ia_worker.precalentar(_ConexionAjustes()) is False


def test_validacion_queda_siempre_cargada_por_defecto():
    assert ia_worker.settings.ollama_keep_alive_validacion.startswith("-")
