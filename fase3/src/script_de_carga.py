# Archivo: fase3/script_de_carga_mongodb.py
import csv
from pathlib import Path
from pymongo import MongoClient

# Rutas
BASE_DIR = Path(__file__).resolve().parent
CSV_DIR = BASE_DIR / "output_postgres"

# Conexión a MongoDB (asegúrate de tener el contenedor Mongo corriendo)
client = MongoClient("mongodb://localhost:27017/")
db = client["olimpiadas_fase3"]

def read_csv(filename):
    """Lee un CSV y devuelve una lista de diccionarios."""
    path = CSV_DIR / f"{filename}.csv"
    with open(path, encoding='utf-8') as f:
        return list(csv.DictReader(f))

def main():
    print("Iniciando migración a MongoDB...")
    
    # Limpiar colecciones si existen
    db.paises.drop()
    db.ediciones.drop()
    db.atletas.drop()

    # 1. Cargar Catálogos en memoria para anidar después
    print("Cargando catálogos en memoria...")
    deportes = {d['deporte_id']: d['nombre_deporte'] for d in read_csv('deporte')}
    ediciones_cat = {e['edicion_id']: e for e in read_csv('edicion')}
    eventos = {e['evento_id']: e for e in read_csv('evento')}
    equipos = {e['equipo_id']: e for e in read_csv('equipo')}
    clubes = {c['club_id']: c for c in read_csv('club')}
    
    atleta_club = {}
    for ac in read_csv('atleta_club'):
        atleta_club.setdefault(ac['atleta_id'], []).append(clubes[ac['club_id']])

    # 2. Construir y cargar la colección 'paises' (incluyendo población)
    print("Construyendo colección 'paises'...")
    paises_raw = read_csv('pais')
    poblacion_raw = read_csv('poblacion')
    
    poblacion_por_pais = {}
    for p in poblacion_raw:
        poblacion_por_pais.setdefault(p['pais_id'], []).append({
            "anio": int(p['anio']),
            "poblacion": int(p['poblacion'])
        })

    paises_docs = []
    for p in paises_raw:
        doc = {
            "_id": p['pais_id'],
            "nombre_pais": p['nombre_pais'],
            "region": p['region'] if p['region'] else None,
            "historico_poblacion": poblacion_por_pais.get(p['pais_id'], [])
        }
        paises_docs.append(doc)
    
    if paises_docs:
        db.paises.insert_many(paises_docs)

    # 3. Construir y cargar la colección 'ediciones'
    print("Construyendo colección 'ediciones'...")
    ediciones_docs = []
    for ed_id, ed in ediciones_cat.items():
        doc = {
            "_id": int(ed['edicion_id']),
            "nombre_edicion": ed['nombre_edicion'],
            "anio": int(ed['anio']),
            "temporada": ed['temporada'],
            "ciudad": ed['ciudad'] if ed['ciudad'] else None,
            "pais_sede_id": ed['pais_sede_id'] if ed['pais_sede_id'] else None
        }
        ediciones_docs.append(doc)
    
    if ediciones_docs:
        db.ediciones.insert_many(ediciones_docs)

    # 4. Construir y cargar la colección 'atletas' (con participaciones embebidas)
    print("Construyendo colección 'atletas' y embebiendo participaciones...")
    participaciones_raw = read_csv('participacion')
    
    parts_por_atleta = {}
    for p in participaciones_raw:
        evento = eventos[p['evento_id']]
        edicion = ediciones_cat[evento['edicion_id']]
        deporte = deportes[evento['deporte_id']]
        equipo = equipos.get(p['equipo_id']) if p['equipo_id'] else None
        
        part_doc = {
            "participacion_id": int(p['participacion_id']),
            "edicion": {
                "anio": int(edicion['anio']),
                "temporada": edicion['temporada'],
                "nombre_edicion": edicion['nombre_edicion']
            },
            "deporte": deporte,
            "evento": evento['nombre_evento'],
            "pais_representado_id": p['pais_representado_id'],
            "nombre_en_competencia": p['nombre_en_competencia'] if p['nombre_en_competencia'] else None,
            "posicion": p['posicion'] if p['posicion'] else None,
            "medalla": p['medalla'] if p['medalla'] else None,
            "equipo": {
                "equipo_id": int(equipo['equipo_id']),
                "nombre_equipo": equipo['nombre_equipo']
            } if equipo else None
        }
        parts_por_atleta.setdefault(p['atleta_id'], []).append(part_doc)

    atletas_raw = read_csv('atleta')
    atletas_docs = []
    for a in atletas_raw:
        doc = {
            "_id": int(a['atleta_id']),
            "nombre_completo": a['nombre_completo'],
            "nombre_usado": a['nombre_usado'] if a['nombre_usado'] else None,
            "sexo": a['sexo'] if a['sexo'] else None,
            "fecha_nacimiento": a['fecha_nacimiento'] if a['fecha_nacimiento'] else None,
            "lugar_nacimiento": a['lugar_nacimiento'] if a['lugar_nacimiento'] else None,
            "fecha_fallecimiento": a['fecha_fallecimiento'] if a['fecha_fallecimiento'] else None,
            "lugar_fallecimiento": a['lugar_fallecimiento'] if a['lugar_fallecimiento'] else None,
            "estatura_cm": int(a['estatura_cm']) if a['estatura_cm'] else None,
            "peso_kg": int(a['peso_kg']) if a['peso_kg'] else None,
            "pais_origen_id": a['pais_id'] if a['pais_id'] else None,
            "clubes": [{"club_id": int(c['club_id']), "nombre_club": c['nombre_club'], "pais_id": c['pais_id']} for c in atleta_club.get(a['atleta_id'], [])],
            "participaciones": parts_por_atleta.get(a['atleta_id'], [])
        }
        atletas_docs.append(doc)
    
    if atletas_docs:
        # Insertar en lotes (batches) es más rápido
        db.atletas.insert_many(atletas_docs)

    # 5. Crear Índices para búsquedas rápidas (Opcional pero recomendado para Fase 3)
    print("Creando índices...")
    db.atletas.create_index("nombre_completo")
    db.atletas.create_index("nombre_usado")
    db.paises.create_index("nombre_pais")

    print("¡Migración a MongoDB completada con éxito!")

if __name__ == "__main__":
    main()