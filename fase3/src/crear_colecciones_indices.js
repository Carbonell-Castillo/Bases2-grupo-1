// Script de BD: creación de colecciones, validadores e índices de MongoDB.
// Ejecución: docker exec -i proyecto_fase3 mongosh --quiet < crear_colecciones_indices.js
// Es idempotente: elimina y vuelve a crear las 3 colecciones del modelo.
// El script de carga (script_de_carga.py) inserta los documentos y vuelve a
// asegurar estos mismos índices con create_index (operación idempotente).

const dbo = db.getSiblingDB("olimpiadas_fase3");
print("[" + new Date().toISOString() + "] Creando colecciones e índices en olimpiadas_fase3");

["paises", "ediciones", "atletas"].forEach(c => dbo[c].drop());

// ---------------------------------------------------------------- paises
dbo.createCollection("paises", {
  validator: { $jsonSchema: {
    bsonType: "object",
    required: ["_id", "nombre_pais", "historico_poblacion"],
    properties: {
      _id: { bsonType: "string", description: "código NOC del país" },
      nombre_pais: { bsonType: "string" },
      region: { bsonType: ["string", "null"] },
      historico_poblacion: { bsonType: "array" }
    }
  } }
});
dbo.paises.createIndex({ nombre_pais: 1 }, { name: "nombre_pais_1" });
dbo.paises.createIndex({ nombre_busqueda: 1 }, { name: "nombre_busqueda_1" });

// ------------------------------------------------------------- ediciones
dbo.createCollection("ediciones", {
  validator: { $jsonSchema: {
    bsonType: "object",
    required: ["_id", "nombre_edicion", "anio", "temporada"],
    properties: {
      _id: { bsonType: "int" },
      anio: { bsonType: "int" },
      temporada: { enum: ["Verano", "Invierno"] },
      ciudad: { bsonType: ["string", "null"] },
      pais_sede_id: { bsonType: ["string", "null"] }
    }
  } }
});
dbo.ediciones.createIndex({ pais_sede_id: 1 }, { name: "pais_sede_id_1" });
dbo.ediciones.createIndex({ anio: 1, temporada: 1 }, { name: "anio_1_temporada_1" });

// --------------------------------------------------------------- atletas
dbo.createCollection("atletas", {
  validator: { $jsonSchema: {
    bsonType: "object",
    required: ["_id", "nombre_completo", "participaciones", "clubes"],
    properties: {
      _id: { bsonType: "int" },
      nombre_completo: { bsonType: "string" },
      participaciones: { bsonType: "array" },
      clubes: { bsonType: "array" }
    }
  } }
});
dbo.atletas.createIndex({ nombre_completo: 1 }, { name: "nombre_completo_1" });
dbo.atletas.createIndex({ nombre_usado: 1 }, { name: "nombre_usado_1" });
dbo.atletas.createIndex({ nombre_busqueda: 1 }, { name: "nombre_busqueda_1" });
dbo.atletas.createIndex({ pais_origen_id: 1 }, { name: "pais_origen_id_1" });
dbo.atletas.createIndex({ "participaciones.pais_representado_id": 1 }, { name: "part_pais_1" });
dbo.atletas.createIndex({ "participaciones.edicion.anio": 1 }, { name: "part_anio_1" });
dbo.atletas.createIndex({ "participaciones.deporte": 1 }, { name: "part_deporte_1" });
dbo.atletas.createIndex({ "participaciones.medalla": 1 }, { name: "part_medalla_1" });

["paises", "ediciones", "atletas"].forEach(c => {
  print("  " + c + ": " + dbo[c].getIndexes().map(i => i.name).join(", "));
});
print("[" + new Date().toISOString() + "] Colecciones e índices listos");
