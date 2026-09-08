"""
Script de ETL
Junta todos los CSVs y los mete en las tablas del modelo (src/schema.sql).
"""

import csv
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASETS = ROOT / "datasets"
OUT = ROOT / "etl-csvs"
OUT.mkdir(exist_ok=True)


# ==================================
# utilidades varias
# ==================================

def norm_name(s):
    if not s:
        return ""
    s = s.replace("•", " ")  # separador "•" usado en bios.csv
    return re.sub(r"\s+", " ", s).strip()


def name_key(s):
    # quitar acentos para comparar nombres bien (ej: "Cenk Ildem" == "Cenk İldem")
    folded = norm_name(s).casefold()
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFKD", folded) if not unicodedata.combining(c)
    )
    return sin_acentos


def clean(s):
    s = (s or "").strip()
    return s or None


BORN_FULL = re.compile(
    r"^(?P<day>\d{1,2}) (?P<month>[A-Za-z]+) (?P<year>\d{4})"
    r"(?: in (?P<place>.+?))?(?: \((?P<code>[A-Z]{3})\))?$"
)
BORN_YEAR_ONLY = re.compile(
    r"^(?P<year>\d{4})(?: in (?P<place>.+?))?(?: \((?P<code>[A-Z]{3})\))?$"
)
BORN_PLACE_ONLY = re.compile(r"^in (?P<place>.+?)(?: \((?P<code>[A-Z]{3})\))?$")
TRAILING_CODE = re.compile(r"\(([A-Z]{3})\)\s*$")


def parse_when(raw):
    """Saca la fecha, lugar y pais de nacimiento/muerte. A veces viene incompleto en el csv original."""
    raw = (raw or "").strip()
    if not raw:
        return None, None, None

    m = BORN_FULL.match(raw)
    if m:
        try:
            d = datetime.strptime(f"{m['day']} {m['month']} {m['year']}", "%d %B %Y").date()
        except ValueError:
            d = None
        return d, m["place"], m["code"]

    m = BORN_YEAR_ONLY.match(raw)
    if m:
        return None, m["place"], m["code"]

    m = BORN_PLACE_ONLY.match(raw)
    if m:
        return None, m["place"], m["code"]

    m = TRAILING_CODE.search(raw)
    return None, None, m.group(1) if m else None


CM_PAT = re.compile(r"(\d+)\s*cm")
KG_PAT = re.compile(r"(\d+)\s*kg")


def parse_measurements(raw):
    if not raw:
        return None, None
    cm_m = CM_PAT.search(raw)
    kg_m = KG_PAT.search(raw)
    return (int(cm_m.group(1)) if cm_m else None,
            int(kg_m.group(1)) if kg_m else None)


def to_int(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


MEDAL_ES = {"Gold": "Oro", "Silver": "Plata", "Bronze": "Bronce"}
MEDAL_EMPTY = {"", "NA", "No medal", "null", "None", "N/A"}


def normalize_medal(raw):
    raw = (raw or "").strip()
    if raw in MEDAL_EMPTY:
        return None
    return MEDAL_ES.get(raw, raw)


# pais

# algunos codigos que vienen raros
COUNTRY_ALIASES = {
    "SGP": "SIN",  # Singapur: ISO usa SGP, el catalogo IOC trae SIN
}

# equipos raros que no son paises
EXTRA_COUNTRIES = {
    "ROC": "Comite Olimpico Ruso",
    "EOR": "Equipo Olimpico de Refugiados",
    "AIN": "Atletas Individuales Neutrales",
    "COR": "Corea Unificada",
}

pais = {}  # pais_id -> {"nombre_pais": str, "region": None}


def load_pais():
    with open(DATASETS / "noc_regions.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            code = row["NOC"].strip()
            if not code:
                continue
            pais[code] = {"nombre_pais": row["region"].strip() or code, "region": None}
    for code, name in EXTRA_COUNTRIES.items():
        pais.setdefault(code, {"nombre_pais": name, "region": None})


def resolve_country(raw):
    code = (raw or "").strip().upper()
    if not code:
        return None
    code = COUNTRY_ALIASES.get(code, code)
    return code if code in pais else None


# deportes

deporte_by_key = {}
_next_deporte_id = [1]


def get_deporte_id(raw_name):
    name = norm_name(raw_name)
    if not name:
        return None
    key = name.casefold()
    rec = deporte_by_key.get(key)
    if rec is None:
        rec = {"id": _next_deporte_id[0], "nombre_deporte": name}
        deporte_by_key[key] = rec
        _next_deporte_id[0] += 1
    return rec["id"]


# ==================================
# edicion (se usa el nombre completo para no cruzar datos, ej: "1912 Summer Olympics")
# ==================================

HOST_COUNTRY_BY_CITY = {
    "Athina": "GRE", "Paris": "FRA", "St. Louis": "USA", "London": "GBR",
    "Stockholm": "SWE", "Antwerpen": "BEL", "Chamonix": "FRA", "Amsterdam": "NED",
    "Sankt Moritz": "SUI", "Los Angeles": "USA", "Berlin": "GER",
    "Garmisch-Partenkirchen": "GER", "Helsinki": "FIN", "Oslo": "NOR",
    "Melbourne": "AUS", "Cortina d'Ampezzo": "ITA", "Roma": "ITA",
    "Squaw Valley": "USA", "Tokyo": "JPN", "Innsbruck": "AUT",
    "Mexico City": "MEX", "Grenoble": "FRA", "Munich": "GER", "Sapporo": "JPN",
    "Montreal": "CAN", "Moskva": "URS", "Lake Placid": "USA", "Sarajevo": "YUG",
    "Seoul": "KOR", "Calgary": "CAN", "Barcelona": "ESP", "Albertville": "FRA",
    "Lillehammer": "NOR", "Atlanta": "USA", "Nagano": "JPN", "Sydney": "AUS",
    "Salt Lake City": "USA", "Torino": "ITA", "Beijing": "CHN", "Vancouver": "CAN",
    "Sochi": "RUS", "Rio de Janeiro": "BRA",
}

# Estas ediciones vienen incompletas en results.csv (falta la ciudad)
HOST_COUNTRY_BY_EDITION = {
    "2018 Winter Olympics": "KOR",
    "2022 Winter Olympics": "CHN",
}

edicion_by_name = {}
_next_edicion_id = [1]


def edition_name(year, season_en):
    return f"{year} {season_en} Olympics"


def get_edicion(nombre_edicion, anio, temporada, ciudad=None, pais_sede_id=None):
    rec = edicion_by_name.get(nombre_edicion)
    if rec is None:
        rec = {
            "id": _next_edicion_id[0],
            "nombre_edicion": nombre_edicion,
            "anio": anio,
            "temporada": temporada,
            "ciudad": ciudad,
            "pais_sede_id": pais_sede_id,
        }
        edicion_by_name[nombre_edicion] = rec
        _next_edicion_id[0] += 1
    else:
        if not rec["ciudad"] and ciudad:
            rec["ciudad"] = ciudad
        if not rec["pais_sede_id"] and pais_sede_id:
            rec["pais_sede_id"] = pais_sede_id
    return rec["id"]


# ==================================
# evento
# ==================================

evento_by_key = {}
_next_evento_id = [1]


def get_evento(edicion_id, deporte_id, nombre_evento_raw):
    nombre_evento = norm_name(nombre_evento_raw)
    key = (edicion_id, deporte_id, nombre_evento.casefold())
    rec = evento_by_key.get(key)
    if rec is None:
        rec = {
            "id": _next_evento_id[0],
            "edicion_id": edicion_id,
            "deporte_id": deporte_id,
            "nombre_evento": nombre_evento,
        }
        evento_by_key[key] = rec
        _next_evento_id[0] += 1
    return rec["id"]


# deduplicacion de atletas

atleta_by_name = {}  # name_key -> [rec, ...] (varios atletas homonimos)
_next_atleta_id = [1]


def find_or_create_atleta(nombre, sexo=None, pais_id=None, **extra):
    key = name_key(nombre)
    if not key:
        return None
    bucket = atleta_by_name.setdefault(key, [])

    for rec in bucket:
        # si hay un dato diferente entonces es otra persona
        if sexo and rec["sexo"] and rec["sexo"] != sexo:
            continue
        if pais_id and rec["pais_id"] and rec["pais_id"] != pais_id:
            continue
        # es el mismo man, llenamos los datos
        if sexo and not rec["sexo"]:
            rec["sexo"] = sexo
        if pais_id and not rec["pais_id"]:
            rec["pais_id"] = pais_id
        for k, v in extra.items():
            if v is not None and not rec.get(k):
                rec[k] = v
        return rec

    rec = {
        "id": _next_atleta_id[0],
        "nombre_completo": extra.get("nombre_completo") or norm_name(nombre),
        "nombre_usado": extra.get("nombre_usado") or norm_name(nombre),
        "sexo": sexo,
        "fecha_nacimiento": extra.get("fecha_nacimiento"),
        "lugar_nacimiento": extra.get("lugar_nacimiento"),
        "fecha_fallecimiento": extra.get("fecha_fallecimiento"),
        "lugar_fallecimiento": extra.get("lugar_fallecimiento"),
        "estatura_cm": extra.get("estatura_cm"),
        "peso_kg": extra.get("peso_kg"),
        "pais_id": pais_id,
    }
    _next_atleta_id[0] += 1
    bucket.append(rec)
    return rec


def register_alias(nombre, rec):
    """Guarda los alias para encontrarlos mas facil despues."""
    key = name_key(nombre)
    if key:
        atleta_by_name.setdefault(key, []).append(rec)


# clubes

club_by_key = {}
_next_club_id = [1]
atleta_club_pairs = set()

AFFIL_TRAILING_CODE = re.compile(r"\(([A-Z]{3})\)\s*$")


def get_club(nombre, pais_id):
    nombre = norm_name(nombre)
    if not nombre:
        return None
    key = (nombre.casefold(), pais_id)
    rec = club_by_key.get(key)
    if rec is None:
        rec = {"id": _next_club_id[0], "nombre_club": nombre, "pais_id": pais_id}
        club_by_key[key] = rec
        _next_club_id[0] += 1
    return rec["id"]


def process_affiliations(raw, atleta_id):
    if not raw:
        return
    for part in raw.split(" / "):
        part = part.strip()
        if not part:
            continue
        m = AFFIL_TRAILING_CODE.search(part)
        club_country = resolve_country(m.group(1)) if m else None
        sin_codigo = AFFIL_TRAILING_CODE.sub("", part).strip().rstrip(",").strip()
        club_name = sin_codigo.split(",")[0].strip()
        club_id = get_club(club_name, club_country)
        if club_id:
            atleta_club_pairs.add((atleta_id, club_id))


# participaciones

participaciones = {}
_next_participacion_id = [1]


def add_participacion(atleta_id, evento_id, pais_representado_id,
                       nombre_en_competencia=None, posicion=None, medalla=None,
                       equipo_id=None):
    if atleta_id is None or evento_id is None:
        return
    key = (atleta_id, evento_id, pais_representado_id)
    rec = participaciones.get(key)
    if rec is None:
        participaciones[key] = {
            "id": _next_participacion_id[0],
            "atleta_id": atleta_id,
            "evento_id": evento_id,
            "equipo_id": equipo_id,
            "pais_representado_id": pais_representado_id,
            "nombre_en_competencia": nombre_en_competencia,
            "posicion": posicion,
            "medalla": medalla,
        }
        _next_participacion_id[0] += 1
    else:
        if not rec["nombre_en_competencia"] and nombre_en_competencia:
            rec["nombre_en_competencia"] = nombre_en_competencia
        if not rec["posicion"] and posicion:
            rec["posicion"] = posicion
        if not rec["medalla"] and medalla:
            rec["medalla"] = medalla
        if not rec["equipo_id"] and equipo_id:
            rec["equipo_id"] = equipo_id


# procesando bios.csv

bios_id_to_atleta = {}


def process_bios():
    path = DATASETS / "bios.csv"
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        for row in csv.DictReader(f):
            full_name = norm_name(row["Full name"])
            used_name = norm_name(row["Used name"]) or full_name
            primary_name = used_name or full_name
            if not primary_name:
                continue

            sexo = {"Male": "M", "Female": "F"}.get(row["Sex"])
            born_date, born_place, born_code = parse_when(row["Born"])
            died_date, died_place, _died_code = parse_when(row["Died"])
            pais_id = resolve_country(born_code)
            estatura_cm, peso_kg = parse_measurements(row["Measurements"])

            rec = find_or_create_atleta(
                primary_name,
                sexo=sexo,
                pais_id=pais_id,
                nombre_completo=full_name,
                nombre_usado=used_name,
                fecha_nacimiento=born_date,
                lugar_nacimiento=born_place,
                fecha_fallecimiento=died_date,
                lugar_fallecimiento=died_place,
                estatura_cm=estatura_cm,
                peso_kg=peso_kg,
            )
            if full_name and full_name.casefold() != primary_name.casefold():
                register_alias(full_name, rec)

            bios_id_to_atleta[row["athlete_id"]] = rec["id"]
            process_affiliations(row["Affiliations"], rec["id"])


# mapeo para los otros csvs que vienen parecido

def process_flat_source(filename, colmap, has_height_weight):
    path = DATASETS / filename
    local_atleta = {}  # id propio de la fuente -> atleta_id unificado
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        for row in csv.DictReader(f):
            name = norm_name(row.get(colmap["name"]))
            if not name:
                continue
            sid = row.get(colmap["id"])
            noc = resolve_country(row.get(colmap["noc"]))
            sexo = (row.get(colmap["sex"]) or "").strip().upper()[:1] or None
            if sexo not in ("M", "F"):
                sexo = None

            if sid not in local_atleta:
                extra = {}
                if has_height_weight:
                    h = to_int(row.get(colmap["height"]))
                    w = to_int(row.get(colmap["weight"]))
                    if h:
                        extra["estatura_cm"] = h
                    if w:
                        extra["peso_kg"] = w
                rec = find_or_create_atleta(name, sexo=sexo, pais_id=noc, **extra)
                local_atleta[sid] = rec["id"] if rec else None
            atleta_id = local_atleta[sid]

            year = (row.get(colmap["year"]) or "").strip()
            season_en = (row.get(colmap["season"]) or "").strip()
            temporada = "Invierno" if season_en.lower().startswith("win") else "Verano"
            nombre_ed = edition_name(year, season_en) if year and season_en else None
            if nombre_ed is None:
                continue
            ciudad = clean(row.get(colmap["city"]))
            host = HOST_COUNTRY_BY_CITY.get(ciudad) if ciudad else None
            edicion_id = get_edicion(nombre_ed, to_int(year), temporada, ciudad, host)

            deporte_id = get_deporte_id(row.get(colmap["sport"]))
            if deporte_id is None:
                continue
            evento_id = get_evento(edicion_id, deporte_id, row.get(colmap["event"]))

            medalla = normalize_medal(row.get(colmap["medal"]))
            add_participacion(atleta_id, evento_id, noc,
                               nombre_en_competencia=name, medalla=medalla)


ATHLETE_EVENTS_COLMAP = {
    "id": "ID", "name": "Name", "sex": "Sex", "noc": "NOC",
    "year": "Year", "season": "Season", "city": "City",
    "sport": "Sport", "event": "Event", "medal": "Medal",
    "height": "Height", "weight": "Weight",
}
OLYMPICS_DATASET_COLMAP = {
    "id": "player_id", "name": "Name", "sex": "Sex", "noc": "NOC",
    "year": "Year", "season": "Season", "city": "City",
    "sport": "Sport", "event": "Event", "medal": "Medal",
}
DATALAB_COLMAP = {
    "id": "id", "name": "name", "sex": "sex", "noc": "noc",
    "year": "year", "season": "season", "city": "city",
    "sport": "sport", "event": "event", "medal": "medal",
    "height": "height", "weight": "weight",
}


# cargar results.csv

GAMES_YEAR = re.compile(r"(\d{4})")


def process_results():
    path = DATASETS / "results.csv"
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        for row in csv.DictReader(f):
            atleta_id = bios_id_to_atleta.get(row["athlete_id"])
            if atleta_id is None:
                continue

            games = (row["Games"] or "").strip()
            if not games:
                continue
            temporada = "Invierno" if "winter" in games.lower() else "Verano"
            ym = GAMES_YEAR.search(games)
            anio = int(ym.group(1)) if ym else None
            host = HOST_COUNTRY_BY_EDITION.get(games)
            edicion_id = get_edicion(games, anio, temporada, None, host)

            deporte_id = get_deporte_id(row["Discipline"])
            if deporte_id is None:
                continue
            evento_id = get_evento(edicion_id, deporte_id, row["Event"])

            noc = resolve_country(row["NOC"])
            medalla = normalize_medal(row["Medal"])
            posicion = clean(row["Pos"])
            nombre_comp = norm_name(row["As"])
            add_participacion(atleta_id, evento_id, noc,
                               nombre_en_competencia=nombre_comp,
                               posicion=posicion, medalla=medalla)


# ==================================
# poblacion
# ==================================

# arreglos para codigos raros del banco mundial
ISO_TO_IOC = {
    "DEU": "GER", "CHE": "SUI", "NLD": "NED", "GRC": "GRE", "DNK": "DEN",
    "PRT": "POR", "HRV": "CRO", "ZAF": "RSA", "LBN": "LIB", "VNM": "VIE",
    "MMR": "MYA", "PHL": "PHI", "IDN": "INA", "TCD": "CHA", "COG": "CGO",
    "NER": "NIG", "BRN": "BRU", "ARE": "UAE", "SAU": "KSA", "TWN": "TPE",
}


def process_population():
    path = DATASETS / "populations.csv"
    pop_map = {}
    skipped_codes = set()
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        header = next(reader)
        year_cols = [(i, h.strip()) for i, h in enumerate(header) if h.strip().isdigit()]
        for row in reader:
            if len(row) < 3:
                continue
            code = row[1].strip().upper()
            pais_id = resolve_country(ISO_TO_IOC.get(code, code))
            if not pais_id:
                skipped_codes.add(code)
                continue
            for idx, year in year_cols:
                if idx >= len(row):
                    continue
                pop = to_int(row[idx])
                if pop is None:
                    continue
                pop_map.setdefault((pais_id, int(year)), pop)
    return pop_map, skipped_codes


# generar los archivos de salida

def write_csv(name, header, rows):
    path = OUT / name
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for row in rows:
            w.writerow(["" if v is None else v for v in row])
    return path


def main():
    load_pais()
    process_bios()
    process_flat_source("athlete_events.csv", ATHLETE_EVENTS_COLMAP, has_height_weight=True)
    process_flat_source("olympics_dataset.csv", OLYMPICS_DATASET_COLMAP, has_height_weight=False)
    process_flat_source("datalab_export.csv", DATALAB_COLMAP, has_height_weight=True)
    process_results()
    pop_map, skipped_pop_codes = process_population()

    write_csv("pais.csv", ["pais_id", "nombre_pais", "region"],
              [(pid, d["nombre_pais"], d["region"]) for pid, d in sorted(pais.items())])

    write_csv("poblacion.csv", ["pais_id", "anio", "poblacion"],
              [(pid, anio, pop) for (pid, anio), pop in sorted(pop_map.items())])

    all_atletas = [rec for bucket in atleta_by_name.values() for rec in bucket]
    all_atletas = list({r["id"]: r for r in all_atletas}.values())
    all_atletas.sort(key=lambda r: r["id"])
    write_csv(
        "atleta.csv",
        ["atleta_id", "nombre_completo", "nombre_usado", "sexo", "fecha_nacimiento",
         "lugar_nacimiento", "fecha_fallecimiento", "lugar_fallecimiento",
         "estatura_cm", "peso_kg", "pais_id"],
        [(r["id"], r["nombre_completo"], r["nombre_usado"], r["sexo"],
          r["fecha_nacimiento"], r["lugar_nacimiento"], r["fecha_fallecimiento"],
          r["lugar_fallecimiento"], r["estatura_cm"], r["peso_kg"], r["pais_id"])
         for r in all_atletas],
    )

    write_csv(
        "edicion.csv",
        ["edicion_id", "nombre_edicion", "anio", "temporada", "ciudad", "pais_sede_id"],
        [(r["id"], r["nombre_edicion"], r["anio"], r["temporada"], r["ciudad"], r["pais_sede_id"])
         for r in sorted(edicion_by_name.values(), key=lambda r: r["id"])],
    )

    write_csv(
        "deporte.csv", ["deporte_id", "nombre_deporte"],
        [(r["id"], r["nombre_deporte"]) for r in sorted(deporte_by_key.values(), key=lambda r: r["id"])],
    )

    write_csv(
        "evento.csv", ["evento_id", "edicion_id", "deporte_id", "nombre_evento"],
        [(r["id"], r["edicion_id"], r["deporte_id"], r["nombre_evento"])
         for r in sorted(evento_by_key.values(), key=lambda r: r["id"])],
    )

    write_csv("equipo.csv", ["equipo_id", "evento_id", "pais_id", "nombre_equipo"], [])

    write_csv(
        "club.csv", ["club_id", "nombre_club", "pais_id"],
        [(r["id"], r["nombre_club"], r["pais_id"]) for r in sorted(club_by_key.values(), key=lambda r: r["id"])],
    )

    write_csv("atleta_club.csv", ["atleta_id", "club_id"], sorted(atleta_club_pairs))

    write_csv(
        "participacion.csv",
        ["participacion_id", "atleta_id", "evento_id", "equipo_id", "pais_representado_id",
         "nombre_en_competencia", "posicion", "medalla"],
        [(r["id"], r["atleta_id"], r["evento_id"], r["equipo_id"], r["pais_representado_id"],
          r["nombre_en_competencia"], r["posicion"], r["medalla"])
         for r in sorted(participaciones.values(), key=lambda r: r["id"])],
    )

    homonimos = sum(1 for bucket in atleta_by_name.values()
                     if len({r["id"] for r in bucket}) > 1)

    print("=== resumen de carga ===")
    print(f"pais:            {len(pais)}")
    print(f"poblacion:       {len(pop_map)} (codigos de pais sin match: {len(skipped_pop_codes)})")
    print(f"atleta:          {len(all_atletas)}  (nombres con homonimos detectados: {homonimos})")
    print(f"edicion:         {len(edicion_by_name)}")
    print(f"deporte:         {len(deporte_by_key)}")
    print(f"evento:          {len(evento_by_key)}")
    print(f"club:            {len(club_by_key)}")
    print(f"atleta_club:     {len(atleta_club_pairs)}")
    print(f"participacion:   {len(participaciones)}")
    print(f"CSVs escritos en: {OUT}")


if __name__ == "__main__":
    main()
