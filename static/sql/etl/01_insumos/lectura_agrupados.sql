CREATE TABLE {zona_proceso}.ultima_ingestion_agrupados AS
SELECT 
    id,
    registros_relacionados,
    TRIM(registro_desagrupado) AS registros_relacionados_desagrupados
FROM {zona_resultados}.srm_registros_agrupados_sya,
LATERAL unnest(string_to_array(registros_relacionados, ',')) AS registro_desagrupado;