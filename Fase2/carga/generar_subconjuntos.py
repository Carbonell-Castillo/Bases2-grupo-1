"""
Genera los CSV de las 3 rondas de carga (por anio, por deporte, por deportista)
a partir de los CSV ya procesados en ../Fase1/etl-csvs. Cada ronda tiene 3 pasos
acumulativos (paso N incluye todo lo de paso N-1 mas el dato nuevo), para poder
tomar: carga1 -> full backup, carga2 -> incremental 1, carga3 -> incremental 2.
"""
import csv
import os

FASE1 = os.path.join(os.path.dirname(__file__), "..", "..", "Fase1", "etl-csvs")
OUT = os.path.join(os.path.dirname(__file__), "subconjuntos")

TABLAS = [
    "pais", "poblacion", "edicion", "deporte", "evento", "atleta",
    "equipo", "club", "atleta_club", "participacion",
]


def leer(tabla):
    path = os.path.join(FASE1, f"{tabla}.csv")
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def escribir(tabla, filas, carpeta):
    os.makedirs(carpeta, exist_ok=True)
    if not filas:
        campos = CAMPOS[tabla]
    else:
        campos = list(filas[0].keys())
    with open(os.path.join(carpeta, f"{tabla}.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(filas)


CAMPOS = {
    "pais": ["pais_id", "nombre_pais", "region"],
    "poblacion": ["pais_id", "anio", "poblacion"],
    "edicion": ["edicion_id", "nombre_edicion", "anio", "temporada", "ciudad", "pais_sede_id"],
    "deporte": ["deporte_id", "nombre_deporte"],
    "evento": ["evento_id", "edicion_id", "deporte_id", "nombre_evento"],
    "atleta": ["atleta_id", "nombre_completo", "nombre_usado", "sexo", "fecha_nacimiento",
               "lugar_nacimiento", "fecha_fallecimiento", "lugar_fallecimiento",
               "estatura_cm", "peso_kg", "pais_id"],
    "equipo": ["equipo_id", "evento_id", "pais_id", "nombre_equipo"],
    "club": ["club_id", "nombre_club", "pais_id"],
    "atleta_club": ["atleta_id", "club_id"],
    "participacion": ["participacion_id", "atleta_id", "evento_id", "equipo_id",
                       "pais_representado_id", "nombre_en_competencia", "posicion", "medalla"],
}

CLAVES = {
    "pais": ("pais_id",),
    "poblacion": ("pais_id", "anio"),
    "edicion": ("edicion_id",),
    "deporte": ("deporte_id",),
    "evento": ("evento_id",),
    "atleta": ("atleta_id",),
    "equipo": ("equipo_id",),
    "club": ("club_id",),
    "atleta_club": ("atleta_id", "club_id"),
    "participacion": ("participacion_id",),
}


def clave_fila(tabla, fila):
    return tuple(fila[campo] for campo in CLAVES[tabla])


def armar_paso(participaciones_incluidas, datos, carpeta, ya_incluido):
    # Deriva todas las tablas relacionadas a partir de los participacion_id
    # incluidos y escribe solo filas NUEVAS respecto a pasos anteriores. Los
    # equipos se derivan en PostgreSQL después de cada carga, pues el CSV de
    # Fase 1 se genera antes de ejecutar etl/derivar_equipos.sql y está vacío.
    part_por_id = datos["participacion_por_id"]
    filas_part = [part_por_id[pid] for pid in participaciones_incluidas]

    evento_ids = {p["evento_id"] for p in filas_part}
    atleta_ids = {p["atleta_id"] for p in filas_part}

    filas_evento = [datos["evento_por_id"][e] for e in sorted(evento_ids, key=int)]
    edicion_ids = {e["edicion_id"] for e in filas_evento}
    deporte_ids = {e["deporte_id"] for e in filas_evento}

    filas_edicion = [datos["edicion_por_id"][e] for e in sorted(edicion_ids, key=int)]
    filas_deporte = [datos["deporte_por_id"][d] for d in sorted(deporte_ids, key=int)]
    filas_atleta = [datos["atleta_por_id"][a] for a in sorted(atleta_ids, key=int)]

    filas_atleta_club = [
        relacion for relacion in datos["atleta_club"]
        if relacion["atleta_id"] in atleta_ids
    ]
    club_ids = {relacion["club_id"] for relacion in filas_atleta_club}
    filas_club = [
        datos["club_por_id"][club_id] for club_id in sorted(club_ids, key=int)
    ]

    pais_ids = {a["pais_id"] for a in filas_atleta if a["pais_id"]}
    pais_ids |= {p["pais_representado_id"] for p in filas_part if p["pais_representado_id"]}
    pais_ids |= {e["pais_sede_id"] for e in filas_edicion if e["pais_sede_id"]}
    pais_ids |= {club["pais_id"] for club in filas_club if club["pais_id"]}
    filas_pais = [datos["pais_por_id"][p] for p in sorted(pais_ids)]
    filas_poblacion = [
        fila for fila in datos["poblacion"] if fila["pais_id"] in pais_ids
    ]

    tablas = {
        "pais": filas_pais,
        "poblacion": filas_poblacion,
        "edicion": filas_edicion,
        "deporte": filas_deporte,
        "evento": filas_evento,
        "atleta": filas_atleta,
        "equipo": [],
        "club": filas_club,
        "atleta_club": filas_atleta_club,
        "participacion": filas_part,
    }

    resumen = {}
    for tabla, filas in tablas.items():
        previos = ya_incluido.setdefault(tabla, set())
        nuevas = [f for f in filas if clave_fila(tabla, f) not in previos]
        previos.update(clave_fila(tabla, f) for f in nuevas)
        escribir(tabla, nuevas, carpeta)
        resumen[tabla] = len(nuevas)

    print(f"  {os.path.basename(carpeta)} (nuevo en este paso): "
          f"{resumen['participacion']} participaciones, {resumen['atleta']} atletas, "
          f"{resumen['evento']} eventos, {resumen['club']} clubes, "
          f"{resumen['poblacion']} poblaciones, {resumen['pais']} paises")


def cargar_datos():
    datos = {}
    for t in [
        "pais", "poblacion", "edicion", "deporte", "evento", "atleta",
        "club", "atleta_club", "participacion",
    ]:
        filas = leer(t)
        datos[t] = filas
        clave = {
            "pais": "pais_id", "edicion": "edicion_id", "deporte": "deporte_id",
            "evento": "evento_id", "atleta": "atleta_id", "club": "club_id",
            "participacion": "participacion_id",
        }.get(t)
        if clave:
            datos[f"{t}_por_id"] = {r[clave]: r for r in filas}
    return datos


def ronda_por_anio(datos):
    print("Ronda 1: carga por anio (Paris 2024 -> Tokio 2020 -> Rio 2016)")
    ediciones = [("53", "carga1_paris2024"), ("52", "carga2_tokio2020"), ("21", "carga3_rio2016")]
    acumulado = []
    ya_incluido = {}
    for edicion_id, nombre in ediciones:
        nuevas = [p["participacion_id"] for p in datos["participacion"]
                  if datos["evento_por_id"][p["evento_id"]]["edicion_id"] == edicion_id]
        acumulado += nuevas
        carpeta = os.path.join(OUT, "por_anio", nombre)
        armar_paso(acumulado, datos, carpeta, ya_incluido)


def ronda_por_deporte(datos):
    print("Ronda 2: carga por deporte - 100m mujeres (Paris 2024 -> Tokio 2020 -> Rio 2016)")
    ediciones = [("53", "carga1_paris2024"), ("52", "carga2_tokio2020"), ("21", "carga3_rio2016")]
    acumulado = []
    ya_incluido = {}
    for edicion_id, nombre in ediciones:
        eventos_100m = {e["evento_id"] for e in datos["evento"]
                         if e["edicion_id"] == edicion_id
                         and e["deporte_id"] == "7"
                         and "100" in e["nombre_evento"]
                         and ("women" in e["nombre_evento"].lower() or "mujeres" in e["nombre_evento"].lower())
                         and "hurdles" not in e["nombre_evento"].lower()
                         and "relay" not in e["nombre_evento"].lower()
                         and "4 x" not in e["nombre_evento"].lower()
                         and "4 ×" not in e["nombre_evento"].lower()}
        nuevas = [p["participacion_id"] for p in datos["participacion"]
                  if p["evento_id"] in eventos_100m]
        acumulado += nuevas
        carpeta = os.path.join(OUT, "por_deporte", nombre)
        armar_paso(acumulado, datos, carpeta, ya_incluido)


def ronda_por_deportista(datos):
    print("Ronda 3: carga por deportista - Usain Bolt (Atenas 2004 -> Pekin 2008 -> Londres 2012)")
    ediciones = [("22", "carga1_atenas2004"), ("20", "carga2_pekin2008"), ("2", "carga3_londres2012")]
    bolt_id = "103192"
    acumulado = []
    ya_incluido = {}
    for edicion_id, nombre in ediciones:
        nuevas = [p["participacion_id"] for p in datos["participacion"]
                  if p["atleta_id"] == bolt_id
                  and datos["evento_por_id"][p["evento_id"]]["edicion_id"] == edicion_id]
        acumulado += nuevas
        carpeta = os.path.join(OUT, "por_deportista", nombre)
        armar_paso(acumulado, datos, carpeta, ya_incluido)


if __name__ == "__main__":
    datos = cargar_datos()
    ronda_por_anio(datos)
    ronda_por_deporte(datos)
    ronda_por_deportista(datos)
    print("Subconjuntos generados en", OUT)
