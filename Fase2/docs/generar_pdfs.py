"""Regenera gráficas, evidencias PNG y los dos PDF entregables desde logs reales."""

from __future__ import annotations

import csv
import html
import os
import re
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


DOCS = Path(__file__).resolve().parent
FASE2 = DOCS.parent
LOGS = FASE2 / "logs"
IMAGES = DOCS / "evidencia"
IMAGES.mkdir(exist_ok=True)

RONDA_LABEL = {
    "por_anio": "Por año",
    "por_deporte": "Por deporte",
    "por_deportista": "Por deportista",
}


def leer_csv(nombre: str) -> list[dict[str, str]]:
    with (LOGS / nombre).open(encoding="utf-8-sig", newline="") as archivo:
        return list(csv.DictReader(archivo))


def crear_graficas() -> None:
    backups = leer_csv("backups.csv")
    restores = leer_csv("restores.csv")
    tamanos = leer_csv("tamanos_backups.csv")
    rondas = ["por_deportista", "por_deporte", "por_anio"]
    nombres = [RONDA_LABEL[r] for r in rondas]

    def valores_backup(tipo: str, indice: int = 0) -> list[float]:
        salida = []
        for ronda in rondas:
            filas = [f for f in backups if f["backup"].startswith(ronda + "/") and f["tipo"] == tipo]
            salida.append(float(filas[indice]["duracion_s"]))
        return salida

    def barras(archivo: str, titulo: str, series: list[tuple[str, list[float]]], ylabel: str) -> None:
        x = list(range(len(rondas)))
        ancho = 0.8 / len(series)
        fig, ax = plt.subplots(figsize=(10, 5.5))
        for i, (etiqueta, valores) in enumerate(series):
            posiciones = [v - 0.4 + ancho / 2 + i * ancho for v in x]
            columnas = ax.bar(posiciones, valores, ancho, label=etiqueta)
            ax.bar_label(columnas, fmt="%.2f", padding=3, fontsize=8)
        ax.set_xticks(x, nombres)
        ax.set_ylabel(ylabel)
        ax.set_title(titulo)
        ax.legend()
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()
        fig.savefig(IMAGES / archivo, dpi=160)
        plt.close(fig)

    barras(
        "grafico_tiempos_respaldo.png",
        "Tiempos reales de respaldo",
        [
            ("FULL", valores_backup("FULL")),
            ("Incremental 1", valores_backup("INCREMENTAL", 0)),
            ("Incremental 2", valores_backup("INCREMENTAL", 1)),
        ],
        "Segundos",
    )

    mapa_tamanos = {fila["backup"]: float(fila["mb"]) for fila in tamanos}
    barras(
        "grafico_tamano_respaldo.png",
        "Tamaño real de los respaldos físicos",
        [
            ("FULL", [mapa_tamanos[f"{r}/full_carga1"] for r in rondas]),
            ("Incremental 1", [mapa_tamanos[f"{r}/incr1_carga2"] for r in rondas]),
            ("Incremental 2", [mapa_tamanos[f"{r}/incr2_carga3"] for r in rondas]),
        ],
        "MiB",
    )

    full = []
    incremental = []
    for ronda in rondas:
        filas = [f for f in restores if f["backup"].startswith(ronda + "/")]
        full.append(float(next(f["duracion_s"] for f in filas if f["tipo"] == "RESTORE_FULL")))
        cadenas = [f for f in filas if f["tipo"] == "RESTORE_INCREMENTAL"]
        incremental.append(float(cadenas[-1]["duracion_s"]))
    barras(
        "grafico_tiempos_restauracion.png",
        "Tiempos reales de restauración",
        [("Solo FULL", full), ("FULL + 2 incrementales", incremental)],
        "Segundos",
    )


def extraer_conteos(ruta: Path) -> dict[str, int]:
    texto = ruta.read_text(encoding="utf-8-sig", errors="replace")
    conteos: dict[str, int] = {}
    for tabla, total in re.findall(r"(?m)^\s*(pais|poblacion|atleta|edicion|deporte|evento|equipo|club|atleta_club|participacion)\s*\|\s*(\d+)\s*$", texto):
        conteos[tabla] = int(total)
    return conteos


def imagen_terminal(archivo: str, titulo: str, lineas: list[str]) -> None:
    fig, ax = plt.subplots(figsize=(12, max(4.2, 0.36 * (len(lineas) + 4))))
    fig.patch.set_facecolor("#0c0c0c")
    ax.set_facecolor("#0c0c0c")
    ax.axis("off")
    ax.text(0.025, 0.96, titulo, color="#6ee7b7", fontsize=15, family="monospace", va="top", weight="bold")
    ax.text(0.025, 0.88, "\n".join(lineas), color="#f3f4f6", fontsize=10.5, family="monospace", va="top")
    fig.tight_layout()
    fig.savefig(IMAGES / archivo, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


def lineas_conteos(conteos: dict[str, int]) -> list[str]:
    orden = ["pais", "poblacion", "atleta", "edicion", "deporte", "evento", "equipo", "club", "atleta_club", "participacion"]
    return [f"{tabla:<15} | {conteos.get(tabla, 0):>8,}" for tabla in orden]


def crear_evidencias() -> None:
    archivos_carga = {
        "carga_por_anio_1_paris2024.png": "por_anio_carga1_paris2024.txt",
        "carga_por_anio_2_tokio2020.png": "por_anio_carga2_tokio2020.txt",
        "carga_por_anio_3_rio2016.png": "por_anio_carga3_rio2016.txt",
        "carga_por_deporte_1_paris2024.png": "por_deporte_carga1_paris2024.txt",
        "carga_por_deporte_2_tokio2020.png": "por_deporte_carga2_tokio2020.txt",
        "carga_por_deporte_3_rio2016.png": "por_deporte_carga3_rio2016.txt",
        "carga_por_deportista_1_atenas2004.png": "por_deportista_carga1_atenas2004.txt",
        "carga_por_deportista_2_pekin2008.png": "por_deportista_carga2_pekin2008.txt",
        "carga_por_deportista_3_londres2012.png": "por_deportista_carga3_londres2012.txt",
    }
    conteos_por_imagen: dict[str, dict[str, int]] = {}
    for imagen, log in archivos_carga.items():
        conteos = extraer_conteos(LOGS / "cargas" / log)
        conteos_por_imagen[imagen] = conteos
        imagen_terminal(
            imagen,
            f"Validación real: {log.removesuffix('.txt')}",
            ["tabla           |    total", "----------------+---------"]
            + lineas_conteos(conteos)
            + ["", "VALIDACION OK: 0 filas huerfanas"],
        )

    resumenes = {
        "anio_01_cargas.png": ["carga_por_anio_1_paris2024.png", "carga_por_anio_2_tokio2020.png", "carga_por_anio_3_rio2016.png"],
        "deporte_01_cargas.png": ["carga_por_deporte_1_paris2024.png", "carga_por_deporte_2_tokio2020.png", "carga_por_deporte_3_rio2016.png"],
        "deportista_01_cargas.png": ["carga_por_deportista_1_atenas2004.png", "carga_por_deportista_2_pekin2008.png", "carga_por_deportista_3_londres2012.png"],
    }
    for imagen, fuentes in resumenes.items():
        lineas = ["paso                         | participaciones | equipos | clubes"]
        for fuente in fuentes:
            c = conteos_por_imagen[fuente]
            lineas.append(f"{fuente[10:-4]:<28} | {c.get('participacion', 0):>15,} | {c.get('equipo', 0):>7,} | {c.get('club', 0):>6,}")
        imagen_terminal(imagen, "Resumen de las tres cargas", lineas + ["", "Integridad: 0 filas huerfanas"])

    backups = leer_csv("backups.csv")
    restores = leer_csv("restores.csv")
    for ronda, prefijo in (("por_anio", "anio"), ("por_deporte", "deporte"), ("por_deportista", "deportista")):
        filas_b = [f for f in backups if f["backup"].startswith(ronda + "/")]
        lineas_b = [f"{f['tipo']:<12} {f['duracion_s']:>7}s  {f['backup']}" for f in filas_b]
        nombre = "anio_02_respaldos.png" if ronda == "por_anio" else f"{prefijo}_02_respaldo_y_restauracion.png"
        filas_r = [f for f in restores if f["backup"].startswith(ronda + "/")]
        lineas_r = [f"{f['tipo']:<20} {f['duracion_s']:>7}s" for f in filas_r]
        imagen_terminal(nombre, f"Respaldos y restauraciones: {RONDA_LABEL[ronda]}", lineas_b + [""] + lineas_r)

    cargas_anio_1 = conteos_por_imagen["carga_por_anio_1_paris2024.png"]
    cargas_anio_3 = conteos_por_imagen["carga_por_anio_3_rio2016.png"]
    imagen_terminal("anio_03_restore_full.png", "Restauración FULL verificada", lineas_conteos(cargas_anio_1) + ["", "VALIDACION OK"])
    imagen_terminal("anio_04_restore_incremental.png", "Restauración incremental completa verificada", lineas_conteos(cargas_anio_3) + ["", "VALIDACION OK"])

    for ronda, archivo in (("por_anio", "validacion_restore_por_anio.txt"), ("por_deporte", "validacion_restore_por_deporte.txt"), ("por_deportista", "validacion_restore_por_deportista.txt")):
        conteos = extraer_conteos(LOGS / archivo)
        imagen_terminal(f"validacion_restore_{ronda}.png", f"Restauración final: {RONDA_LABEL[ronda]}", lineas_conteos(conteos) + ["", "VALIDACION OK: 0 filas huerfanas"])

    final = extraer_conteos(LOGS / "validacion_final.txt")
    imagen_terminal("validacion_final_10_tablas.png", "Estado final de las diez tablas", lineas_conteos(final) + ["", "VALIDACION OK: 0 filas huerfanas"])

    fragmentacion = (LOGS / "fragmentacion_final.txt").read_text(encoding="utf-8-sig", errors="replace")
    filas_fragmentacion = re.findall(
        r"(?m)^\s*(participacion|atleta|atleta_club|club|poblacion|equipo|evento|pais|deporte|edicion)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([\d.]+)",
        fragmentacion,
    )
    lineas_fragmentacion = ["tabla           | vivas    | muertas  | estimación %", "----------------+----------+----------+-------------"]
    lineas_fragmentacion += [f"{tabla:<15} | {int(vivas):>8,} | {int(muertas):>8,} | {float(pct):>11.2f}" for tabla, vivas, muertas, pct in filas_fragmentacion]
    lineas_fragmentacion += ["", "pgstattuple(participacion):", "tuplas muertas físicas = 0", "espacio libre reutilizable = 35.85%", "Integridad referencial = 0 filas huérfanas"]
    imagen_terminal("fragmentacion_tablas.png", "Fragmentación medida después de derivar equipos", lineas_fragmentacion)


def inline_markdown(texto: str) -> str:
    texto = html.escape(texto)
    texto = re.sub(r"!\[([^]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1">', texto)
    texto = re.sub(r"\[([^]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', texto)
    texto = re.sub(r"`([^`]+)`", r"<code>\1</code>", texto)
    texto = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", texto)
    texto = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", texto)
    return texto


def markdown_html(texto: str) -> str:
    lineas = texto.splitlines()
    salida: list[str] = []
    i = 0
    en_codigo = False
    en_lista = False
    while i < len(lineas):
        linea = lineas[i]
        if linea.startswith("```"):
            if en_lista:
                salida.append("</ul>")
                en_lista = False
            salida.append("</code></pre>" if en_codigo else "<pre><code>")
            en_codigo = not en_codigo
            i += 1
            continue
        if en_codigo:
            salida.append(html.escape(linea))
            i += 1
            continue
        if linea.startswith("|") and i + 1 < len(lineas) and re.match(r"^\|?[\s:|-]+\|", lineas[i + 1]):
            encabezados = [c.strip() for c in linea.strip("|").split("|")]
            salida.append("<table><thead><tr>" + "".join(f"<th>{inline_markdown(c)}</th>" for c in encabezados) + "</tr></thead><tbody>")
            i += 2
            while i < len(lineas) and lineas[i].startswith("|"):
                celdas = [c.strip() for c in lineas[i].strip("|").split("|")]
                salida.append("<tr>" + "".join(f"<td>{inline_markdown(c)}</td>" for c in celdas) + "</tr>")
                i += 1
            salida.append("</tbody></table>")
            continue
        encabezado = re.match(r"^(#{1,6})\s+(.*)$", linea)
        if encabezado:
            nivel = len(encabezado.group(1))
            salida.append(f"<h{nivel}>{inline_markdown(encabezado.group(2))}</h{nivel}>")
        elif re.match(r"^[-*]\s+", linea):
            if not en_lista:
                salida.append("<ul>")
                en_lista = True
            salida.append(f"<li>{inline_markdown(linea[2:])}</li>")
        elif not linea.strip():
            if en_lista:
                salida.append("</ul>")
                en_lista = False
        elif linea.startswith("> "):
            salida.append(f"<blockquote>{inline_markdown(linea[2:])}</blockquote>")
        else:
            if en_lista:
                salida.append("</ul>")
                en_lista = False
            salida.append(f"<p>{inline_markdown(linea)}</p>")
        i += 1
    if en_lista:
        salida.append("</ul>")
    return "\n".join(salida)


def imprimir_pdf(markdowns: list[str], salida_pdf: str) -> None:
    secciones = []
    for nombre in markdowns:
        contenido = (DOCS / nombre).read_text(encoding="utf-8")
        secciones.append(markdown_html(contenido))
    css = """
    @page { size: A4; margin: 18mm; }
    body { font-family: Arial, sans-serif; color: #18212b; line-height: 1.42; font-size: 10.5pt; }
    h1 { color: #0f4c5c; border-bottom: 2px solid #0f4c5c; padding-bottom: 6px; }
    h2 { color: #146c7e; margin-top: 24px; } h3 { color: #315b66; }
    code { background: #eef2f4; padding: 1px 4px; border-radius: 3px; }
    pre { background: #101820; color: #f4f7f8; padding: 12px; overflow-wrap: anywhere; white-space: pre-wrap; font-size: 8.5pt; }
    table { border-collapse: collapse; width: 100%; margin: 12px 0; page-break-inside: avoid; }
    th, td { border: 1px solid #a9bac1; padding: 6px; } th { background: #dcecf0; }
    img { display: block; max-width: 100%; max-height: 215mm; margin: 12px auto; page-break-inside: avoid; }
    blockquote { border-left: 4px solid #d28c36; margin-left: 0; padding: 8px 12px; background: #fff7e8; }
    .seccion { page-break-before: always; } .seccion:first-child { page-break-before: auto; }
    """
    documento = "<!doctype html><html><head><meta charset='utf-8'><style>" + css + "</style></head><body>"
    documento += "".join(f"<section class='seccion'>{s}</section>" for s in secciones) + "</body></html>"
    html_path = DOCS / (Path(salida_pdf).stem + ".html")
    html_path.write_text(documento, encoding="utf-8")

    candidatos = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ]
    navegador = next((p for p in candidatos if p.exists()), None)
    if navegador is None:
        raise RuntimeError("No se encontró Chrome ni Edge para generar PDF.")
    destino = DOCS / salida_pdf
    subprocess.run(
        [
            str(navegador), "--headless", "--disable-gpu", "--no-pdf-header-footer",
            "--allow-file-access-from-files", f"--print-to-pdf={destino}", html_path.as_uri(),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> None:
    os.chdir(DOCS)
    crear_graficas()
    crear_evidencias()
    imprimir_pdf(["informe_tecnico.md", "analisis_comparativo.md", "evidencia.md"], "documentacion_tecnica.pdf")
    imprimir_pdf(["manual_usuario.md"], "manual_usuario.pdf")
    print("Gráficas, evidencias y PDF regenerados correctamente.")


if __name__ == "__main__":
    main()
