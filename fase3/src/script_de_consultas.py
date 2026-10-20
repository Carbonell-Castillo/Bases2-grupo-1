import sys
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["olimpiadas_fase3"]

def buscar_atleta(nombre, filtro_deporte=None):
    """
    Script enfocado en la consulta de información de atletas.
    """
    print(f"\n--- BÚSQUEDA DE ATLETA: {nombre} ---")
    
    query = {"$text": {"$search": f'"{nombre}"'}}
    atletas = list(db.atletas.find(query))
    
    if not atletas:
        # Fallback a regex si el texto exacto no hace match perfecto
        query = {"nombre_completo": {"$regex": nombre, "$options": "i"}}
        atletas = list(db.atletas.find(query))
        
    if not atletas:
        print("No se encontraron atletas.")
        return

    for atl in atletas:
        print(f"\nID: {atl['_id']} | Nombre: {atl['nombre_completo']} ({atl.get('sexo', 'N/A')})")
        print(f"País de Origen: {atl.get('pais_origen_id')}")
        print("Participaciones y Medallas:")
        
        medallas = {"Oro": 0, "Plata": 0, "Bronce": 0}
        participaciones_filtradas = atl.get('participaciones', [])
        
        if filtro_deporte:
            participaciones_filtradas = [p for p in participaciones_filtradas if p['deporte'] == filtro_deporte]
            
        for p in participaciones_filtradas:
            medalla_str = f"🥇 {p['medalla']}" if p['medalla'] else "Sin medalla"
            if p['medalla'] in medallas: medallas[p['medalla']] += 1
            
            print(f"  - {p['anio']} {p['edicion']} | {p['deporte']}: {p['evento']} -> {medalla_str}")
            
        print(f"Resumen de Medallas: {medallas}")

def buscar_pais(codigo_o_nombre):
    """
    Script enfocado en la consulta de información por país.
    """
    print(f"\n--- BÚSQUEDA DE PAÍS: {codigo_o_nombre} ---")
    
    query = {"$or": [
        {"_id": codigo_o_nombre.upper()},
        {"nombre_pais": {"$regex": f"^{codigo_o_nombre}$", "$options": "i"}}
    ]}
    
    pais = db.paises.find_one(query)
    
    if not pais:
        print("País no encontrado.")
        return
        
    print(f"\nPaís: {pais['nombre_pais']} (Código: {pais['_id']})")
    
    if pais['sedes_olimpicas']:
        print("Ha sido sede de los Juegos Olímpicos en:")
        for sede in pais['sedes_olimpicas']:
            print(f"  - {sede['ciudad']} ({sede['anio']} - {sede['temporada']})")
    else:
        print("Nunca ha sido sede de los Juegos Olímpicos.")
        
    # Calcular resumen de participaciones usando Aggregation Framework en Atletas
    pipeline = [
        {"$match": {"participaciones.pais_representado": pais['_id']}},
        {"$unwind": "$participaciones"},
        {"$match": {"participaciones.pais_representado": pais['_id']}},
        {"$group": {
            "_id": "$participaciones.anio",
            "total_atletas": {"$addToSet": "$_id"},
            "medallas_oro": {"$sum": {"$cond": [{"$eq": ["$participaciones.medalla", "Oro"]}, 1, 0]}},
            "medallas_plata": {"$sum": {"$cond": [{"$eq": ["$participaciones.medalla", "Plata"]}, 1, 0]}},
            "medallas_bronce": {"$sum": {"$cond": [{"$eq": ["$participaciones.medalla", "Bronce"]}, 1, 0]}}
        }},
        {"$sort": {"_id": 1}}
    ]
    
    resultados = list(db.atletas.aggregate(pipeline))
    
    print("\nHistorial de Participaciones y Medallas por Año:")
    total_oro = total_plata = total_bronce = 0
    for res in resultados:
        if res['_id'] is None: continue
        o = res['medallas_oro']
        p = res['medallas_plata']
        b = res['medallas_bronce']
        total_oro += o; total_plata += p; total_bronce += b
        print(f"  {res['_id']}: {len(res['total_atletas'])} atletas enviados | Medallas: 🥇 {o} 🥈 {p} 🥉 {b}")
        
    print(f"\nTOTAL HISTÓRICO: 🥇 {total_oro}  🥈 {total_plata}  🥉 {total_bronce}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso:")
        print("  python mongo_consultas.py atleta \"Nombre del Atleta\" [Filtro Deporte]")
        print("  python mongo_consultas.py pais \"Codigo/Nombre Pais\"")
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