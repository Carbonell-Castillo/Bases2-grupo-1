# Guía de Ejecución Paso a Paso - Fase 3

Esta guía detalla cómo ejecutar la migración completa desde la Fase 1 hacia MongoDB, cómo gestionar el contenedor y cómo realizar las consultas mediante Python.

## Requisitos Previos
1. **Docker y Docker Compose** instalados y en ejecución.
2. **Python 3.8+** instalado.
3. Librerías de Python instaladas (para ello usaremos un entorno virtual):
    ```bash
    python -m venv venv
    .\venv\Scripts\activate.bat
    pip install pymongo pandas
    pip freeze > requirements.txt
    ```

4. Estructura de carpetas: La carpeta `fase3` debe estar al mismo nivel que la carpeta `fase1` en tu sistema de archivos.

> Nota: Para salir del entorno virtual se usa el comando `deactivate`.

## Paso 1: Ejecutar la Orquestación y Exportación

Abre una terminal en la carpeta `fase3`, asegúrate de tener tu entorno virtual activado, y ejecuta el script principal que desencadenará todo el proceso:

```bash
bash exportar_fase1.sh
```

**¿Qué hace este script internamente?**

1. Llama al `run_load.sh` de la Fase 1, el cual levanta PostgreSQL, carga los datos crudos y ejecuta `derivar_equipos.sql`.
2. Extrae las 10 tablas resultantes en formato CSV y las guarda en la carpeta `./fase3/output_postgres/`.
3. Levanta el contenedor de MongoDB (`proyecto-fase3`) en segundo plano (`-d`).
4. Ejecuta `script_de_carga.py`, el cual lee los CSV exportados y los inserta en las 3 colecciones de MongoDB.
5. Abre automáticamente la consola interactiva de MongoDB.

## Paso 2: Gestión del Contenedor y la Terminal

Como el contenedor se ejecuta en segundo plano, puedes gestionar la terminal y su ciclo de vida de la siguiente manera:

* **Abrir la terminal de MongoDB sin reiniciar el contenedor:**
Si cerraste la terminal de `mongosh` y necesitas volver a entrar, ejecuta:
```bash
docker exec -it proyecto-fase3 mongosh olimpiadas_fase3
```

* **Cerrar la terminal sin apagar el contenedor:**
Dentro de `mongosh`, simplemente escribe `exit` y presiona Enter, o usa la combinación de teclas `Ctrl + C` dos veces. El contenedor seguirá funcionando en segundo plano.
* **Detener el contenedor:**
Si ya terminaste de trabajar y quieres detener la base de datos:
```bash
docker compose stop
```

* **Volver a levantar el contenedor:**
Para iniciarlo nuevamente (los datos se perderán si no usas volúmenes, requiriendo correr el script de carga de nuevo):
```bash
docker compose up -d
```

## Paso 3: Ejecutar el Script de Consultas

Se ha desarrollado un script en Python (`script_de_consultas.py`) que cumple con los requerimientos de la Fase 3, permitiendo consultar atletas y países con filtros opcionales.

**Para consultar un Atleta (Búsqueda obligatoria por nombre):**

```bash
python script_de_consultas.py atleta "Usain St. Leo Bolt"
```

*Con filtro opcional por deporte:*

```bash
python script_de_consultas.py atleta "Usain St. Leo Bolt" "Athletics"
```

**Para consultar un País (Búsqueda obligatoria por código o nombre):**

```bash
python script_de_consultas.py pais "JAM"
```

```bash
python script_de_consultas.py pais "Jamaica"
```

---
