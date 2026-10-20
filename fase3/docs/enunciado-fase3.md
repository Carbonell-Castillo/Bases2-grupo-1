## PROYECTO FASE 3

### Descripción General
Se ha solicitado cargar la información relacionada con las olimpiadas trabajada en la Fase 1, la cual debe incluir toda la información de las fuentes de datos y las correcciones encontradas durante el proceso.

> **Nota:** El alcance definitivo de la data será establecido en clase y en las reuniones de seguimiento conforme al avance del proyecto.

---

### Entregables y Requerimientos

#### a) Carga de Datos en Base de Datos NoSQL
* Utilizar los datos procesados en la Fase 1 y cargarlos en una base de datos NoSQL (**MongoDB**).
* La información debe estar completa. Cualquier fallo previo en la carga hacia la base de datos relacional debe ser solucionado y corregido para esta fase.

#### b) Scripts y Documentación
* **Scripts de BD:** Entregar la totalidad de scripts utilizados para la creación de documentos, colecciones e índices en MongoDB.
* **Scripts de Carga:** Incluir los scripts de carga de datos junto con sus archivos fuente correspondientes.
* **Documentación:** Documentación detallada de la ejecución, especificando **fecha y hora** de cada proceso realizado.

#### c) Script de Atletas
Desarrollar un método o script enfocado en la consulta de información de atletas:
* **Parámetro principal (Obligatorio):** Nombre del atleta.
* **Información a desplegar:** Datos personales, participaciones, resultados obtenidos y medallas ganadas.
* **Formato de salida:** A criterio del estudiante.
* **Filtros opcionales:** Posibilidad de recibir parámetros adicionales para filtrar información específica (ej. deporte, país, año).

#### d) Script de Países
Desarrollar un método o script enfocado en la consulta de información por país:
* **Parámetro principal (Obligatorio):** Nombre o código del país.
* **Información a desplegar:** Participaciones generales, resumen e historial de medallas, resultados, años de participación y registro de si ha sido sede de los Juegos Olímpicos (indicando los años correspondientes).
* **Formato de salida:** A criterio del estudiante.
* **Filtros opcionales:** Posibilidad de agregar parámetros adicionales para filtrar la información.

---

### Consideraciones para la Evaluación

* **Fecha de entrega y calificación:** 24 de Octubre de 2026.
* **Pruebas en vivo:** Durante la calificación se solicitará realizar consultas en el momento.
* **Rendimiento:** Las consultas ejecutadas no deben demorar en retornar resultados (se recomienda un uso adecuado de índices y optimización en MongoDB).