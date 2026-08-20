SELECT p.id, p.nombre, a.registros_relacionados_desagrupados as Registros_relacionados_desagregados,c.comision, c.fecha_efectiva
FROM {zona_proceso}.ultima_ingestion_agrupados AS a
JOIN {zona_proceso}.ultima_ingestion_personas_con_dia_habil_calculado AS p ON a.id = p.id
JOIN {zona_proceso}.ultima_ingestion_comisiones AS c ON p.proximo_dia_habil = c.fecha_efectiva AND p.id = c.id