-- Consultas de agregación del dashboard de contratación pública (PLACSP, almacén de septiembre de 2026).
-- Una consulta por visual; el nombre (Px.y) es el del wireframe de dashboard.md. DuckDB, sobre los Parquet que deja
-- build_modelo.py en dashboards/contratacion-publica/salida/. Las cifras de ejemplo (-- ej.) salen de ejecutar cada una el
-- 2026-10-09 contra ese almacén. Los filtros globales (feed, año, tipo, procedimiento, CCAA, división CPV) van como
-- WHERE opcionales; aquí se dejan los imprescindibles para que la cifra tenga sentido.
--
-- Convenciones: importe_repartido / importe_lote = importe sin IVA ya repartido entre adjudicatarios cuando el lote es
-- de acuerdo marco (importe_compartido), por lo que SIEMPRE se puede sumar. resultado 8/9 = adjudicado o formalizado.

CREATE OR REPLACE VIEW hecho_licitacion AS SELECT * FROM read_parquet('dashboards/contratacion-publica/salida/hecho_licitacion.parquet');
CREATE OR REPLACE VIEW hecho_lote AS SELECT * FROM read_parquet('dashboards/contratacion-publica/salida/hecho_lote.parquet');
CREATE OR REPLACE VIEW hecho_adjudicacion AS SELECT * FROM read_parquet('dashboards/contratacion-publica/salida/hecho_adjudicacion.parquet');
CREATE OR REPLACE VIEW dim_fecha AS SELECT * FROM read_parquet('dashboards/contratacion-publica/salida/dim_fecha.parquet');
CREATE OR REPLACE VIEW dim_organo AS SELECT * FROM read_parquet('dashboards/contratacion-publica/salida/dim_organo.parquet');
CREATE OR REPLACE VIEW dim_empresa AS SELECT * FROM read_parquet('dashboards/contratacion-publica/salida/dim_empresa.parquet');
CREATE OR REPLACE VIEW dim_cpv AS SELECT * FROM read_parquet('dashboards/contratacion-publica/salida/dim_cpv.parquet');
CREATE OR REPLACE VIEW dim_territorio AS SELECT * FROM read_parquet('dashboards/contratacion-publica/salida/dim_territorio.parquet');
CREATE OR REPLACE VIEW dim_tipo AS SELECT * FROM read_parquet('dashboards/contratacion-publica/salida/dim_tipo.parquet');
CREATE OR REPLACE VIEW dim_procedimiento AS SELECT * FROM read_parquet('dashboards/contratacion-publica/salida/dim_procedimiento.parquet');
CREATE OR REPLACE VIEW dim_estado AS SELECT * FROM read_parquet('dashboards/contratacion-publica/salida/dim_estado.parquet');
CREATE OR REPLACE VIEW dim_resultado AS SELECT * FROM read_parquet('dashboards/contratacion-publica/salida/dim_resultado.parquet');
CREATE OR REPLACE VIEW dim_feed AS SELECT * FROM read_parquet('dashboards/contratacion-publica/salida/dim_feed.parquet');

-- =====================================================================================================================
-- P0. Cabecera: tarjetas de contexto (recuentos y volumen del corte cargado)
-- =====================================================================================================================
-- P0.1 Tarjetas: licitaciones, lotes adjudicados, importe adjudicado repartido, por feed
SELECT f.etiqueta AS feed, count(DISTINCT l.id) AS licitaciones,
       sum(l.lotes_adjudicados) AS lotes_adjudicados,
       round(sum(l.importe_adjudicado) / 1e6, 1) AS importe_adjudicado_millones
FROM hecho_licitacion l JOIN dim_feed f USING (feed)
WHERE NOT l.importe_sospechoso
GROUP BY ALL ORDER BY licitaciones DESC;
-- ej. Contratos menores 46.553 licitaciones, 46.579 lotes adjudicados, 214,8 M€; Perfiles alojados 42.206 / 31.597 / 17.130,4 M€; Agregadas 17.101 / 15.996 / 12.080,5 M€ (sin los 20 importes sospechosos).

-- =====================================================================================================================
-- P1. Empresa licitadora
-- =====================================================================================================================
-- P1.1 Licitaciones abiertas (plazo no vencido, no anuladas) por división CPV y tipo, con presupuesto
SELECT c.division, t.etiqueta AS tipo, count(*) AS licitaciones, round(sum(l.presupuesto_sin_iva) / 1e6, 1) AS presupuesto_millones,
       median(l.presupuesto_sin_iva) AS presupuesto_mediano
FROM hecho_licitacion l JOIN dim_cpv c USING (cpv_key) JOIN dim_tipo t USING (tipo_key)
WHERE l.estado_key IN ('PUB', 'PRE') AND NOT l.anulada AND l.plazo_key >= DATE '2026-10-01' AND l.procedimiento_key <> '6'
GROUP BY ALL ORDER BY licitaciones DESC LIMIT 20;
-- ej. (hoy = 2026-10-01, fin del corte) Trabajos de construcción / Obras: 1.838 licitaciones, 3.519,4 M€, presupuesto mediano 168.144 €; Arquitectura e ingeniería / Servicios: 530.

-- P1.2 Calendario: licitaciones abiertas por semana en que vence el plazo (próximas 8 semanas)
SELECT date_trunc('week', l.plazo_key) AS semana_plazo, count(*) AS licitaciones, round(sum(l.presupuesto_sin_iva) / 1e6, 1) AS presupuesto_millones
FROM hecho_licitacion l
WHERE l.estado_key IN ('PUB', 'PRE') AND NOT l.anulada AND l.plazo_key BETWEEN DATE '2026-10-01' AND DATE '2026-10-01' + INTERVAL 8 WEEK
GROUP BY ALL ORDER BY 1;
-- ej. semana del 2026-10-05: 2.675 licitaciones por 2.503,1 M€; la del 2026-10-12: 2.229 por 1.251,1 M€.

-- P1.3 Competidores: distribución de ofertas por lote (histograma) para un procedimiento y división CPV
SELECT least(h.ofertas, 10) AS ofertas_tope_10, count(*) AS lotes, round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct
FROM hecho_lote h JOIN hecho_licitacion l USING (id) JOIN dim_cpv c ON c.cpv_key = l.cpv_key
WHERE h.adjudicado AND h.ofertas IS NOT NULL AND l.procedimiento_key IN ('1', '9') AND c.division_codigo = '45'
GROUP BY ALL ORDER BY 1;
-- ej. obras (CPV 45) en abierto o simplificado, 5.298 lotes: una oferta 31,9 %, dos 19,3 %, mediana 2 ofertas, 10 o más 8,3 %.

-- P1.4 Baja media adjudicada (importe adjudicado / presupuesto) por división CPV y tipo, solo expedientes de un lote con ratio fiable
SELECT c.division, t.etiqueta AS tipo, count(*) AS expedientes,
       round(100 * (1 - avg(l.ratio_adjudicado_presupuesto)), 1) AS baja_media_pct,
       round(100 * (1 - median(l.ratio_adjudicado_presupuesto)), 1) AS baja_mediana_pct
FROM hecho_licitacion l JOIN dim_cpv c USING (cpv_key) JOIN dim_tipo t USING (tipo_key)
WHERE l.ratio_fiable AND l.procedimiento_key <> '6'
GROUP BY ALL HAVING count(*) >= 50 ORDER BY expedientes DESC LIMIT 20;
-- ej. Trabajos de construcción / Obras: 4.992 expedientes, baja media 8,7 %, mediana 5,5 %; Arquitectura e ingeniería: 16,8 % / 15,4 %; Equipos médicos: 4,7 % / 0,0 %.

-- P1.5 Ficha de competidor: con qué órganos contrata una empresa (importe repartido, lotes, ofertas medias)
SELECT o.organo, count(*) AS adjudicaciones, round(sum(a.importe_repartido) / 1e3, 1) AS importe_miles,
       round(avg(a.ofertas), 1) AS ofertas_media, min(a.fecha_adjudicacion_key) AS primera, max(a.fecha_adjudicacion_key) AS ultima
FROM hecho_adjudicacion a JOIN dim_organo o USING (organo_key)
WHERE a.empresa_key = (SELECT empresa_key FROM dim_empresa WHERE NOT persona_fisica AND NOT sin_nif ORDER BY adjudicaciones DESC LIMIT 1)
  AND a.resultado_key IN ('8', '9') AND NOT a.importe_sospechoso
GROUP BY ALL ORDER BY importe_miles DESC LIMIT 15;
-- ej. la empresa con más adjudicaciones del corte: Servicio Andaluz de Salud 131 adjudicaciones y 22,5 M€ con 2,8 ofertas de media; Osakidetza 18 y 3,7 M€. Se parametriza por empresa_key.

-- =====================================================================================================================
-- P2. Periodista
-- =====================================================================================================================
-- P2.1 Quién se lleva más dinero: top adjudicatarios por importe repartido (sin personas físicas ni desiertos)
SELECT e.nombre, e.empresa_key AS nif, e.formato_identificador, count(*) AS adjudicaciones, count(DISTINCT a.organo_key) AS organos,
       round(sum(a.importe_repartido) / 1e6, 1) AS importe_millones,
       round(100.0 * count(*) FILTER (WHERE a.ofertas = 1) / count(*), 1) AS pct_una_oferta
FROM hecho_adjudicacion a JOIN dim_empresa e USING (empresa_key)
WHERE a.resultado_key IN ('8', '9') AND NOT e.persona_fisica AND NOT e.sin_nif AND NOT a.importe_sospechoso
GROUP BY ALL ORDER BY importe_millones DESC LIMIT 20;
-- ej. AGRUPACIÓN BIOBIDE 2026 538,8 M€ en 1 adjudicación y 1 órgano; UTE Telefónica - Sphera 408,6 M€ (NIF de relleno A00000000, 7 órganos); Janssen-Cilag 327,4 M€ en 21 órganos con 82,5 % a una oferta.

-- P2.2 Menores cerca del umbral: contratos menores por tramo de 1.000 € de presupuesto, servicios/suministros (10-16 k€) y obras (34-42 k€)
SELECT CASE WHEN l.tipo_key = '3' THEN 'Obras (umbral 40.000)' ELSE 'Servicios y suministros (umbral 15.000)' END AS familia,
       l.tramo_1000, count(*) AS contratos, round(sum(l.presupuesto_sin_iva) / 1e6, 2) AS presupuesto_millones
FROM hecho_licitacion l
WHERE l.procedimiento_key = '6' AND l.tipo_key IN ('1', '2', '3')
  AND ((l.tipo_key = '3' AND l.tramo_1000 BETWEEN 34000 AND 41000) OR (l.tipo_key <> '3' AND l.tramo_1000 BETWEEN 10000 AND 16000))
GROUP BY ALL ORDER BY 1, 2;
-- ej. servicios y suministros: tramo 13.000 = 595, 14.000 = 2.694 (×4,5), 15.000 = 98; obras: 38.000 = 93, 39.000 = 395 (×4,2), 40.000 = 5.

-- P2.3 Indicios de fraccionamiento: grupos órgano + adjudicatario + tipo + año con 2+ menores que juntos superan el umbral
SELECT o.organo, e.nombre AS adjudicatario, t.etiqueta AS tipo, year(a.fecha_adjudicacion_key) AS anio,
       count(*) AS menores, round(sum(a.importe_repartido)) AS importe_sumado,
       round(sum(a.importe_repartido) / CASE WHEN max(a.tipo_key) = '3' THEN 40000 ELSE 15000 END, 1) AS veces_umbral
FROM hecho_adjudicacion a JOIN dim_organo o USING (organo_key) JOIN dim_empresa e USING (empresa_key) JOIN dim_tipo t USING (tipo_key)
WHERE a.en_grupo_fraccionamiento AND a.procedimiento_key = '6' AND a.resultado_key IN ('8', '9')
GROUP BY ALL ORDER BY importe_sumado DESC LIMIT 25;
-- ej. 790 grupos y 3.818 contratos menores; el mayor: un rectorado y EBSCO, 7 menores de suministros en 2026 por 246.543 € (16,4 veces el umbral).

-- P2.4 Negociado sin publicidad: por órgano, lotes, % con una sola oferta e importe
SELECT o.organo, count(*) AS lotes, round(100.0 * count(*) FILTER (WHERE h.una_oferta) / count(*) FILTER (WHERE h.ofertas IS NOT NULL), 1) AS pct_una_oferta,
       round(sum(h.importe_lote) / 1e6, 1) AS importe_millones
FROM hecho_lote h JOIN hecho_licitacion l USING (id) JOIN dim_organo o ON o.organo_key = l.organo_key
WHERE l.procedimiento_key = '3' AND h.adjudicado AND NOT h.importe_sospechoso
GROUP BY ALL HAVING count(*) >= 10 ORDER BY importe_millones DESC LIMIT 20;
-- ej. global: 3.957 lotes adjudicados por negociado sin publicidad, 93,5 % con una oferta; Osakidetza 75 lotes, 97,3 %, 477,6 M€.

-- =====================================================================================================================
-- P3. Regulador
-- =====================================================================================================================
-- P3.1 % de lotes adjudicados con una sola oferta por procedimiento
SELECT p.etiqueta AS procedimiento, count(*) AS lotes,
       round(100.0 * count(*) FILTER (WHERE h.una_oferta) / count(*) FILTER (WHERE h.ofertas IS NOT NULL), 1) AS pct_una_oferta
FROM hecho_lote h JOIN hecho_licitacion l USING (id) JOIN dim_procedimiento p ON p.procedimiento_key = l.procedimiento_key
WHERE h.adjudicado
GROUP BY ALL HAVING count(*) >= 100 ORDER BY lotes DESC;
-- ej. Contrato menor 85,6 % (46.588 lotes); Abierto 38,3 % (27.438); Abierto simplificado 33,8 % (10.912); Negociado sin publicidad 93,5 % (3.957); Derivado de acuerdo marco 66,8 %.

-- P3.2 % de lotes con una oferta por feed (las tres sindicaciones no se mezclan sin este corte) y tipo
SELECT f.etiqueta AS feed, t.etiqueta AS tipo, count(*) AS lotes,
       round(100.0 * count(*) FILTER (WHERE h.una_oferta) / count(*) FILTER (WHERE h.ofertas IS NOT NULL), 1) AS pct_una_oferta
FROM hecho_lote h JOIN hecho_licitacion l USING (id) JOIN dim_feed f ON f.feed = h.feed JOIN dim_tipo t ON t.tipo_key = l.tipo_key
WHERE h.adjudicado AND l.tipo_key IN ('1', '2', '3')
GROUP BY ALL ORDER BY 1, 2;
-- ej. Perfiles alojados: obras 33,2 %, servicios 42,5 %, suministros 42,9 %; Agregadas: 34,3 / 40,4 / 46,7 %; Menores: 65,2 / 87,7 / 85,7 %.

-- P3.3 % de lotes con una oferta por división CPV (licitaciones no menores)
SELECT c.division, count(*) AS lotes,
       round(100.0 * count(*) FILTER (WHERE h.una_oferta) / count(*) FILTER (WHERE h.ofertas IS NOT NULL), 1) AS pct_una_oferta
FROM hecho_lote h JOIN hecho_licitacion l USING (id) JOIN dim_cpv c ON c.cpv_key = l.cpv_key
WHERE h.adjudicado AND l.procedimiento_key <> '6' AND NOT c.sin_cpv
GROUP BY ALL HAVING count(*) >= 200 ORDER BY pct_una_oferta DESC;
-- ej. Ocio, cultura y deporte 68,3 % de 2.124 lotes; Equipos médicos y farmacia 51,5 % de 7.601; Trabajos de construcción 33,5 % de 6.013.

-- P3.4 % de lotes con una oferta por órgano (mínimo 50 lotes no menores)
SELECT o.organo, count(*) AS lotes, round(100.0 * count(*) FILTER (WHERE h.una_oferta) / count(*) FILTER (WHERE h.ofertas IS NOT NULL), 1) AS pct_una_oferta,
       round(sum(h.importe_lote) / 1e6, 1) AS importe_millones
FROM hecho_lote h JOIN hecho_licitacion l USING (id) JOIN dim_organo o ON o.organo_key = l.organo_key
WHERE h.adjudicado AND l.procedimiento_key <> '6' AND NOT h.importe_sospechoso
GROUP BY ALL HAVING count(*) >= 50 ORDER BY pct_una_oferta DESC LIMIT 20;
-- ej. CIC nanoGUNE 98,0 % de 51 lotes; Gerencia de Servicios Sanitarios de Fuerteventura 92,7 % de 109; Osakidetza 69,9 % de 495 lotes y 685 M€.

-- P3.5 Plazo de presentación (publicación → fin de plazo) por procedimiento: mediana, p10, p90
SELECT p.etiqueta AS procedimiento, count(*) AS licitaciones, median(l.dias_plazo) AS dias_mediana,
       quantile_cont(l.dias_plazo, 0.1) AS p10, quantile_cont(l.dias_plazo, 0.9) AS p90,
       count(*) FILTER (WHERE l.dias_plazo < 0) AS plazo_antes_de_publicar
FROM hecho_licitacion l JOIN dim_procedimiento p USING (procedimiento_key)
WHERE l.dias_plazo IS NOT NULL AND l.procedimiento_key <> '6'
GROUP BY ALL HAVING count(*) >= 100 ORDER BY licitaciones DESC;
-- ej. Abierto: mediana 28 días (p10 15, p90 43), 121 con plazo anterior a la publicación; Abierto simplificado: 17 (14-24); Negociado sin publicidad: 11.

-- P3.6 Desiertos: % de lotes desiertos por tipo y división CPV
SELECT t.etiqueta AS tipo, c.division, count(*) AS lotes, round(100.0 * count(*) FILTER (WHERE h.desierto) / count(*), 1) AS pct_desiertos
FROM hecho_lote h JOIN hecho_licitacion l USING (id) JOIN dim_tipo t ON t.tipo_key = l.tipo_key JOIN dim_cpv c ON c.cpv_key = l.cpv_key
WHERE l.procedimiento_key <> '6' AND h.resultado_key IN ('3', '8', '9')
GROUP BY ALL HAVING count(*) >= 200 ORDER BY pct_desiertos DESC LIMIT 15;
-- ej. Patrimonial / sin CPV 51,9 % de 297 lotes; Concesión de servicios / Hostelería 24,5 %; Servicios / Transporte 13,7 % de 2.016; Obras / Construcción 9,8 % de 6.575.

-- P3.7 Cuota pyme por tipo (solo feeds que traen el campo: 643 y 1143; el 1044 queda fuera y se avisa en el visual)
SELECT f.etiqueta AS feed, t.etiqueta AS tipo, count(*) AS adjudicaciones,
       round(100.0 * count(*) FILTER (WHERE a.pyme) / count(*) FILTER (WHERE a.pyme IS NOT NULL), 1) AS pct_adjudicaciones_pyme,
       round(100.0 * sum(a.importe_repartido) FILTER (WHERE a.pyme) / sum(a.importe_repartido) FILTER (WHERE a.pyme IS NOT NULL), 1) AS pct_importe_pyme
FROM hecho_adjudicacion a JOIN dim_feed f USING (feed) JOIN dim_tipo t USING (tipo_key)
WHERE a.resultado_key IN ('8', '9') AND f.trae_pyme AND a.tipo_key IN ('1', '2', '3')
GROUP BY ALL ORDER BY 1, 2;
-- ej. Perfiles alojados: obras 67,0 % de adjudicaciones a pyme pero 29,0 % del importe; servicios 59,5 % / 19,7 %; Menores: obras 60,1 % / 60,4 %.

-- =====================================================================================================================
-- P4. Analista
-- =====================================================================================================================
-- P4.1 Tiempo de adjudicación (fin de plazo → adjudicación) por procedimiento y trimestre de adjudicación
SELECT p.etiqueta AS procedimiento, d.anio || '-T' || d.trimestre AS trimestre, count(*) AS licitaciones,
       median(l.dias_hasta_adjudicacion) AS dias_mediana
FROM hecho_licitacion l JOIN dim_procedimiento p USING (procedimiento_key) JOIN dim_fecha d ON d.fecha_key = l.fecha_adjudicacion_key
WHERE l.dias_hasta_adjudicacion BETWEEN 0 AND 730 AND l.procedimiento_key IN ('1', '9', '3', '2') AND d.anio >= 2025
GROUP BY ALL HAVING count(*) >= 50 ORDER BY 1, 2;
-- ej. Abierto 2026-T3: mediana 52 días (8.834 licitaciones); Abierto simplificado 36; Negociado sin publicidad 23; Restringido 21.

-- P4.2 Concentración del gasto por órgano: top 20 y cuota acumulada (Pareto)
SELECT o.organo, o.tipo_identificador, round(sum(a.importe_repartido) / 1e6, 1) AS importe_millones,
       round(100.0 * sum(sum(a.importe_repartido)) OVER (ORDER BY sum(a.importe_repartido) DESC) / sum(sum(a.importe_repartido)) OVER (), 1) AS pct_acumulado
FROM hecho_adjudicacion a JOIN dim_organo o USING (organo_key)
WHERE a.resultado_key IN ('8', '9') AND NOT a.importe_sospechoso
GROUP BY ALL ORDER BY importe_millones DESC LIMIT 20;
-- ej. Servicio Andaluz de Salud 1.430,6 M€ (4,9 %), Canal de Isabel II 1.075,9 M€, INGESA 1.024,2 M€; los 20 primeros órganos suman el 44,7 % del importe adjudicado.

-- P4.3 Gasto por territorio (CCAA, con la provincia como desglose) y aviso de cuánto queda sin territorio
SELECT tr.ccaa, count(*) AS adjudicaciones, round(sum(a.importe_repartido) / 1e6, 1) AS importe_millones,
       round(100.0 * sum(a.importe_repartido) / sum(sum(a.importe_repartido)) OVER (), 1) AS pct
FROM hecho_adjudicacion a JOIN dim_territorio tr USING (nuts_key)
WHERE a.resultado_key IN ('8', '9') AND NOT a.importe_sospechoso
GROUP BY ALL ORDER BY importe_millones DESC;
-- ej. Madrid 7.974 M€ (27,1 %), Andalucía 4.948 M€ (16,8 %), "Toda España" (NUTS ES, sin provincia) 2.877 M€ (9,8 %); total 29.422 M€.

-- P4.4 Serie mensual: importe adjudicado repartido y lotes por feed (mes de adjudicación; 1044 usa la fecha del contrato)
SELECT d.anio_mes, f.etiqueta AS feed, count(*) AS lotes, round(sum(h.importe_lote) / 1e6, 1) AS importe_millones
FROM hecho_lote h JOIN dim_feed f USING (feed) JOIN dim_fecha d ON d.fecha_key = h.fecha_adjudicacion
WHERE h.adjudicado AND d.anio >= 2026 AND NOT h.importe_sospechoso
GROUP BY ALL ORDER BY 1, 2;
-- ej. 2026-09: Perfiles alojados 12.092 lotes y 3.444 M€; Agregadas 3.972 lotes y 2.168 M€; Menores 16.378 lotes y 89,5 M€.

-- P4.5 Calidad del dato (visual de aviso): % de filas sin DIR3, sin CPV, sin NUTS, sin fecha, fechas sucias, por feed
SELECT f.etiqueta AS feed, count(*) AS licitaciones,
       round(100.0 * count(*) FILTER (WHERE o.dir3 IS NULL) / count(*), 1) AS pct_sin_dir3,
       round(100.0 * count(*) FILTER (WHERE l.cpv_key = '?') / count(*), 1) AS pct_sin_cpv,
       round(100.0 * count(*) FILTER (WHERE l.fecha_publicacion_key IS NULL) / count(*), 1) AS pct_sin_fecha_publicacion,
       round(100.0 * count(*) FILTER (WHERE l.plazo_key IS NULL) / count(*), 1) AS pct_sin_plazo,
       count(*) FILTER (WHERE l.plazo_sucio OR l.fecha_publicacion_sucia) AS fechas_imposibles
FROM hecho_licitacion l JOIN dim_feed f USING (feed) JOIN dim_organo o USING (organo_key)
GROUP BY ALL ORDER BY licitaciones DESC;
-- ej. Agregadas: 80,6 % sin DIR3, 12,0 % sin fecha de publicación, 19 fechas imposibles; Menores: 47,8 % sin CPV, 96,9 % sin fecha de publicación, 76,6 % sin plazo.
