# Archivo: fase3/src/script_de_carga.py
# Carga los CSV exportados de PostgreSQL (output_postgres/) en MongoDB.
# Cada paso imprime fecha y hora y queda registrado en fase3/logs/carga_<fecha>.log
import csv
import re
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

from pymongo import ASCENDING, MongoClient

BASE_DIR = Path(__file__).resolve().parent
CSV_DIR = BASE_DIR / "output_postgres"
LOG_DIR = BASE_DIR.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"carga_{datetime.now():%Y%m%d_%H%M%S}.log"

client = MongoClient("mongodb://localhost:27017/")
db = client["olimpiadas_fase3"]

# Correcciones sobre datos incompletos de la Fase 1 (ciudad sede sin dato en las fuentes)
CORRECCIONES_SEDE = {
    "2018 Winter Olympics": "Pyeongchang",
    "2022 Winter Olympics": "Beijing",
}

def log(msg):
    linea = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(linea, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(linea + "\n")


def read_csv(filename):
    """Lee un CSV y devuelve una lista de diccionarios."""
    with open(CSV_DIR / f"{filename}.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def sin_acentos(texto):
    t = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in t if not unicodedata.combining(c)).lower().strip()


def clave_evento(evento, deporte):
    """Clave canónica de un evento. Las fuentes de la Fase 1 nombran el mismo
    evento distinto ("Athletics Men's 100 metres" vs "100 metres, Men (Olympic)")."""
    s = evento.lower().replace("×", "x").replace("(olympic)", "").strip()
    base = re.sub(r"\s*\(.*\)", "", deporte).lower()
    if s.startswith(base + " "):
        s = s[len(base) + 1:]
    m = re.match(r"^(.*), (men|women|mixed|open)\s*$", s)
    if m:
        s = f"{m.group(2)}'s {m.group(1)}"
    return re.sub(r"[^a-z0-9]", "", s)


class UnionFind:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            # el menor id queda como representante
            if rb < ra:
                ra, rb = rb, ra
            self.p[rb] = ra


def main():
    t0 = time.time()
    log("INICIO migración a MongoDB (base olimpiadas_fase3)")

    # Se vacían las colecciones conservando validadores e índices creados por
    # crear_colecciones_indices.js
    for col in ("paises", "ediciones", "atletas"):
        db[col].delete_many({})
    log("Colecciones vaciadas")

    log("Leyendo catálogos desde CSV")
    deportes = {d["deporte_id"]: d["nombre_deporte"] for d in read_csv("deporte")}
    ediciones_cat = {e["edicion_id"]: e for e in read_csv("edicion")}
    eventos = {e["evento_id"]: e for e in read_csv("evento")}
    equipos = {e["equipo_id"]: e for e in read_csv("equipo")}
    clubes = {c["club_id"]: c for c in read_csv("club")}

    atleta_club = {}
    for ac in read_csv("atleta_club"):
        atleta_club.setdefault(ac["atleta_id"], []).append(clubes[ac["club_id"]])

    # ------------------------------------------------------------- paises
    log("Construyendo colección 'paises' (con población anidada)")
    poblacion_por_pais = {}
    for p in read_csv("poblacion"):
        poblacion_por_pais.setdefault(p["pais_id"], []).append(
            {"anio": int(p["anio"]), "poblacion": int(p["poblacion"])}
        )
    paises_docs = []
    nombres_pais = {}
    for p in read_csv("pais"):
        nombres_pais[p["pais_id"]] = p["nombre_pais"]
        paises_docs.append({
            "_id": p["pais_id"],
            "nombre_pais": p["nombre_pais"],
            "nombre_busqueda": sin_acentos(p["nombre_pais"]),
            "region": p["region"] or None,
            "historico_poblacion": sorted(poblacion_por_pais.get(p["pais_id"], []), key=lambda x: x["anio"]),
        })
    db.paises.insert_many(paises_docs)
    log(f"paises insertados: {len(paises_docs)}")

    # ---------------------------------------------------------- ediciones
    log("Construyendo colección 'ediciones'")
    ediciones_docs = []
    for ed in ediciones_cat.values():
        ciudad = ed["ciudad"] or CORRECCIONES_SEDE.get(ed["nombre_edicion"])
        ediciones_docs.append({
            "_id": int(ed["edicion_id"]),
            "nombre_edicion": ed["nombre_edicion"],
            "anio": int(ed["anio"]),
            "temporada": ed["temporada"],
            "ciudad": ciudad or None,
            "pais_sede_id": ed["pais_sede_id"] or None,
        })
    db.ediciones.insert_many(ediciones_docs)
    log(f"ediciones insertadas: {len(ediciones_docs)}")

    # ------------------------------------------- participaciones (dedup)
    log("Leyendo participaciones y unificando duplicados entre fuentes")
    participaciones_raw = read_csv("participacion")
    grupos = {}
    for p in participaciones_raw:
        ev = eventos[p["evento_id"]]
        clave = (p["atleta_id"], ev["edicion_id"], clave_evento(ev["nombre_evento"], deportes[ev["deporte_id"]]))
        grupos.setdefault(clave, []).append(p)

    uf = UnionFind()
    for grupo in grupos.values():
        ids = [g["equipo_id"] for g in grupo if g["equipo_id"]]
        for i in ids:
            uf.find(i)
        for i in ids[1:]:
            uf.union(ids[0], i)

    parts_por_atleta = {}
    for (atleta_id, _, clave), grupo in grupos.items():
        # Se prefiere el registro con posición (fuente Olympedia), luego el que tenga medalla
        grupo.sort(key=lambda g: (not g["posicion"], not g["medalla"]))
        base = grupo[0]
        medalla = next((g["medalla"] for g in grupo if g["medalla"]), None)
        posicion = next((g["posicion"] for g in grupo if g["posicion"]), None)
        pais = next((g["pais_representado_id"] for g in grupo if g["pais_representado_id"]), None)
        eq_id = next((g["equipo_id"] for g in grupo if g["equipo_id"]), None)
        ev = eventos[base["evento_id"]]
        ed = ediciones_cat[ev["edicion_id"]]
        equipo = None
        if eq_id:
            canon = uf.find(eq_id)
            # En Fase 1 el nombre del equipo es el de un integrante; se usa el país representado
            nombre_equipo = nombres_pais.get(pais) or equipos[canon]["nombre_equipo"]
            equipo = {"equipo_id": int(canon), "nombre_equipo": nombre_equipo}
        parts_por_atleta.setdefault(atleta_id, []).append({
            "participacion_id": int(base["participacion_id"]),
            "edicion": {
                "edicion_id": int(ed["edicion_id"]),
                "anio": int(ed["anio"]),
                "temporada": ed["temporada"],
                "nombre_edicion": ed["nombre_edicion"],
            },
            "deporte": deportes[ev["deporte_id"]],
            "evento": ev["nombre_evento"],
            "pais_representado_id": pais,
            "nombre_en_competencia": base["nombre_en_competencia"] or None,
            "posicion": posicion,
            "medalla": medalla,
            "equipo": equipo,
        })
    for lista in parts_por_atleta.values():
        lista.sort(key=lambda x: (x["edicion"]["anio"], x["edicion"]["temporada"], x["evento"]))
    total_antes = len(participaciones_raw)
    total_despues = sum(len(v) for v in parts_por_atleta.values())
    log(f"participaciones: {total_antes} filas CSV -> {total_despues} únicas "
        f"({total_antes - total_despues} duplicados entre fuentes unificados)")

    # ------------------------------------------------------------ atletas
    log("Construyendo colección 'atletas' con participaciones y clubes embebidos")
    atletas_docs = []
    for a in read_csv("atleta"):
        atletas_docs.append({
            "_id": int(a["atleta_id"]),
            "nombre_completo": a["nombre_completo"],
            "nombre_usado": a["nombre_usado"] or None,
            "nombre_busqueda": sin_acentos(a["nombre_completo"]),
            "sexo": a["sexo"] or None,
            "fecha_nacimiento": a["fecha_nacimiento"] or None,
            "lugar_nacimiento": a["lugar_nacimiento"] or None,
            "fecha_fallecimiento": a["fecha_fallecimiento"] or None,
            "lugar_fallecimiento": a["lugar_fallecimiento"] or None,
            "estatura_cm": int(a["estatura_cm"]) if a["estatura_cm"] else None,
            "peso_kg": int(a["peso_kg"]) if a["peso_kg"] else None,
            "pais_origen_id": a["pais_id"] or None,
            "clubes": [
                {"club_id": int(c["club_id"]), "nombre_club": c["nombre_club"], "pais_id": c["pais_id"]}
                for c in atleta_club.get(a["atleta_id"], [])
            ],
            "participaciones": parts_por_atleta.get(a["atleta_id"], []),
        })
    for i in range(0, len(atletas_docs), 20000):
        db.atletas.insert_many(atletas_docs[i:i + 20000], ordered=False)
    log(f"atletas insertados: {len(atletas_docs)}")

    # ------------------------------------------------------------ índices
    log("Asegurando índices")
    db.paises.create_index([("nombre_pais", ASCENDING)], name="nombre_pais_1")
    db.paises.create_index([("nombre_busqueda", ASCENDING)], name="nombre_busqueda_1")
    db.ediciones.create_index([("pais_sede_id", ASCENDING)], name="pais_sede_id_1")
    db.ediciones.create_index([("anio", ASCENDING), ("temporada", ASCENDING)], name="anio_1_temporada_1")
    db.atletas.create_index([("nombre_completo", ASCENDING)], name="nombre_completo_1")
    db.atletas.create_index([("nombre_usado", ASCENDING)], name="nombre_usado_1")
    db.atletas.create_index([("nombre_busqueda", ASCENDING)], name="nombre_busqueda_1")
    db.atletas.create_index([("pais_origen_id", ASCENDING)], name="pais_origen_id_1")
    db.atletas.create_index([("participaciones.pais_representado_id", ASCENDING)], name="part_pais_1")
    db.atletas.create_index([("participaciones.edicion.anio", ASCENDING)], name="part_anio_1")
    db.atletas.create_index([("participaciones.deporte", ASCENDING)], name="part_deporte_1")
    db.atletas.create_index([("participaciones.medalla", ASCENDING)], name="part_medalla_1")

    log(f"Totales en MongoDB -> paises: {db.paises.count_documents({})}, "
        f"ediciones: {db.ediciones.count_documents({})}, atletas: {db.atletas.count_documents({})}")
    log(f"FIN migración. Duración: {time.time() - t0:.1f} s. Bitácora: {LOG_FILE}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        log(f"ERROR: {exc!r}")
        sys.exit(1)
