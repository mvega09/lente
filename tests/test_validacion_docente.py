"""Material de validación con el docente (scripts/validacion_docente.py)."""

import pytest

from scripts.validacion_docente import VEREDICTOS, _normalizar, cargar_casos, crear_excel


def test_casos_completos():
    casos = cargar_casos()
    assert len(casos) == 24
    assert len({c["caso"] for c in casos}) == len(casos)
    assert {c["nivel_escolar"] for c in casos} == {"primaria", "secundaria", "media"}
    for c in casos:
        assert c["texto"] and c["idea_principal"] and c["elementos_clave"] and c["respuesta"].strip()


def test_normalizar_ignora_tildes_y_signos():
    assert _normalizar("«El agua bajó   turbia»") == "el agua bajo turbia"


def _resultado(caso: dict, veredicto: str | None) -> dict:
    ia = ({"error": "ResponseError: tiempo agotado"} if veredicto is None else
          {"veredicto": veredicto, "faltantes": "", "explicacion": "Bien.", "cita": "x", "cita_en_texto": True})
    return caso | {"ia": ia, "segundos": 12.0}


def test_crear_excel(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    casos = cargar_casos()[:4]
    resultados = [_resultado(casos[0], "coincide"), _resultado(casos[1], "coincide_en_parte"),
                  _resultado(casos[2], "por_mejorar"), _resultado(casos[3], None)]
    ruta = tmp_path / "v.xlsx"
    crear_excel(resultados, "qwen3:4b", ruta)

    wb = openpyxl.load_workbook(ruta)
    assert wb.sheetnames == ["Instrucciones", "Noticias", "1. Su evaluación", "2. Respuestas de la IA", "Resultado"]
    ev, ia, res = wb["1. Su evaluación"], wb["2. Respuestas de la IA"], wb["Resultado"]
    # El docente no ve el veredicto de la IA en su hoja
    assert all(c.value not in VEREDICTOS.values() for fila in ev.iter_rows() for c in fila)
    assert str(ev.data_validations.dataValidation[0].sqref) == "E2:E5"
    assert ia["C2"].value == "Coincide" and ia["C5"].value == "Error"
    assert ia["H2"].value.startswith("=IF('1. Su evaluación'!E2")
    assert res["B2"].value == 4
    assert res["B6"].value == 0.7
