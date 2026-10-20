# PROYECTO FASE 1

Se les ha solicitado cargar la información relacionada a las olimpiadas de las siguientes fuentes listadas:

1. [Olympics Dataset by KeithGalli](https://github.com/KeithGalli/Olympics-Dataset)
2. [120 years of olympic history athletes and results by heesoo37](https://www.kaggle.com/datasets/heesoo37/120-years-of-olympic-history-athletes-and-results/data?select=athlete_events.csv)
3. [Summer Olympics Medals (1896-2024) by stefanydeoliveira](https://www.kaggle.com/datasets/stefanydeoliveira/summer-olympics-medals-1896-2024)
4. [datasets olympics by datacamp](https://www.datacamp.com/datalab/datasets/r-olympics)

Y apoyarse en la revisión de calidad de los datos de [olympics official website](https://www.olympics.com/).

Deben crear un base de datos unificada utilizando las fuentes mencionadas para crear una base de datos más completa. Requerimientos adicionales sobre la data serán definidos en clase, en reuniones conforme el avance del proyecto.

Para esto deben entregar:

- Modelo de datos, diagrama entidad relación del modelo a usar para la carga de los datos. 2-SEP-26
- Extraer los datos de las fuentes listadas y cargar los mismos a una base de datos relacional de su elección utilizando su modelo propuesto.
- Entregar todos los scripts utilizados para la creación de su modelo en SQL, tablas, llaves, índices, incluyendo los scripts para carga de datos con sus archivos fuente.
- Realizar un stored procedure que reciba como primer parámetro el nombre del atleta y que despliegue toda la información relacionada con el mismo, participaciones, resultados, medallas, el formato de salida es a su criterio. Pueden agregar parámetros para mostrar o filtrar información específica, por ejemplo, deporte, país y año.
- Realizar un stored procedure que reciba de parámetro el país y que despliegue toda la información relacionada con el mismo, participaciones, información de medallas, resultados, año de participación, si ha sido sede en alguna ocasión y que años. El formato de salida es a su criterio. Pueden agregar parámetros para filtrar información específica.

**Nota:** el día de la calificación se les pedirá hacer consultas en el momento.
