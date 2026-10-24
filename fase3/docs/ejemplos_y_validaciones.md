# Ejemplos de Consultas y Validación en MongoDB (Python/PyMongo)

Estas consultas se ejecutan utilizando Python y la librería `pymongo`. Asegurese de tener el entorno virtual activado. Para probarlas, se puede crear un archivo temporal o ejecutarse en una consola de Python.

Todas las consultas asumen la siguiente configuración inicial:
```python
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["olimpiadas_fase3"]
```



## 1. Consultas sobre Equipos (Embebidos)

**Lógica y Justificación:** En SQL teníamos una tabla `equipo`. En Mongo, el equipo se integró como un subdocumento dentro del arreglo `participaciones` de cada atleta. Usamos el *Aggregation Pipeline* para "desenrollar" (`$unwind`) las participaciones y agruparlas.

**Verificar equipos creados con más atletas enlazados:**

```python
pipeline = [
    {"$unwind": "$participaciones"},
    {"$match": {"participaciones.equipo": {"$ne": None}}},
    {"$group": {
        "_id": "$participaciones.equipo.equipo_id",
        "nombre_equipo": {"$first": "$participaciones.equipo.nombre_equipo"},
        "deporte": {"$first": "$participaciones.deporte"},
        "evento": {"$first": "$participaciones.evento"},
        "anio": {"$first": "$participaciones.edicion.anio"},
        "atletas_enlazados": {"$sum": 1}
    }},
    {"$sort": {"atletas_enlazados": -1}},
    {"$limit": 10}
]
resultados = list(db.atletas.aggregate(pipeline))
for r in resultados: print(r)
```

**Filtrar los equipos de relevos de Jamaica (Caso Usain Bolt):**

```python
pipeline = [
    {"$unwind": "$participaciones"},
    {"$match": {
        "participaciones.equipo": {"$ne": None},
        "participaciones.pais_representado_id": "JAM",
        "participaciones.evento": {"$regex": "Relay", "$options": "i"}
    }},
    {"$group": {
        "_id": "$participaciones.equipo.equipo_id",
        "nombre_equipo": {"$first": "$participaciones.equipo.nombre_equipo"},
        "evento": {"$first": "$participaciones.evento"},
        "anio": {"$first": "$participaciones.edicion.anio"},
        "atletas": {"$sum": 1}
    }},
    {"$sort": {"anio": 1, "evento": 1}}
]
resultados = list(db.atletas.aggregate(pipeline))
for r in resultados: print(r)
```

## 2. Verificar Integridad de Relaciones

**Lógica y Justificación:** Como los datos se anidaron con un script en Python directamente desde la base de datos validada en Postgres, el concepto de "llaves foráneas huérfanas" se elimina. En Mongo comprobamos la proporción de registros individuales vs en equipo basándonos en la existencia del campo.

```python
# Contar atletas con al menos una participación en equipo
con_equipo = db.atletas.count_documents({"participaciones.equipo": {"$ne": None}})
print(f"Atletas con equipo: {con_equipo}")

# Contar atletas sin ninguna participación de equipo
sin_equipo = db.atletas.count_documents({
    "participaciones": {"$not": {"$elemMatch": {"equipo": {"$ne": None}}}}
})
print(f"Atletas sin equipo: {sin_equipo}")
```

**Países no nulos y sin referencias huérfanas:**

```python
pipeline = [
    {"$unwind": "$participaciones"},
    {"$match": {"participaciones.pais_representado_id": None}},
    {"$count": "total"}
]
print(list(db.atletas.aggregate(pipeline)))  # []: no hay participaciones sin país
```

## 3. Emulación de `sp_info_atleta`

**Lógica y Justificación:** Al embeber toda la historia del atleta en su propio documento, el equivalente a ejecutar un *Stored Procedure* masivo con 5 JOINs se reduce a un simple `find_one`.

```python
# Búsqueda general de atleta (equivalente a CALL sp_info_atleta('Usain St. Leo Bolt'))
atleta = db.atletas.find_one(
    {"nombre_completo": {"$regex": "Usain St. Leo Bolt", "$options": "i"}},
    {"nombre_completo": 1, "pais_origen_id": 1, "participaciones": 1}
)
print(atleta)

# Búsqueda de atleta aplicando filtros de deporte y año
pipeline = [
    {"$match": {"nombre_completo": {"$regex": "Usain St. Leo Bolt", "$options": "i"}}},
    {"$project": {
        "nombre_completo": 1,
        "participaciones_filtradas": {
            "$filter": {
                "input": "$participaciones",
                "as": "part",
                "cond": {
                    "$and": [
                        {"$eq": ["$$part.deporte", "Athletics"]},
                        {"$eq": ["$$part.edicion.anio", 2012]}
                    ]
                }
            }
        }
    }}
]
resultados = list(db.atletas.aggregate(pipeline))
for r in resultados: print(r)
```

## 4. Emulación de `sp_info_pais`

**Lógica y Justificación:** Consultar la información del país base es un simple `find_one` en la colección `paises`. Para el historial, usamos la colección `atletas`.

```python
# Información demográfica del país
pais = db.paises.find_one({"_id": "JAM"})
print(pais)

# Historial de medallas ganadas por el país
pipeline = [
    {"$unwind": "$participaciones"},
    {"$match": {
        "participaciones.pais_representado_id": "JAM",
        "participaciones.medalla": {"$ne": None}
    }},
    {"$group": {
        "_id": "$participaciones.medalla",
        "total": {"$sum": 1}
    }}
]
resultados = list(db.atletas.aggregate(pipeline))
for r in resultados: print(r)
```

## 5. Consultas Rápidas de Resumen (Analytics)

### 5.1. Registros de medallistas generales

Esta consulta cuenta registros por atleta. En pruebas de equipo no equivale al número de medallas del país. Para el conteo correcto por país/equipo use `script_de_consultas.py pais CODIGO`, que agrupa por `equipo_id`.

```python
pipeline = [
    {"$unwind": "$participaciones"},
    {"$match": {"participaciones.medalla": {"$ne": None}}},
    {"$group": {"_id": "$participaciones.medalla", "total": {"$sum": 1}}},
    {"$sort": {"total": -1}}
]
resultados = list(db.atletas.aggregate(pipeline))
for r in resultados: print(r)
```

### 5.2. Países con más registros de medallistas

```python
pipeline = [
    {"$unwind": "$participaciones"},
    {"$match": {"participaciones.medalla": {"$ne": None}}},
    {"$group": {
        "_id": "$participaciones.pais_representado_id",
        "total_medallas": {"$sum": 1}
    }},
    {"$sort": {"total_medallas": -1}},
    {"$limit": 10}
]
resultados = list(db.atletas.aggregate(pipeline))
for r in resultados: print(r)
```

### 5.3. Atletas Históricos con más Medallas

```python
pipeline = [
    {"$unwind": "$participaciones"},
    {"$match": {"participaciones.medalla": {"$ne": None}}},
    {"$group": {
        "_id": "$nombre_completo",
        "oros": {"$sum": {"$cond": [{"$eq": ["$participaciones.medalla", "Oro"]}, 1, 0]}},
        "platas": {"$sum": {"$cond": [{"$eq": ["$participaciones.medalla", "Plata"]}, 1, 0]}},
        "bronces": {"$sum": {"$cond": [{"$eq": ["$participaciones.medalla", "Bronce"]}, 1, 0]}},
        "total_medallas": {"$sum": 1}
    }},
    {"$sort": {"total_medallas": -1}},
    {"$limit": 10}
]
resultados = list(db.atletas.aggregate(pipeline))
for r in resultados: print(r)
```

### 5.4. Países Sede Históricos

```python
sedes = db.ediciones.find(
    {"pais_sede_id": {"$ne": None}},
    {"anio": 1, "nombre_edicion": 1, "ciudad": 1, "pais_sede_id": 1, "_id": 0}
).sort("anio", 1)

for sede in sedes: print(sede)
```

---
## 6. Validaciones de la carga (resultados de la corrida final)

| Validación | Esperado | Resultado |
|---|---|---|
| `paises` | 234 (tabla `pais`) | 234 |
| `ediciones` | 64 (tabla `edicion`) | 64 |
| `atletas` | ETL corregido | 244,540 |
| Participaciones CSV → únicas | 693,398 → 534,950 | 158,448 duplicados entre fuentes unificados |
| País representado nulo | 0 | 0 |
| Referencias de país huérfanas | 0 | 0 |
| Identidad reutilizada | Hala Fattouh separada de Mansour Al-Soraihi | documento propio con participación `LIB` |
| Usain Bolt | 8 oros | 8 oros (100 m y 200 m en 2008, 2012, 2016 + relevos 2012 y 2016) |
| Michael Phelps | 23 oros | 23 oros, 3 platas, 2 bronces |
| Simone Biles (2016) | 4 oros, 1 bronce | 4 oros, 1 bronce |
| Sedes de USA | 8 | 8 (1904, 1932 V/I, 1960, 1980, 1984, 1996, 2002) |

La corrida final, iniciada desde `docker compose down`, se ejecutó el **2026-10-23 21:54:47–21:57:05 (UTC-6)**. La verificación ejecutó 26 pruebas: **26 correctas, 0 fallidas**. Evidencia: `fase3/logs/ejecucion_pipeline_completa.log` y `fase3/logs/verificacion_fase3.log`.

Para repetirlas desde la raíz:

```powershell
python fase3\src\verificar_fase3.py
```

```python
# Verificar que ningún atleta tenga dos participaciones con el mismo evento y edición
pipeline = [
    {"$unwind": "$participaciones"},
    {"$group": {"_id": {"a": "$_id", "e": "$participaciones.edicion.edicion_id", "ev": "$participaciones.evento"}, "n": {"$sum": 1}}},
    {"$match": {"n": {"$gt": 1}}},
    {"$limit": 5}
]
print(list(db.atletas.aggregate(pipeline, allowDiskUse=True)))   # []
```
