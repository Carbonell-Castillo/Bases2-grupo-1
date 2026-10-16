# Análisis Comparativo de Estrategias de Respaldo

Datos reales tomados de `logs/backups.csv` y `logs/restores.csv` durante la
ejecución del **2026-10-16** sobre Postgres 17 en Docker Desktop (contenedor
`fase2-pg`, 1 CPU/volumen por defecto de Docker Desktop en Windows).

## 1. Tiempos de respaldo (segundos)

| Ronda | Full | Incremental 1 | Incremental 2 |
| --- | ---: | ---: | ---: |
| Por deportista (14 participaciones) | 42.02 | 39.10 | 42.91 |
| Por deporte (410 participaciones) | 38.65 | 35.34 | 37.39 |
| Por año (75,533 participaciones) | 42.95 | 35.67 | 39.77 |

![Gráfico de tiempos de respaldo](evidencia/grafico_tiempos_respaldo.png)

## 2. Tamaño de los respaldos en disco (MB)

| Ronda | Full | Incremental 1 | Incremental 2 |
| --- | ---: | ---: | ---: |
| Por deportista | 46.0 | 36.0 | 36.0 |
| Por deporte | 45.9 | 36.2 | 36.4 |
| Por año | 48.8 | 27.4 | 46.8 |

![Gráfico de tamaño de respaldo](evidencia/grafico_tamano_respaldo.png)

## 3. Tiempos de restauración (segundos)

| Ronda | Solo FULL | FULL + 2 incrementales (`pg_combinebackup`) | Diferencia |
| --- | ---: | ---: | ---: |
| Por deportista | 68.93 | 128.85 | +86.9% |
| Por deporte | 61.83 | 144.42 | +133.6% |
| Por año | 54.71 | 139.00 | +154.1% |

![Gráfico de tiempos de restauración](evidencia/grafico_tiempos_restauracion.png)

## 4. Hallazgos

**El tiempo de respaldo NO escala con el volumen de datos en este rango.**
Entre la ronda más chica (14 filas) y la más grande (75,533 filas) el tiempo
de `pg_basebackup` se mantiene entre 35-43 segundos en todos los casos. La
razón es que, a esta escala (decenas de MB), el costo fijo domina: esperar el
checkpoint (`-c fast`), el protocolo de replicación, y el streaming de WAL
(segmentos de 16 MB mínimo) pesan más que la diferencia real de datos. El
tamaño en disco sí refleja el ahorro esperado: los incrementales pesan
20-40% menos que el full porque solo copian bloques modificados — la
excepción es `por_anio/incr2_carga3` (46.8 MB), más grande por la propia
carga de ~31,643 filas nuevas (la más voluminosa de las 9 cargas).

**Restaurar con incrementales siempre fue más lento que restaurar solo el
full (87%-154% más tiempo), y la brecha crece con el tamaño del respaldo.**
`pg_combinebackup` tiene que leer el full completo más cada incremental de
la cadena y reconstruir un directorio de datos íntegro antes de poder
arrancar Postgres; restaurar solo el full es una simple copia de directorio.
Es la contraparte del punto anterior: lo que no se paga al respaldar
(tiempo) se paga al restaurar.

**Restaurar solo el full backup NUNCA recupera el estado más reciente.**
Se validó en las 3 rondas: tras restaurar únicamente el full, el `COUNT(*)`
de `participacion` coincide exactamente con lo cargado en la carga 1 (p. ej.
14,891 de 75,533 en la ronda por año) — los datos de las cargas 2 y 3 solo
aparecen al combinar el full con ambos incrementales (ver
[`evidencia.md`](evidencia.md), secciones 1.3-1.4, 2.2 y 3.2).

## 5. Conclusión y recomendación

- **Si la prioridad es *tiempo de recuperación* (RTO bajo)** y se puede
  tolerar perder los cambios posteriores al último full, el respaldo
  **completo** es la mejor opción: restaura más rápido porque es una copia
  directa de un directorio ya consistente.
- **Si la prioridad es *minimizar la pérdida de datos* (RPO bajo)** —
  recuperar hasta el último cambio posible — es necesario el esquema
  **completo + incremental**, aceptando un tiempo de restauración mayor
  (en estas pruebas, 1.9x a 2.5x más) porque hay que recombinar la cadena.
- **Recomendación para este volumen de datos (cientos de miles de filas):**
  mantener la estrategia híbrida clásica — un full periódico (p. ej.
  diario) + incrementales frecuentes entre cada full (p. ej. cada carga) —
  ya que el costo de tomar un incremental es prácticamente el mismo que un
  full (ambos dominados por el overhead fijo medido arriba) pero el
  incremental pesa menos en disco, y el riesgo de una restauración más
  lenta solo se asume en el escenario de recuperación total, que es
  infrecuente.
