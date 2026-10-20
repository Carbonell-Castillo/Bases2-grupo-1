# Guía de Ejecución Paso a Paso - Fase 3

Esta guía detalla cómo ejecutar la migración completa desde la Fase 1 hacia MongoDB, cómo gestionar el contenedor y cómo realizar las consultas mediante Python.

## Requisitos Previos
1. **Docker y Docker Compose** instalados y en ejecución.
2. **Python 3.8+** instalado.
3. Librerías de Python instaladas (para ello usaremos un entorno virtual):
    ```bash
    python -m venv venv
    .\venv\Scripts\activate
    python -m pip install pymongo pandas
    python -m pip freeze > requirements.txt
    ```

> Nota: Para salir del entorno virtual se usa el comando `deactivate`.

## Paso 1: Ejecutar la Orquestación y Exportación

Vamos a abrir una terminal de **Git bash** en la carpeta `fase3` con el entorno virtual activado para poder ejecutar el script principal que desencadena todo el proceso,:

```bash
bash src/exportar_fase1.sh
```

**¿Qué hace este script internamente?**

1. Llama al `run_load.sh` de la Fase 1, el cual levanta PostgreSQL, carga los datos crudos y ejecuta `derivar_equipos.sql`.
2. Extrae las 10 tablas resultantes en formato CSV y las guarda en `fase3/src/output_postgres/`.
3. Levanta el contenedor de MongoDB (`proyecto_fase3`) en segundo plano con `-d`.
4. Ejecuta `script_de_carga.py`, el cual lee los CSV exportados y los inserta en las 3 colecciones de MongoDB.
5. Abre automáticamente la consola interactiva de MongoDB.

## Paso 2: Gestión del Contenedor y la Terminal

Como el contenedor se ejecuta en segundo plano, se puede gestionar la terminal de la siguiente manera:

* **Abrir la terminal de MongoDB sin reiniciar el contenedor:**
Si se cerró la terminal de `mongosh` y se necesita volver a entrar, ejecutamos:
```bash
docker exec -it proyecto_fase3 mongosh olimpiadas_fase3
```

* **Cerrar la terminal sin apagar el contenedor:**
Dentro de `mongosh`, simplemente se escribe `exit` y se presiona Enter, o se usa la combinación de teclas `Ctrl + C` dos veces. El contenedor seguirá funcionando en segundo plano.

* **Detener el contenedor:**
Si ya terminamos de trabajar y se desea detener la base de datos:
```bash
docker compose stop
```

* **Volver a levantar el contenedor:**
Para iniciarlo nuevamente (los datos se perderán porque no usamos volúmenes, ejecutamos nuevamente script_de_carga.py para solucionarlo):
```bash
docker compose up -d
# para volver a cargar los CSVs
py src/script_de_carga.py
```

## Paso 3: Ejecutar el Script de Consultas

Como solución a loas incisos c y d del enunciado, se desarrolló un script en `script_de_consultas.py`, que permite consultar atletas y países con filtros opcionales.

**Para consultar un Atleta (Búsqueda obligatoria por nombre):**

```bash
python src/script_de_consultas.py atleta "Usain St. Leo Bolt"
```

*Con filtro opcional por deporte:*

```bash
python src/script_de_consultas.py atleta "Usain St. Leo Bolt" "Athletics"
```

**Para consultar un País (Búsqueda obligatoria por código o nombre):**

```bash
python src/script_de_consultas.py pais "JAM"
```

```bash
python src/script_de_consultas.py pais "Jamaica"
```

---
