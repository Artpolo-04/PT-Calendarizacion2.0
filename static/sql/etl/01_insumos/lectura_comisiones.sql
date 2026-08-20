CREATE TABLE {zona_proceso}.ultima_ingestion_comisiones AS
SELECT id, comision, fecha_efectiva
FROM {zona_resultados}.srm_comisiones_sya;