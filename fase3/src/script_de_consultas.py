import re
import sys

from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["olimpiadas_fase3"]


def buscar_atleta(nombre, filtro_deporte=None):
    print(f"\n--- BÚSQUEDA DE ATLETA: {nombre} ---")

    query = {
        "$or": [
            {"nombre_completo": nombre},
            {"nombre_usado": nombre},
        ]
    }
    atletas = list(db.atletas.find(query))

    if not atletas:
        nombre_regex = re.escape(nombre)
        query = {
            "$or": [
                {"nombre_completo": {"$regex": f"^{nombre_regex}$", "$options": "i"}},
                {"nombre_usado": {"$regex": f"^{nombre_regex}$", "$options": "i"}},
            ]
        }
        atletas = list(db.atletas.find(query))

    if not atletas:
        query = {
            "$or": [
                {"nombre_completo": {"$regex": nombre_regex, "$options": "i"}},
                {"nombre_usado": {"$regex": nombre_regex, "$options": "i"}},
            ]
        }
        atletas = list(db.atletas.find(query))

    if not atletas:
        print("No se encontraron atletas.")
        return

    for atl in atletas:
        print(f"\nID: {atl['_id']} | Nombre: {atl['nombre_completo']} ({atl.get('sexo', 'N/A')})")
        print(f"Nombre usado: {atl.get('nombre_usado') or 'N/A'}")
        print(f"País de Origen: {atl.get('pais_origen_id') or 'N/A'}")
        print(
            f"Nacimiento: {atl.get('fecha_nacimiento') or 'N/A'} "
            f"en {atl.get('lugar_nacimiento') or 'N/A'}"
        )
        print(
            f"Fallecimiento: {atl.get('fecha_fallecimiento') or 'N/A'} "
            f"en {atl.get('lugar_fallecimiento') or 'N/A'}"
        )
        print(f"Estatura: {atl.get('estatura_cm') or 'N/A'} cm | Peso: {atl.get('peso_kg') or 'N/A'} kg")
        print("Participaciones y Medallas:")

        medallas = {"Oro": 0, "Plata": 0, "Bronce": 0}
        participaciones_filtradas = atl.get("participaciones", [])

        if filtro_deporte:
            deporte_busqueda = filtro_deporte.casefold()
            participaciones_filtradas = [
                participacion
                for participacion in participaciones_filtradas
                if (participacion.get("deporte") or "").casefold() == deporte_busqueda
            ]

        for p in participaciones_filtradas:
            edicion = p.get("edicion", {})
            medalla = p.get("medalla")
            resultado = f"Medalla: {medalla}" if medalla else "Sin medalla"
            if medalla in medallas:
                medallas[medalla] += 1
            if p.get("posicion"):
                resultado += f" | Posición: {p['posicion']}"

            print(
                f"  - {edicion.get('anio', 'Año desconocido')} "
                f"{edicion.get('nombre_edicion', '')} | "
                f"{p.get('deporte', 'Deporte desconocido')}: "
                f"{p.get('evento', 'Evento desconocido')} -> {resultado}"
            )

        if not participaciones_filtradas:
            if filtro_deporte:
                print(f"  No hay participaciones en el deporte {filtro_deporte}.")
            else:
                print("  No hay participaciones registradas.")

        print(f"Resumen de Medallas: {medallas}")

def buscar_pais(codigo_o_nombre):
    print(f"\n--- BÚSQUEDA DE PAÍS: {codigo_o_nombre} ---")

    nombre_regex = re.escape(codigo_o_nombre)
    query = {
        "$or": [
            {"_id": codigo_o_nombre.upper()},
            {"nombre_pais": {"$regex": f"^{nombre_regex}$", "$options": "i"}},
        ]
    }
    pais = db.paises.find_one(query)

    if not pais:
        print("País no encontrado.")
        return

    print(f"\nPaís: {pais['nombre_pais']} (Código: {pais['_id']})")

    sedes = list(
        db.ediciones.find(
            {"pais_sede_id": pais["_id"]},
            {"_id": 0, "ciudad": 1, "anio": 1, "temporada": 1},
        ).sort("anio", 1)
    )
    if sedes:
        print("Ha sido sede de los Juegos Olímpicos en:")
        for sede in sedes:
            print(
                f"  - {sede.get('ciudad') or 'Ciudad desconocida'} "
                f"({sede.get('anio', 'Año desconocido')} - "
                f"{sede.get('temporada', 'Temporada desconocida')})"
            )
    else:
        print("Nunca ha sido sede de los Juegos Olímpicos.")

    pipeline = [
        {"$match": {"participaciones.pais_representado_id": pais["_id"]}},
        {"$unwind": "$participaciones"},
        {"$match": {"participaciones.pais_representado_id": pais["_id"]}},
        {"$group": {
            "_id": "$participaciones.edicion.anio",
            "total_atletas": {"$addToSet": "$_id"},
            "total_participaciones": {"$sum": 1},
            "medallas_oro": {"$sum": {"$cond": [{"$eq": ["$participaciones.medalla", "Oro"]}, 1, 0]}},
            "medallas_plata": {"$sum": {"$cond": [{"$eq": ["$participaciones.medalla", "Plata"]}, 1, 0]}},
            "medallas_bronce": {"$sum": {"$cond": [{"$eq": ["$participaciones.medalla", "Bronce"]}, 1, 0]}},
        }},
        {"$sort": {"_id": 1}}
    ]

    resultados = list(db.atletas.aggregate(pipeline))

    if not resultados:
        print("\nNo hay participaciones registradas para este país.")
        return

    print("\nHistorial de Participaciones y Medallas por Año:")
    total_participaciones = 0
    total_oro = total_plata = total_bronce = 0
    for res in resultados:
        oro = res["medallas_oro"]
        plata = res["medallas_plata"]
        bronce = res["medallas_bronce"]
        total_participaciones += res["total_participaciones"]
        total_oro += oro
        total_plata += plata
        total_bronce += bronce
        print(
            f"  {res['_id']}: {len(res['total_atletas'])} atletas | "
            f"{res['total_participaciones']} participaciones | "
            f"Medallas: Oro {oro}, Plata {plata}, Bronce {bronce}"
        )

    print(f"\nTOTAL DE PARTICIPACIONES: {total_participaciones}")
    print(f"TOTAL HISTÓRICO: Oro {total_oro}, Plata {total_plata}, Bronce {total_bronce}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso:")
        print("  python .\\src\\script_de_consultas.py atleta \"Nombre del Atleta\" [Filtro Deporte]")
        print("  python .\\src\\script_de_consultas.py pais \"Código/Nombre del país\"")
        sys.exit(1)

    tipo = sys.argv[1].lower()
    param = sys.argv[2]

    if tipo == "atleta":
        filtro = sys.argv[3] if len(sys.argv) > 3 else None
        buscar_atleta(param, filtro)
    elif tipo == "pais":
        buscar_pais(param)
    else:
        print("Tipo de consulta inválido. Use 'atleta' o 'pais'.")
        sys.exit(1)