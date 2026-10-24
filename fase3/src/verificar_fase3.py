"""Verificación integral y repetible de la entrega de Fase 3.

Ejecutar desde cualquier carpeta con:
    python fase3/src/verificar_fase3.py

El proceso termina con código 0 si todo cumple y con código 1 si una prueba
falla. La evidencia se guarda en fase3/logs/verificacion_fase3.log.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from pymongo import MongoClient


BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR.parent / "logs" / "verificacion_fase3.log"
URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.environ.get("MONGO_DB", "olimpiadas_fase3")
EXPECTED_INDEXES = {
    "paises": {"_id_", "nombre_pais_1", "nombre_busqueda_1"},
    "ediciones": {"_id_", "pais_sede_id_1", "anio_1_temporada_1"},
    "atletas": {
        "_id_", "nombre_completo_1", "nombre_usado_1", "nombre_busqueda_1",
        "pais_origen_id_1", "part_pais_1", "part_anio_1", "part_deporte_1",
        "part_medalla_1",
    },
}


class Verificador:
    def __init__(self):
        LOG_FILE.parent.mkdir(exist_ok=True)
        LOG_FILE.write_text("", encoding="utf-8")
        self.ok = 0
        self.fallos = []

    def log(self, mensaje):
        linea = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {mensaje}"
        print(linea, flush=True)
        with LOG_FILE.open("a", encoding="utf-8") as archivo:
            archivo.write(linea + "\n")

    def comprobar(self, nombre, condicion, detalle=""):
        if condicion:
            self.ok += 1
            self.log(f"OK   {nombre}" + (f": {detalle}" if detalle else ""))
        else:
            self.fallos.append(nombre)
            self.log(f"FALLO {nombre}" + (f": {detalle}" if detalle else ""))


def contiene_etapa(plan, etapa):
    if isinstance(plan, dict):
        return plan.get("stage") == etapa or any(contiene_etapa(v, etapa) for v in plan.values())
    if isinstance(plan, list):
        return any(contiene_etapa(v, etapa) for v in plan)
    return False


def medallas_atleta(atleta):
    return {
        nombre: sum(p.get("medalla") == nombre for p in atleta["participaciones"])
        for nombre in ("Oro", "Plata", "Bronce")
    }


def totales_medallas_pais(db, pais, anio=None):
    condicion = {"pais_representado_id": pais}
    if anio:
        condicion["edicion.anio"] = anio
    match = {f"participaciones.{k}": v for k, v in condicion.items()}
    resultados = db.atletas.aggregate([
        {"$match": {"participaciones": {"$elemMatch": condicion}}},
        {"$unwind": "$participaciones"},
        {"$match": match},
        {"$match": {"participaciones.medalla": {"$in": ["Oro", "Plata", "Bronce"]}}},
        {"$group": {
            "_id": {
                "medalla": "$participaciones.medalla",
                "equipo": "$participaciones.equipo.equipo_id",
                "individual": {"$cond": [
                    {"$ifNull": ["$participaciones.equipo", False]},
                    0,
                    "$participaciones.participacion_id",
                ]},
            }
        }},
        {"$group": {"_id": "$_id.medalla", "total": {"$sum": 1}}},
    ])
    return {r["_id"]: r["total"] for r in resultados}


def ejecutar_cli(*argumentos):
    proceso = subprocess.run(
        [sys.executable, str(BASE_DIR / "script_de_consultas.py"), *argumentos, "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    if proceso.returncode != 0:
        raise RuntimeError(proceso.stderr.strip() or f"código {proceso.returncode}")
    return json.loads(proceso.stdout)


def main():
    v = Verificador()
    inicio = time.perf_counter()
    v.log(f"INICIO verificación de {DB_NAME} en {URI}")

    try:
        cliente = MongoClient(URI, serverSelectionTimeoutMS=5000)
        v.comprobar("conexión MongoDB", cliente.admin.command("ping").get("ok") == 1)
    except Exception as exc:  # noqa: BLE001
        v.comprobar("conexión MongoDB", False, repr(exc))
        v.log("No se pueden continuar las pruebas sin conexión.")
        return 1

    db = cliente[DB_NAME]
    colecciones = set(db.list_collection_names())
    v.comprobar("exactamente tres colecciones", colecciones == set(EXPECTED_INDEXES), str(sorted(colecciones)))

    conteos = {c: db[c].count_documents({}) for c in EXPECTED_INDEXES}
    esperados = {"paises": 234, "ediciones": 64, "atletas": 244540}
    v.comprobar("conteos de documentos", conteos == esperados, str(conteos))

    info = {c["name"]: c for c in db.list_collections()}
    for coleccion, requeridos in {
        "paises": {"_id", "nombre_pais", "historico_poblacion"},
        "ediciones": {"_id", "nombre_edicion", "anio", "temporada"},
        "atletas": {"_id", "nombre_completo", "participaciones", "clubes"},
    }.items():
        schema = info[coleccion]["options"]["validator"]["$jsonSchema"]
        v.comprobar(f"validador JSON de {coleccion}", set(schema["required"]) == requeridos)
        indices = {i["name"] for i in db[coleccion].list_indexes()}
        v.comprobar(f"índices de {coleccion}", indices == EXPECTED_INDEXES[coleccion], str(sorted(indices)))

    total_participaciones = next(db.atletas.aggregate([
        {"$project": {"n": {"$size": "$participaciones"}}},
        {"$group": {"_id": None, "total": {"$sum": "$n"}}},
    ]))["total"]
    v.comprobar("participaciones consolidadas", total_participaciones == 534950, str(total_participaciones))
    v.comprobar("atletas sin participación documentados", db.atletas.count_documents({"participaciones": {"$size": 0}}) == 232)

    duplicados = list(db.atletas.aggregate([
        {"$unwind": "$participaciones"},
        {"$group": {
            "_id": {
                "atleta": "$_id",
                "edicion": "$participaciones.edicion.edicion_id",
                "evento": "$participaciones.evento",
            },
            "n": {"$sum": 1},
        }},
        {"$match": {"n": {"$gt": 1}}},
        {"$limit": 1},
    ], allowDiskUse=True))
    v.comprobar("sin participaciones exactas duplicadas", not duplicados, str(duplicados[:1]))

    huerfanas = list(db.atletas.aggregate([
        {"$unwind": "$participaciones"},
        {"$match": {"participaciones.pais_representado_id": {"$ne": None}}},
        {"$group": {"_id": "$participaciones.pais_representado_id"}},
        {"$lookup": {"from": "paises", "localField": "_id", "foreignField": "_id", "as": "pais"}},
        {"$match": {"pais": {"$size": 0}}},
    ]))
    v.comprobar("países representados sin referencias huérfanas", not huerfanas, str(huerfanas))
    nulas = next(db.atletas.aggregate([
        {"$unwind": "$participaciones"},
        {"$match": {"participaciones.pais_representado_id": None}},
        {"$count": "n"},
    ]), {"n": 0})["n"]
    v.comprobar("todas las participaciones tienen país representado", nulas == 0, str(nulas))

    hala = db.atletas.find_one({"nombre_usado": "Hala Fattouh"})
    v.comprobar(
        "corrección LBN -> LIB conserva atleta y participación",
        bool(hala) and any(p["pais_representado_id"] == "LIB" for p in hala["participaciones"]),
    )

    bolt = db.atletas.find_one({"nombre_usado": "Usain Bolt"})
    phelps = db.atletas.find_one({"nombre_usado": "Michael Phelps"})
    biles = db.atletas.find_one({"nombre_usado": "Simone Biles"})
    v.comprobar("Usain Bolt: 8 oros", medallas_atleta(bolt) == {"Oro": 8, "Plata": 0, "Bronce": 0})
    v.comprobar("Michael Phelps: 23/3/2", medallas_atleta(phelps) == {"Oro": 23, "Plata": 3, "Bronce": 2})
    biles_2016 = {**biles, "participaciones": [p for p in biles["participaciones"] if p["edicion"]["anio"] == 2016]}
    v.comprobar("Simone Biles 2016: 4 oros y 1 bronce", medallas_atleta(biles_2016) == {"Oro": 4, "Plata": 0, "Bronce": 1})

    v.comprobar("Jamaica: historial 37/48/36", totales_medallas_pais(db, "JAM") == {"Oro": 37, "Plata": 48, "Bronce": 36})
    v.comprobar("Guatemala 2024: 1 oro y 1 bronce", totales_medallas_pais(db, "GUA", 2024) == {"Oro": 1, "Bronce": 1})
    sedes_usa = list(db.ediciones.find({"pais_sede_id": "USA"}))
    v.comprobar("Estados Unidos: 8 ediciones sede", len(sedes_usa) == 8, str(len(sedes_usa)))
    v.comprobar("correcciones de ciudad sede", all([
        db.ediciones.count_documents({"nombre_edicion": "2018 Winter Olympics", "ciudad": "Pyeongchang"}) == 1,
        db.ediciones.count_documents({"nombre_edicion": "2022 Winter Olympics", "ciudad": "Beijing"}) == 1,
    ]))

    explain_nombre = db.command("explain", {"find": "atletas", "filter": {"nombre_completo": bolt["nombre_completo"]}}, verbosity="executionStats")
    explain_pais = db.command("explain", {"find": "atletas", "filter": {"participaciones.pais_representado_id": "JAM"}}, verbosity="executionStats")
    v.comprobar("búsqueda de atleta usa índice", contiene_etapa(explain_nombre["queryPlanner"]["winningPlan"], "IXSCAN"))
    v.comprobar("búsqueda por país usa índice multikey", contiene_etapa(explain_pais["queryPlanner"]["winningPlan"], "IXSCAN"))

    try:
        cli_atleta = ejecutar_cli("atleta", "Simone Biles", "--pais", "USA", "--anio", "2016")
        v.comprobar("CLI atleta con filtros y JSON", cli_atleta["atletas"][0]["medallas"] == {"Oro": 4, "Plata": 0, "Bronce": 1})
    except Exception as exc:  # noqa: BLE001
        v.comprobar("CLI atleta con filtros y JSON", False, repr(exc))
    try:
        cli_pais = ejecutar_cli("pais", "GUA", "--anio", "2024")
        v.comprobar("CLI país con filtro y JSON", cli_pais["totales"] == {"Oro": 1, "Plata": 0, "Bronce": 1, "participaciones": 16})
    except Exception as exc:  # noqa: BLE001
        v.comprobar("CLI país con filtro y JSON", False, repr(exc))

    duracion = time.perf_counter() - inicio
    v.log(f"FIN: {v.ok} pruebas correctas, {len(v.fallos)} fallidas, duración {duracion:.1f} s")
    if v.fallos:
        v.log("Pruebas fallidas: " + ", ".join(v.fallos))
        return 1
    v.log(f"RESULTADO FINAL: APROBADO. Evidencia: {LOG_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
