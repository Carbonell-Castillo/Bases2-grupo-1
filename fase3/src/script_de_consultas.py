# Archivo: fase3/src/script_de_consultas.py
# Consultas de atletas y países sobre MongoDB (base olimpiadas_fase3).
#
#   python script_de_consultas.py atleta "Usain Bolt" [--deporte Athletics] [--pais JAM] [--anio 2012] [--medalla Oro] [--json]
#   python script_de_consultas.py pais   "Guatemala"  [--anio 2016] [--deporte Judo] [--medalla Oro] [--detalle] [--json]
import argparse
import json
import re
import sys
import time
import unicodedata
from datetime import datetime

from pymongo import MongoClient

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=5000)
db = client["olimpiadas_fase3"]

MEDALLAS = ("Oro", "Plata", "Bronce")
MAX_ATLETAS = 20


def sin_acentos(texto):
    t = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in t if not unicodedata.combining(c)).lower().strip()


def normaliza_medalla(valor):
    if not valor:
        return None
    mapa = {"oro": "Oro", "gold": "Oro", "plata": "Plata", "silver": "Plata", "bronce": "Bronce", "bronze": "Bronce"}
    return mapa.get(valor.casefold(), valor.capitalize())


def encabezado(titulo):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {titulo}")


# ===================================================================== ATLETA
def buscar_atletas_por_nombre(nombre):
    """Búsqueda escalonada: exacto -> sin acentos/mayúsculas -> prefijo -> contiene."""
    atletas = list(db.atletas.find({"$or": [{"nombre_completo": nombre}, {"nombre_usado": nombre}]}))
    if atletas:
        return atletas
    n = sin_acentos(nombre)
    atletas = list(db.atletas.find({"nombre_busqueda": n}))
    if atletas:
        return atletas
    atletas = list(db.atletas.find({"nombre_busqueda": {"$regex": "^" + re.escape(n)}}).limit(200))
    if atletas:
        return atletas
    patron = {"$regex": re.escape(nombre), "$options": "i"}
    return list(db.atletas.find({"$or": [{"nombre_completo": patron}, {"nombre_usado": patron}]}).limit(200))


def participa_filtro(p, deporte, pais, anio, medalla):
    if deporte and deporte.casefold() not in (p.get("deporte") or "").casefold():
        return False
    if pais and (p.get("pais_representado_id") or "").upper() != pais.upper():
        return False
    if anio and p["edicion"]["anio"] != anio:
        return False
    if medalla and p.get("medalla") != medalla:
        return False
    return True


def consulta_atleta(nombre, deporte=None, pais=None, anio=None, medalla=None, como_json=False):
    medalla = normaliza_medalla(medalla)
    t0 = time.time()
    atletas = buscar_atletas_por_nombre(nombre)
    resultados = []
    for a in atletas:
        parts = [p for p in a.get("participaciones", []) if participa_filtro(p, deporte, pais, anio, medalla)]
        if (deporte or pais or anio or medalla) and not parts:
            continue
        medallas = {m: sum(1 for p in parts if p.get("medalla") == m) for m in MEDALLAS}
        resultados.append({
            "id": a["_id"],
            "nombre_completo": a["nombre_completo"],
            "nombre_usado": a.get("nombre_usado"),
            "sexo": a.get("sexo"),
            "pais_origen": a.get("pais_origen_id"),
            "nacimiento": a.get("fecha_nacimiento"),
            "lugar_nacimiento": a.get("lugar_nacimiento"),
            "fallecimiento": a.get("fecha_fallecimiento"),
            "lugar_fallecimiento": a.get("lugar_fallecimiento"),
            "estatura_cm": a.get("estatura_cm"),
            "peso_kg": a.get("peso_kg"),
            "clubes": [c["nombre_club"] for c in a.get("clubes", [])],
            "participaciones": parts,
            "medallas": medallas,
        })
    resultados.sort(key=lambda r: (-sum(r["medallas"].values()), -len(r["participaciones"])))
    total_encontrados = len(resultados)
    resultados = resultados[:MAX_ATLETAS]
    ms = (time.time() - t0) * 1000

    if como_json:
        print(json.dumps({"consulta": nombre, "total": total_encontrados, "atletas": resultados},
                         ensure_ascii=False, indent=2, default=str))
        return

    filtros = {k: v for k, v in dict(deporte=deporte, pais=pais, anio=anio, medalla=medalla).items() if v}
    encabezado(f"BÚSQUEDA DE ATLETA: '{nombre}'" + (f" | filtros: {filtros}" if filtros else ""))
    if not resultados:
        print("No se encontraron atletas con esos criterios.")
        return
    for r in resultados:
        print("\n" + "=" * 78)
        print(f"{r['nombre_completo']}  (ID {r['id']})")
        print("=" * 78)
        print(f"Nombre usado : {r['nombre_usado'] or 'N/A'}")
        print(f"Sexo         : {r['sexo'] or 'N/A'}   País de origen: {r['pais_origen'] or 'N/A'}")
        print(f"Nacimiento   : {r['nacimiento'] or 'N/A'} en {r['lugar_nacimiento'] or 'N/A'}")
        if r["fallecimiento"] or r["lugar_fallecimiento"]:
            print(f"Fallecimiento: {r['fallecimiento'] or 'N/A'} en {r['lugar_fallecimiento'] or 'N/A'}")
        print(f"Estatura     : {r['estatura_cm'] or 'N/A'} cm   Peso: {r['peso_kg'] or 'N/A'} kg")
        if r["clubes"]:
            print(f"Clubes       : {', '.join(r['clubes'][:5])}" + (" ..." if len(r["clubes"]) > 5 else ""))
        anios = sorted({p["edicion"]["anio"] for p in r["participaciones"]})
        print(f"Participó en : {len(r['participaciones'])} eventos, ediciones {anios}")
        print("\nParticipaciones y resultados:")
        for p in r["participaciones"]:
            ed = p["edicion"]
            res = f"Medalla {p['medalla']}" if p.get("medalla") else "Sin medalla"
            if p.get("posicion"):
                res += f" (posición {p['posicion']})"
            eq = f" [equipo: {p['equipo']['nombre_equipo']}]" if p.get("equipo") else ""
            print(f"  {ed['anio']} {ed['temporada']:<8} {p.get('pais_representado_id') or '---':<4} "
                  f"{p['deporte']}: {p['evento']} -> {res}{eq}")
        m = r["medallas"]
        print(f"\nMEDALLAS: Oro {m['Oro']} | Plata {m['Plata']} | Bronce {m['Bronce']} | Total {sum(m.values())}")
    if total_encontrados > MAX_ATLETAS:
        print(f"\n(Se muestran {MAX_ATLETAS} de {total_encontrados} coincidencias; afina el nombre o usa filtros)")
    print(f"\nConsulta resuelta en {ms:.0f} ms")


# ===================================================================== PAÍS
def buscar_pais(texto):
    pais = db.paises.find_one({"_id": texto.upper()})
    if pais:
        return [pais]
    n = sin_acentos(texto)
    exactos = list(db.paises.find({"nombre_busqueda": n}))
    if exactos:
        return exactos
    return list(db.paises.find({"nombre_busqueda": {"$regex": re.escape(n)}}).limit(10))


def consulta_pais(texto, anio=None, deporte=None, medalla=None, detalle=False, como_json=False):
    medalla = normaliza_medalla(medalla)
    t0 = time.time()
    candidatos = buscar_pais(texto)
    if not candidatos:
        print("País no encontrado.")
        return
    if len(candidatos) > 1:
        print(f"Varios países coinciden con '{texto}'; use el código:")
        for c in candidatos:
            print(f"  {c['_id']}  {c['nombre_pais']}")
        return
    pais = candidatos[0]
    pid = pais["_id"]

    sedes = list(db.ediciones.find({"pais_sede_id": pid}, {"anio": 1, "temporada": 1, "ciudad": 1, "nombre_edicion": 1})
                 .sort("anio", 1))

    cond = {"pais_representado_id": pid}
    if anio:
        cond["edicion.anio"] = anio
    if deporte:
        cond["deporte"] = {"$regex": re.escape(deporte), "$options": "i"}
    match_unwind = {f"participaciones.{k}": v for k, v in cond.items()}
    inicio = [
        {"$match": {"participaciones": {"$elemMatch": cond}}},
        {"$unwind": "$participaciones"},
        {"$match": match_unwind},
    ]

    # (1) participaciones por edición
    por_edicion = {}
    for r in db.atletas.aggregate(inicio + [
        {"$group": {
            "_id": {"anio": "$participaciones.edicion.anio", "temp": "$participaciones.edicion.temporada"},
            "atletas": {"$addToSet": "$_id"},
            "participaciones": {"$sum": 1},
            "deportes": {"$addToSet": "$participaciones.deporte"},
        }},
    ]):
        por_edicion[(r["_id"]["anio"], r["_id"]["temp"])] = {
            "atletas": len(r["atletas"]), "participaciones": r["participaciones"], "deportes": len(r["deportes"]),
            "Oro": 0, "Plata": 0, "Bronce": 0,
        }

    # (2) medallas: un evento por equipo cuenta una sola medalla (no una por integrante)
    filtro_medalla = {"participaciones.medalla": medalla} if medalla else {"participaciones.medalla": {"$in": list(MEDALLAS)}}
    medallistas = list(db.atletas.aggregate(inicio + [
        {"$match": filtro_medalla},
        {"$group": {
            "_id": {
                "anio": "$participaciones.edicion.anio", "temp": "$participaciones.edicion.temporada",
                "medalla": "$participaciones.medalla",
                "equipo": "$participaciones.equipo.equipo_id",
                "indiv": {"$cond": [{"$ifNull": ["$participaciones.equipo", False]}, 0, "$participaciones.participacion_id"]},
            },
            "deporte": {"$first": "$participaciones.deporte"},
            "evento": {"$first": "$participaciones.evento"},
            "equipo": {"$first": "$participaciones.equipo.nombre_equipo"},
            "atletas": {"$push": "$nombre_completo"},
        }},
        {"$sort": {"_id.anio": 1, "deporte": 1, "evento": 1}},
    ]))
    for m in medallistas:
        k = (m["_id"]["anio"], m["_id"]["temp"])
        por_edicion.setdefault(k, {"atletas": 0, "participaciones": 0, "deportes": 0, "Oro": 0, "Plata": 0, "Bronce": 0})
        por_edicion[k][m["_id"]["medalla"]] += 1

    total = {"Oro": 0, "Plata": 0, "Bronce": 0, "participaciones": 0}
    for v in por_edicion.values():
        for k in total:
            total[k] += v[k]
    anios_part = sorted({k[0] for k in por_edicion})

    # población
    pob = pais.get("historico_poblacion", [])
    if anio and pob:
        cerca = min(pob, key=lambda x: abs(x["anio"] - anio))
    else:
        cerca = pob[-1] if pob else None
    ms = (time.time() - t0) * 1000

    if como_json:
        print(json.dumps({
            "pais": {"codigo": pid, "nombre": pais["nombre_pais"], "region": pais.get("region")},
            "poblacion_referencia": cerca,
            "sede_de_juegos": [{"anio": s["anio"], "temporada": s["temporada"], "ciudad": s.get("ciudad")} for s in sedes],
            "anios_de_participacion": anios_part,
            "por_edicion": [{"anio": k[0], "temporada": k[1], **v} for k, v in sorted(por_edicion.items())],
            "totales": total,
            "medallistas": [{"anio": m["_id"]["anio"], "medalla": m["_id"]["medalla"], "deporte": m["deporte"],
                             "evento": m["evento"], "equipo": m["equipo"], "atletas": m["atletas"]} for m in medallistas]
            if detalle else None,
        }, ensure_ascii=False, indent=2, default=str))
        return

    filtros = {k: v for k, v in dict(anio=anio, deporte=deporte, medalla=medalla).items() if v}
    encabezado(f"BÚSQUEDA DE PAÍS: '{texto}'" + (f" | filtros: {filtros}" if filtros else ""))
    print("=" * 78)
    print(f"{pais['nombre_pais']}  (código {pid})   Región: {pais.get('region') or 'N/A'}")
    print("=" * 78)
    if cerca:
        print(f"Población ({cerca['anio']}): {cerca['poblacion']:,}   [registros históricos: {len(pob)}]")
    if sedes:
        print("Sede de los Juegos Olímpicos:")
        for s in sedes:
            print(f"  - {s['anio']} {s['temporada']}: {s.get('ciudad') or 'ciudad N/D'} ({s['nombre_edicion']})")
    else:
        print("Sede de los Juegos Olímpicos: nunca ha sido sede")
    if not por_edicion:
        print("\nSin participaciones con esos criterios.")
        return
    print(f"\nAños de participación ({len(anios_part)}): {', '.join(map(str, anios_part))}")
    print("\nHistorial por edición:")
    print(f"  {'Año':<5} {'Temporada':<9} {'Atletas':>8} {'Partic.':>8} {'Deportes':>8} {'Oro':>5} {'Plata':>6} {'Bronce':>7}")
    for (a, t), v in sorted(por_edicion.items()):
        print(f"  {a:<5} {t:<9} {v['atletas']:>8} {v['participaciones']:>8} {v['deportes']:>8} "
              f"{v['Oro']:>5} {v['Plata']:>6} {v['Bronce']:>7}")
    print(f"\nTOTAL: {total['participaciones']} participaciones | Oro {total['Oro']} | Plata {total['Plata']} "
          f"| Bronce {total['Bronce']} | Medallas {total['Oro'] + total['Plata'] + total['Bronce']}")
    print("(las medallas de equipo se cuentan una vez por evento, no una por integrante)")

    if detalle:
        print("\nResultados (medallas obtenidas):")
        for m in medallistas:
            quien = m["equipo"] and f"equipo {m['equipo']} ({len(m['atletas'])} integrantes)" or ", ".join(m["atletas"])
            print(f"  {m['_id']['anio']} {m['_id']['medalla']:<6} {m['deporte']}: {m['evento']} -> {quien}")
    print(f"\nConsulta resuelta en {ms:.0f} ms")


# ======================================================================= CLI
def main():
    ap = argparse.ArgumentParser(description="Consultas de atletas y países (MongoDB, Juegos Olímpicos)")
    sub = ap.add_subparsers(dest="tipo", required=True)

    a = sub.add_parser("atleta", help="Información de un atleta por nombre")
    a.add_argument("nombre", help="Nombre del atleta (obligatorio)")
    a.add_argument("--deporte", help="Filtrar por deporte (ej. Athletics)")
    a.add_argument("--pais", help="Filtrar por país representado (código, ej. JAM)")
    a.add_argument("--anio", type=int, help="Filtrar por año de la edición")
    a.add_argument("--medalla", help="Filtrar por medalla (Oro, Plata, Bronce)")
    a.add_argument("--json", action="store_true", help="Salida en JSON")

    p = sub.add_parser("pais", help="Información de un país por nombre o código")
    p.add_argument("pais", help="Nombre o código del país (obligatorio)")
    p.add_argument("--anio", type=int, help="Filtrar por año de la edición")
    p.add_argument("--deporte", help="Filtrar por deporte")
    p.add_argument("--medalla", help="Filtrar medallas (Oro, Plata, Bronce)")
    p.add_argument("--detalle", action="store_true", help="Lista cada medalla obtenida")
    p.add_argument("--json", action="store_true", help="Salida en JSON")

    args = ap.parse_args()
    if args.tipo == "atleta":
        consulta_atleta(args.nombre, args.deporte, args.pais, args.anio, args.medalla, args.json)
    else:
        consulta_pais(args.pais, args.anio, args.deporte, args.medalla, args.detalle, args.json)


if __name__ == "__main__":
    main()
