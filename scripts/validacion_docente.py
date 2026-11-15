"""Material para que el docente valide la revisión de la idea principal (RF-10).

Criterio del levantamiento v1.1: la IA debe coincidir con el docente en al
menos el 70 % de los casos. La validación es "a ciegas": el docente califica
cada respuesta sin ver lo que dijo la IA, y la hoja calcula el acuerdo sola.

Dos pasos:

1. Pedir a la IA su veredicto para cada caso (en la VM-APP, con acceso a Ollama).
   Usa exactamente el mismo prompt, formato y modelo que el worker:

       OLLAMA_URL=http://10.60.14.181:11434 python -m scripts.validacion_docente ia \
           --salida validacion_ia.json

2. Crear la hoja de Excel para el docente (necesita openpyxl):

       python -m scripts.validacion_docente excel --resultados validacion_ia.json \
           --salida validacion_docente.xlsx
"""

import argparse
import json
import pathlib
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor

CASOS = pathlib.Path(__file__).with_name("casos_validacion.json")

VEREDICTOS = {
    "coincide": "Coincide",
    "coincide_en_parte": "Coincide en parte",
    "por_mejorar": "Por mejorar",
}


def cargar_casos(ruta: pathlib.Path = CASOS) -> list[dict]:
    """Aplana el archivo de casos: una fila por respuesta de estudiante."""
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    casos = []
    for n in datos["noticias"]:
        for i, respuesta in enumerate(n["respuestas"], start=1):
            casos.append({
                "caso": f"{n['id']}-{i}",
                "noticia_id": n["id"],
                "titulo": n["titulo"],
                "nivel_escolar": n["nivel_escolar"],
                "texto": n["texto"],
                "idea_principal": n["idea_principal"],
                "elementos_clave": n["elementos_clave"],
                "respuesta": respuesta,
            })
    return casos


def _normalizar(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    return " ".join("".join(c for c in t if unicodedata.category(c) != "Mn"
                            and (c.isalnum() or c.isspace())).split())


# ---------------------------------------------------------------- paso 1: IA

def pedir_ia(casos: list[dict], modelo: str, simultaneos: int) -> list[dict]:
    from worker import prompts
    from worker.ia_worker import cliente_revision, preguntar
    from worker.modelos import RevisionIdea

    def uno(c: dict) -> dict:
        inicio = time.perf_counter()
        try:
            rev = preguntar(modelo,
                            prompts.mensajes_revisar_idea(c["texto"], c["idea_principal"], c["elementos_clave"],
                                                          c["nivel_escolar"], c["respuesta"]),
                            RevisionIdea, 250, cliente_revision)
            ia = rev.model_dump()
            # Igual que guardar_revision_idea: una cita que no está en el texto no se muestra
            ia["cita_en_texto"] = bool(ia["cita"].strip()) and _normalizar(ia["cita"]) in _normalizar(c["texto"])
        except Exception as e:  # noqa: BLE001
            ia = {"error": f"{type(e).__name__}: {e}"[:200]}
        return c | {"ia": ia, "segundos": round(time.perf_counter() - inicio, 1)}

    with ThreadPoolExecutor(max_workers=simultaneos) as pool:
        return list(pool.map(uno, casos))


# ---------------------------------------------------------------- paso 2: Excel

def crear_excel(resultados: list[dict], modelo: str, salida: pathlib.Path) -> None:
    from openpyxl import Workbook
    from openpyxl.comments import Comment
    from openpyxl.formatting.rule import FormulaRule
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.datavalidation import DataValidation

    fuente = "Arial"
    titulo = Font(name=fuente, size=14, bold=True)
    negrita = Font(name=fuente, bold=True)
    normal = Font(name=fuente)
    gris = Font(name=fuente, color="666666", italic=True)
    encabezado_fill = PatternFill("solid", fgColor="1F4E78")
    encabezado_font = Font(name=fuente, bold=True, color="FFFFFF")
    amarillo = PatternFill("solid", fgColor="FFF2CC")
    borde = Border(*(Side(style="thin", color="BFBFBF"),) * 4)
    ajustar = Alignment(wrap_text=True, vertical="top")
    opciones = list(VEREDICTOS.values())
    n = len(resultados)

    wb = Workbook()

    # --- Instrucciones
    ins = wb.active
    ins.title = "Instrucciones"
    ins.column_dimensions["A"].width = 110
    lineas = [
        ("Validación de la IA de LENTE con el docente", titulo),
        ("", normal),
        ("¿Para qué sirve?", negrita),
        ("LENTE usa inteligencia artificial para decirle al estudiante si su idea principal coincide con la de la "
         "noticia. El requisito del proyecto es que la IA esté de acuerdo con el docente en al menos el 70 % de los "
         "casos. Esta hoja mide ese porcentaje.", normal),
        ("", normal),
        ("Cómo llenarla (unos 20 minutos)", negrita),
        ("1. Lea las noticias en la hoja «Noticias».", normal),
        ("2. En la hoja «1. Su evaluación», para cada respuesta de estudiante elija en la columna amarilla su "
         "veredicto: Coincide, Coincide en parte o Por mejorar. Solo debe editar las celdas amarillas.", normal),
        ("3. No mire la hoja «2. Respuestas de la IA» hasta terminar: así su calificación no se deja influir.", normal),
        ("4. Al terminar, la hoja «Resultado» muestra el porcentaje de acuerdo y si se cumple el 70 %.", normal),
        ("", normal),
        ("Qué significa cada veredicto", negrita),
        ("Coincide: menciona lo esencial de la idea principal.", normal),
        ("Coincide en parte: va por buen camino pero le falta algún elemento clave.", normal),
        ("Por mejorar: se queda en un detalle, opina o se sale del tema.", normal),
        ("", normal),
        ("Ejemplo (no cuenta en el resultado)", negrita),
        ("Respuesta: «Van a hacer un parqueadero en el centro.» → Su veredicto: Coincide en parte "
         "(dice qué se hará, pero no quién lo aprobó ni el desacuerdo de los vecinos).", gris),
        ("", normal),
        (f"Modelo evaluado: {modelo}. Noticias y respuestas ficticias, escritas para cubrir respuestas buenas, "
         "parciales, pobres, de opinión y fuera de tema.", gris),
    ]
    for i, (texto, estilo) in enumerate(lineas, start=1):
        c = ins.cell(row=i, column=1, value=texto)
        c.font, c.alignment = estilo, Alignment(wrap_text=True, vertical="top")

    # --- Noticias
    noticias = wb.create_sheet("Noticias")
    vistas = []
    for r in resultados:
        if r["noticia_id"] not in vistas:
            vistas.append(r["noticia_id"])
    for col, (cab, ancho) in enumerate([("Noticia", 10), ("Título", 30), ("Nivel", 12), ("Texto", 90),
                                        ("Idea principal de referencia", 45)], start=1):
        c = noticias.cell(row=1, column=col, value=cab)
        c.font, c.fill = encabezado_font, encabezado_fill
        noticias.column_dimensions[c.column_letter].width = ancho
    for fila, nid in enumerate(vistas, start=2):
        r = next(x for x in resultados if x["noticia_id"] == nid)
        for col, v in enumerate([nid, r["titulo"], r["nivel_escolar"], r["texto"], r["idea_principal"]], start=1):
            c = noticias.cell(row=fila, column=col, value=v)
            c.font, c.alignment, c.border = normal, ajustar, borde
    noticias.freeze_panes = "A2"

    # --- 1. Su evaluación (lo único que llena el docente)
    ev = wb.create_sheet("1. Su evaluación")
    cols = [("Caso", 8), ("Noticia", 9), ("Nivel", 11), ("Respuesta del estudiante", 70),
            ("Su veredicto", 20), ("Comentario (opcional)", 40)]
    for col, (cab, ancho) in enumerate(cols, start=1):
        c = ev.cell(row=1, column=col, value=cab)
        c.font, c.fill, c.alignment = encabezado_font, encabezado_fill, Alignment(wrap_text=True)
        ev.column_dimensions[c.column_letter].width = ancho
    ev["E1"].comment = Comment("Elija: Coincide, Coincide en parte o Por mejorar.", "LENTE")
    for i, r in enumerate(resultados, start=2):
        for col, v in enumerate([r["caso"], r["noticia_id"], r["nivel_escolar"], r["respuesta"], None, None], start=1):
            c = ev.cell(row=i, column=col, value=v)
            c.font, c.alignment, c.border = normal, ajustar, borde
        ev.cell(row=i, column=5).fill = amarillo
        ev.cell(row=i, column=6).fill = amarillo
    lista = DataValidation(type="list", formula1='"' + ",".join(opciones) + '"', allow_blank=True,
                           showErrorMessage=True, errorTitle="Valor no válido",
                           error="Elija Coincide, Coincide en parte o Por mejorar.")
    ev.add_data_validation(lista)
    lista.add(f"E2:E{n + 1}")
    ev.freeze_panes = "A2"

    # --- 2. Respuestas de la IA (con la comparación)
    ia = wb.create_sheet("2. Respuestas de la IA")
    cols = [("Caso", 8), ("Respuesta del estudiante", 50), ("Veredicto de la IA", 18), ("Lo que faltó (IA)", 30),
            ("Explicación para el estudiante (IA)", 40), ("Cita del texto (IA)", 35), ("¿Cita en el texto?", 11),
            ("Su veredicto", 18), ("¿Coinciden?", 12), ("Diferencia de un nivel", 12)]
    for col, (cab, ancho) in enumerate(cols, start=1):
        c = ia.cell(row=1, column=col, value=cab)
        c.font, c.fill, c.alignment = encabezado_font, encabezado_fill, Alignment(wrap_text=True)
        ia.column_dimensions[c.column_letter].width = ancho
    for i, r in enumerate(resultados, start=2):
        d = r["ia"]
        if "error" in d:
            valores = [r["caso"], r["respuesta"], "Error", d["error"], "", "", ""]
        else:
            valores = [r["caso"], r["respuesta"], VEREDICTOS[d["veredicto"]], d["faltantes"], d["explicacion"],
                       d["cita"], "Sí" if d["cita_en_texto"] else "No"]
        valores += [
            f"=IF('1. Su evaluación'!E{i}=\"\",\"\",'1. Su evaluación'!E{i})",
            f"=IF(H{i}=\"\",\"\",IF(C{i}=H{i},\"Sí\",\"No\"))",
            # "Coincide en parte" frente a cualquiera de los extremos es una diferencia de un solo nivel
            f"=IF(I{i}<>\"No\",\"\",IF(OR(C{i}=\"Coincide en parte\",H{i}=\"Coincide en parte\"),\"Sí\",\"No\"))",
        ]
        for col, v in enumerate(valores, start=1):
            c = ia.cell(row=i, column=col, value=v)
            c.font, c.alignment, c.border = normal, ajustar, borde
    rango_i = f"I2:I{n + 1}"
    ia.conditional_formatting.add(rango_i, FormulaRule(formula=['I2="Sí"'], fill=PatternFill("solid", fgColor="C6EFCE")))
    ia.conditional_formatting.add(rango_i, FormulaRule(formula=['I2="No"'], fill=PatternFill("solid", fgColor="FFC7CE")))
    ia.freeze_panes = "B2"

    # --- Resultado
    res = wb.create_sheet("Resultado")
    res.column_dimensions["A"].width = 48
    res.column_dimensions["B"].width = 16
    res.column_dimensions["C"].width = 60
    hoja = "'2. Respuestas de la IA'"
    col_ia, col_doc, col_ok, col_1 = (f"{hoja}!{c}2:{c}{n + 1}" for c in "CHIJ")
    filas = [
        ("Resultado de la validación", None, None, titulo),
        ("Casos en total", n, None, normal),
        ("Casos calificados por el docente", f"=COUNTIF({col_ok},\"Sí\")+COUNTIF({col_ok},\"No\")", None, normal),
        ("Casos en que la IA coincide con el docente", f"=COUNTIF({col_ok},\"Sí\")", None, normal),
        ("Porcentaje de acuerdo", "=IF(B3=0,\"\",B4/B3)", None, negrita),
        ("Meta del proyecto (levantamiento v1.1)", 0.7, "Valor fijado por el requisito: al menos 70 % de acuerdo.", normal),
        ("¿Se cumple?", "=IF(B3=0,\"Falta calificar\",IF(B3<B2,\"Incompleto: \"&(B2-B3)&\" casos sin calificar\","
                        "IF(B5>=B6,\"Sí cumple\",\"No cumple\")))", None, negrita),
        ("", None, None, normal),
        ("Desacuerdos de un solo nivel (p. ej. Coincide vs. Coincide en parte)",
         f"=COUNTIF({col_1},\"Sí\")", "Desacuerdos menos graves.", normal),
        ("Desacuerdos graves (Coincide vs. Por mejorar)", f"=COUNTIF({col_1},\"No\")", "Revisar estos casos primero.", normal),
        ("", None, None, normal),
        ("Acuerdo por veredicto del docente", None, None, negrita),
    ]
    for i, (etiqueta, valor, nota, estilo) in enumerate(filas, start=1):
        res.cell(row=i, column=1, value=etiqueta).font = estilo
        if valor is not None:
            res.cell(row=i, column=2, value=valor).font = estilo
        if nota:
            res.cell(row=i, column=3, value=nota).font = gris
    res["B5"].number_format = "0.0%"
    res["B6"].number_format = "0%"
    res["B6"].font = Font(name=fuente, color="0000FF")
    for c, cab in zip("ABC", ["Veredicto del docente", "Casos", "Acuerdo de la IA"]):
        cel = res[f"{c}13"]
        cel.value, cel.font, cel.fill = cab, encabezado_font, encabezado_fill
    for fila, v in enumerate(opciones, start=14):
        res[f"A{fila}"] = v
        res[f"B{fila}"] = f"=COUNTIF({col_doc},A{fila})"
        res[f"C{fila}"] = f"=IF(B{fila}=0,\"\",COUNTIFS({col_doc},A{fila},{col_ok},\"Sí\")/B{fila})"
        res[f"C{fila}"].number_format = "0.0%"
        for c in "ABC":
            res[f"{c}{fila}"].font = normal
    res.conditional_formatting.add("B7", FormulaRule(formula=['B7="Sí cumple"'], fill=PatternFill("solid", fgColor="C6EFCE")))
    res.conditional_formatting.add("B7", FormulaRule(formula=['B7="No cumple"'], fill=PatternFill("solid", fgColor="FFC7CE")))

    wb.save(salida)


# ---------------------------------------------------------------- línea de comandos

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="paso", required=True)
    p_ia = sub.add_parser("ia", help="Pedir el veredicto de la IA para cada caso")
    p_ia.add_argument("--casos", type=pathlib.Path, default=CASOS)
    p_ia.add_argument("--modelo", default=None, help="Por defecto, el modelo de validación configurado")
    p_ia.add_argument("--simultaneos", type=int, default=4)
    p_ia.add_argument("--salida", type=pathlib.Path, default=pathlib.Path("validacion_ia.json"))
    p_x = sub.add_parser("excel", help="Crear la hoja de Excel para el docente")
    p_x.add_argument("--resultados", type=pathlib.Path, default=pathlib.Path("validacion_ia.json"))
    p_x.add_argument("--salida", type=pathlib.Path, default=pathlib.Path("validacion_docente.xlsx"))
    args = ap.parse_args()

    if args.paso == "ia":
        from app.core.config import get_settings
        modelo = args.modelo or get_settings().ollama_modelo_validacion
        resultados = pedir_ia(cargar_casos(args.casos), modelo, args.simultaneos)
        args.salida.write_text(json.dumps({"modelo": modelo, "resultados": resultados}, ensure_ascii=False, indent=1),
                               encoding="utf-8")
        errores = sum("error" in r["ia"] for r in resultados)
        print(f"{len(resultados)} casos, {errores} con error -> {args.salida}")
    else:
        datos = json.loads(args.resultados.read_text(encoding="utf-8"))
        crear_excel(datos["resultados"], datos["modelo"], args.salida)
        print(f"Hoja creada: {args.salida}")


if __name__ == "__main__":
    main()
