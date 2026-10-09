#!/usr/bin/env python
"""Construye el modelo dimensional de contratación pública (PLACSP) desde el almacén local.

Lee placsp_ultimo y adjudicaciones_ultimo con `conectar` (scripts/clientes/almacen.py) y deja en SALIDA un Parquet por
tabla: hecho_licitacion (una fila por expediente), hecho_lote (una por expediente-lote), hecho_adjudicacion (una por
expediente-lote-adjudicatario) y las dimensiones. Al final imprime los cuadres: importes del hecho = fuente tras repartir
los compartidos, y recuentos frente al almacén.

Uso: .venv/bin/python dashboards/contratacion-publica/build_modelo.py [ruta_almacen]
"""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "clientes"))
from almacen import conectar  # noqa: E402

SALIDA = Path(__file__).resolve().parent / "salida"
ALMACEN = sys.argv[1] if len(sys.argv) > 1 else str(REPO / "almacen")

# Ventana de fechas creíbles: fuera de ella (años 0023, 0203, 2080...) la fecha pasa a NULL y la clave a -1
FECHA_MIN, FECHA_MAX = "2015-01-01", "2027-12-31"
UMBRAL_OBRAS, UMBRAL_RESTO = 40000, 15000

# --- Etiquetas (códigos CODICE). Los marcados (*) no venían en el enunciado y están tomados de la lista de códigos
# CODICE de memoria: comprobar contra la documentación oficial antes de publicar.
TIPO = {"1": "Suministros", "2": "Servicios", "3": "Obras", "7": "Administrativo especial (*)", "8": "Privado (*)",
        "21": "Gestión de servicios públicos (*)", "22": "Concesión de servicios (*)", "31": "Concesión de obra pública (*)",
        "32": "Concesión de obras (*)", "40": "Colaboración público-privada (*)", "50": "Patrimonial (*)", "999": "Otros (*)"}
PROCEDIMIENTO = {"1": "Abierto", "2": "Restringido", "3": "Negociado sin publicidad", "4": "Diálogo competitivo (*)",
                 "5": "Negociado con publicidad (*)", "6": "Contrato menor", "7": "Derivado de acuerdo marco",
                 "8": "Asociación para la innovación (*)", "9": "Abierto simplificado", "10": "Concurso de proyectos (*)",
                 "11": "Basado en sistema dinámico (*)", "12": "Contratación centralizada (*)", "13": "Licitación con negociación",
                 "100": "Normas internas", "999": "Otros (*)"}
RESULTADO = {"3": "Desierto", "4": "Desistimiento", "5": "Renuncia", "8": "Adjudicado", "9": "Formalizado"}
ESTADO = {"PRE": "Anuncio previo", "PUB": "Publicada", "EV": "En evaluación", "ADJ": "Adjudicada", "RES": "Resuelta",
          "ANUL": "Anulada"}
FEED = {"643": "Perfiles alojados (sin menores)", "1044": "Plataformas agregadas (sin menores)", "1143": "Contratos menores"}
CCAA = {"ES11": "Galicia", "ES12": "Asturias", "ES13": "Cantabria", "ES21": "País Vasco", "ES22": "Navarra",
        "ES23": "La Rioja", "ES24": "Aragón", "ES30": "Madrid", "ES41": "Castilla y León", "ES42": "Castilla-La Mancha",
        "ES43": "Extremadura", "ES51": "Cataluña", "ES52": "Comunidad Valenciana", "ES53": "Illes Balears",
        "ES61": "Andalucía", "ES62": "Murcia", "ES63": "Ceuta", "ES64": "Melilla", "ES70": "Canarias"}
PROVINCIA = {  # NUTS 2021, de memoria (*): comprobar contra Eurostat
    "ES111": "A Coruña", "ES112": "Lugo", "ES113": "Ourense", "ES114": "Pontevedra", "ES120": "Asturias",
    "ES130": "Cantabria", "ES211": "Araba/Álava", "ES212": "Gipuzkoa", "ES213": "Bizkaia", "ES220": "Navarra",
    "ES230": "La Rioja", "ES241": "Huesca", "ES242": "Teruel", "ES243": "Zaragoza", "ES300": "Madrid",
    "ES411": "Ávila", "ES412": "Burgos", "ES413": "León", "ES414": "Palencia", "ES415": "Salamanca", "ES416": "Segovia",
    "ES417": "Soria", "ES418": "Valladolid", "ES419": "Zamora", "ES421": "Albacete", "ES422": "Ciudad Real",
    "ES423": "Cuenca", "ES424": "Guadalajara", "ES425": "Toledo", "ES431": "Badajoz", "ES432": "Cáceres",
    "ES511": "Barcelona", "ES512": "Girona", "ES513": "Lleida", "ES514": "Tarragona", "ES521": "Alicante",
    "ES522": "Castellón", "ES523": "Valencia", "ES531": "Eivissa y Formentera", "ES532": "Mallorca", "ES533": "Menorca",
    "ES611": "Almería", "ES612": "Cádiz", "ES613": "Córdoba", "ES614": "Granada", "ES615": "Huelva", "ES616": "Jaén",
    "ES617": "Málaga", "ES618": "Sevilla", "ES620": "Murcia", "ES630": "Ceuta", "ES640": "Melilla",
    "ES703": "El Hierro", "ES704": "Fuerteventura", "ES705": "Gran Canaria", "ES706": "La Gomera", "ES707": "La Palma",
    "ES708": "Lanzarote", "ES709": "Tenerife"}
CPV_DIVISION = {  # divisiones CPV 2008, resumidas, de memoria (*)
    "03": "Agricultura, ganadería y pesca", "09": "Combustibles y energía", "14": "Minería y materias primas",
    "15": "Alimentos y bebidas", "16": "Maquinaria agrícola", "18": "Ropa y calzado", "19": "Cuero, textil y plástico",
    "22": "Impresos y publicaciones", "24": "Productos químicos", "30": "Máquinas de oficina e informática",
    "31": "Máquinas y aparatos eléctricos", "32": "Equipos de radio, TV y comunicación", "33": "Equipos médicos y farmacia",
    "34": "Equipos de transporte", "35": "Seguridad y defensa", "37": "Instrumentos musicales y deporte",
    "38": "Equipos de laboratorio y óptica", "39": "Mobiliario y menaje", "41": "Agua recogida y depurada",
    "42": "Maquinaria industrial", "43": "Maquinaria de minería y construcción", "44": "Materiales de construcción",
    "45": "Trabajos de construcción", "48": "Software", "50": "Reparación y mantenimiento", "51": "Instalación",
    "55": "Hostelería y restauración", "60": "Transporte", "63": "Servicios auxiliares de transporte",
    "64": "Correos y telecomunicaciones", "65": "Servicios públicos (agua, gas, electricidad)",
    "66": "Servicios financieros y seguros", "70": "Servicios inmobiliarios", "71": "Arquitectura e ingeniería",
    "72": "Servicios TI", "73": "I+D", "75": "Administración pública y defensa", "76": "Petróleo y gas",
    "77": "Agricultura, silvicultura y jardinería", "79": "Servicios a empresas", "80": "Educación y formación",
    "85": "Salud y servicios sociales", "90": "Alcantarillado, residuos y medio ambiente",
    "92": "Ocio, cultura y deporte", "98": "Otros servicios comunitarios"}


def tabla_etiquetas(con, nombre, diccionario, clave="codigo", etiqueta="etiqueta"):
    con.execute(f"CREATE OR REPLACE TABLE {nombre} ({clave} VARCHAR, {etiqueta} VARCHAR)")
    con.executemany(f"INSERT INTO {nombre} VALUES (?, ?)", list(diccionario.items()))


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    con = conectar(ALMACEN, solo_lectura=False)  # para escribir fuera del almacén
    con.execute(f"SET memory_limit='4GB'")
    for nombre, d in [("etq_tipo", TIPO), ("etq_procedimiento", PROCEDIMIENTO), ("etq_resultado", RESULTADO),
                      ("etq_estado", ESTADO), ("etq_feed", FEED), ("etq_ccaa", CCAA), ("etq_provincia", PROVINCIA),
                      ("etq_cpv", CPV_DIVISION)]:
        tabla_etiquetas(con, nombre, d)

    # ---------- Fuente limpia: licitaciones (una por expediente) ----------
    con.execute(f"""
    CREATE OR REPLACE TABLE src_lic AS
    SELECT id, feed, expediente, organo, organo_dir3, organo_nif, organo_plataforma, objeto, link,
           coalesce(organo_dir3, organo_nif, organo_plataforma) AS organo_key,
           CASE WHEN organo_dir3 IS NOT NULL THEN 'DIR3' WHEN organo_nif IS NOT NULL THEN 'NIF' ELSE 'ID_PLATAFORMA' END AS organo_id_tipo,
           coalesce(tipo, '?') AS tipo_key, coalesce(procedimiento, '?') AS procedimiento_key, coalesce(estado, '?') AS estado_key,
           coalesce(anulada, false) AS anulada,
           CASE WHEN importe_sin_iva > 0 THEN importe_sin_iva END AS presupuesto_sin_iva,
           importe_sin_iva AS presupuesto_bruto, valor_estimado, importe_total AS presupuesto_con_iva,
           cpv[1] AS cpv_principal, len(cpv) AS n_cpv,
           coalesce(nuts, '?') AS nuts_key,
           CASE WHEN fecha_publicacion BETWEEN '{FECHA_MIN}' AND '{FECHA_MAX}' THEN fecha_publicacion END AS fecha_publicacion,
           CASE WHEN plazo_presentacion BETWEEN '{FECHA_MIN}' AND '{FECHA_MAX}' THEN plazo_presentacion END AS plazo_presentacion,
           (fecha_publicacion IS NOT NULL AND fecha_publicacion NOT BETWEEN '{FECHA_MIN}' AND '{FECHA_MAX}') AS fecha_publicacion_sucia,
           (plazo_presentacion IS NOT NULL AND plazo_presentacion NOT BETWEEN '{FECHA_MIN}' AND '{FECHA_MAX}') AS plazo_sucio
    FROM placsp_ultimo""")

    # ---------- Fuente limpia: adjudicaciones (una por lote-adjudicatario) ----------
    # importe_compartido viene NULL cuando el importe es NULL: entonces no hay nada que repartir (0).
    # El reparto se hace entre los adjudicatarios CON importe (adjudicatarios_con_importe), no entre todos: en 13 lotes
    # compartidos algún adjudicatario trae importe nulo y dividir entre `adjudicatarios` perdía 459.746 €.
    con.execute(f"""
    CREATE OR REPLACE TABLE src_adj AS
    SELECT a.id, a.feed, a.n, coalesce(a.lote, '') AS lote, a.resultado AS resultado_key, a.ofertas, a.pyme,
           coalesce(a.persona_fisica, false) AS persona_fisica, a.nif, a.nombre, a.contrato,
           a.importe_sin_iva AS importe_fila, a.importe_total AS importe_fila_con_iva,
           a.adjudicatarios, coalesce(a.importe_compartido, false) AS importe_compartido,
           count(a.importe_sin_iva) OVER (PARTITION BY a.id, a.lote) AS adjudicatarios_con_importe,
           CASE WHEN coalesce(a.importe_compartido, false)
                THEN a.importe_sin_iva / count(a.importe_sin_iva) OVER (PARTITION BY a.id, a.lote)
                ELSE a.importe_sin_iva END AS importe_repartido,
           coalesce(a.fecha_adjudicacion, a.fecha_contrato) AS fecha_bruta,
           CASE WHEN coalesce(a.fecha_adjudicacion, a.fecha_contrato) BETWEEN '{FECHA_MIN}' AND '{FECHA_MAX}'
                THEN coalesce(a.fecha_adjudicacion, a.fecha_contrato) END AS fecha_adjudicacion,
           a.fecha_adjudicacion IS NULL AND a.fecha_contrato IS NOT NULL AS fecha_es_de_contrato,
           CASE WHEN a.persona_fisica THEN 'PERSONA_FISICA' WHEN a.nif IS NULL THEN 'SIN_NIF' ELSE upper(trim(a.nif)) END AS empresa_key
    FROM adjudicaciones_ultimo a""")

    # Coma perdida en origen: adjudicado > 10 veces el presupuesto del expediente (20 filas, ~1.992 M€ en este corte; la mayor,
    # 1.954 M€ sobre 22.000 € de presupuesto). Se marca, no se borra: los cuadres incluyen la fila y el dashboard la excluye.
    con.execute("ALTER TABLE src_adj ADD COLUMN importe_sospechoso BOOLEAN DEFAULT false")
    con.execute("""UPDATE src_adj SET importe_sospechoso = true FROM src_lic s
                   WHERE src_adj.id = s.id AND s.presupuesto_sin_iva > 0 AND src_adj.importe_fila > 10 * s.presupuesto_sin_iva""")

    # ---------- Dimensiones ----------
    con.execute(f"""
    CREATE OR REPLACE TABLE dim_fecha AS
    SELECT d::DATE AS fecha_key, year(d) AS anio, quarter(d) AS trimestre, month(d) AS mes,
           strftime(d, '%Y-%m') AS anio_mes, isodow(d) AS dia_semana, isodow(d) >= 6 AS fin_de_semana
    FROM range(DATE '{FECHA_MIN}', DATE '{FECHA_MAX}' + INTERVAL 1 DAY, INTERVAL 1 DAY) t(d)
    UNION ALL SELECT NULL, NULL, NULL, NULL, 'desconocido', NULL, NULL
    """)

    con.execute("""
    CREATE OR REPLACE TABLE dim_organo AS
    SELECT organo_key, any_value(organo_id_tipo) AS tipo_identificador, mode(organo) AS organo,
           list(DISTINCT organo) AS nombres, max(organo_dir3) AS dir3, max(organo_nif) AS nif, max(organo_plataforma) AS id_plataforma,
           mode(nuts_key) AS nuts_mas_frecuente, list(DISTINCT feed) AS feeds, count(*) AS licitaciones
    FROM src_lic GROUP BY organo_key""")

    con.execute(r"""
    CREATE OR REPLACE TABLE dim_empresa AS
    SELECT empresa_key, mode(nombre) AS nombre, list(DISTINCT nombre)[1:5] AS nombres,
           empresa_key = 'PERSONA_FISICA' AS persona_fisica, empresa_key = 'SIN_NIF' AS sin_nif,
           CASE WHEN empresa_key IN ('PERSONA_FISICA', 'SIN_NIF') THEN 'sin identificador'
                WHEN regexp_matches(empresa_key, '^[A-Z]?0{7,8}[A-Z0-9]?$') THEN 'inválido'  -- relleno: A00000000, 000000000
                WHEN regexp_matches(empresa_key, '^[ABCDEFGHJNPQRSUVW][0-9]{7}[0-9A-J]$') THEN 'NIF español'
                WHEN regexp_matches(empresa_key, '^[0-9]{8}[A-Z]$|^[XYZ][0-9]{7}[A-Z]$') THEN 'DNI/NIE (debería ser persona física)'
                WHEN regexp_matches(empresa_key, '^[A-Z]{2}[0-9A-Z]{6,}$') THEN 'identificador extranjero (probable)'
                ELSE 'inválido' END AS formato_identificador,
           bool_or(pyme) AS pyme_alguna_vez, count(*) AS adjudicaciones, min(fecha_adjudicacion) AS primera, max(fecha_adjudicacion) AS ultima
    FROM src_adj GROUP BY empresa_key""")

    con.execute("""
    CREATE OR REPLACE TABLE dim_cpv AS
    SELECT c.cpv_key, c.cpv_key[1:2] AS division_codigo, coalesce(e.etiqueta, 'División desconocida') AS division,
           c.cpv_key[1:3] AS grupo_codigo, c.cpv_key[1:4] AS clase_codigo, c.cpv_key = '?' AS sin_cpv
    FROM (SELECT DISTINCT coalesce(cpv_principal, '?') AS cpv_key FROM src_lic) c
    LEFT JOIN etq_cpv e ON e.codigo = c.cpv_key[1:2]""")

    con.execute("""
    CREATE OR REPLACE TABLE dim_territorio AS
    SELECT t.nuts_key,
           CASE WHEN length(t.nuts_key) >= 5 THEN t.nuts_key[1:5] END AS nuts3,
           coalesce(p.etiqueta, CASE WHEN length(t.nuts_key) >= 5 THEN t.nuts_key END) AS provincia,
           CASE WHEN length(t.nuts_key) >= 4 THEN t.nuts_key[1:4] END AS nuts2,
           coalesce(c.etiqueta, CASE WHEN t.nuts_key = 'ES' THEN 'Toda España' WHEN t.nuts_key = '?' THEN 'Sin territorio'
                                     WHEN t.nuts_key NOT LIKE 'ES%' THEN 'Fuera de España' ELSE 'CCAA desconocida' END) AS ccaa,
           CASE WHEN t.nuts_key = '?' THEN 'desconocido' WHEN t.nuts_key NOT LIKE 'ES%' THEN 'extranjero'
                WHEN length(t.nuts_key) = 2 THEN 'nacional' WHEN length(t.nuts_key) = 3 THEN 'nuts1'
                WHEN length(t.nuts_key) = 4 THEN 'ccaa' ELSE 'provincia' END AS nivel
    FROM (SELECT DISTINCT nuts_key FROM src_lic) t
    LEFT JOIN etq_provincia p ON p.codigo = t.nuts_key[1:5]
    LEFT JOIN etq_ccaa c ON c.codigo = t.nuts_key[1:4]""")

    for dim, etq, fuente, col in [("dim_tipo", "etq_tipo", "src_lic", "tipo_key"),
                                  ("dim_procedimiento", "etq_procedimiento", "src_lic", "procedimiento_key"),
                                  ("dim_estado", "etq_estado", "src_lic", "estado_key"),
                                  ("dim_resultado", "etq_resultado", "src_adj", "resultado_key"),
                                  ("dim_feed", "etq_feed", "src_lic", "feed")]:
        con.execute(f"""
        CREATE OR REPLACE TABLE {dim} AS
        SELECT s.{col}, coalesce(e.etiqueta, CASE WHEN s.{col} = '?' THEN 'Desconocido' ELSE 'Código ' || s.{col} END) AS etiqueta
        FROM (SELECT DISTINCT {col} FROM {fuente}) s LEFT JOIN {etq} e ON e.codigo = s.{col}""")
    con.execute("ALTER TABLE dim_resultado ADD COLUMN desierto BOOLEAN")
    con.execute("UPDATE dim_resultado SET desierto = resultado_key = '3'")
    con.execute("ALTER TABLE dim_resultado ADD COLUMN adjudicado BOOLEAN")
    con.execute("UPDATE dim_resultado SET adjudicado = resultado_key IN ('8', '9')")
    con.execute("ALTER TABLE dim_feed ADD COLUMN trae_pyme BOOLEAN")
    con.execute("UPDATE dim_feed SET trae_pyme = feed <> '1044'")
    con.execute("ALTER TABLE dim_feed ADD COLUMN trae_fecha_adjudicacion BOOLEAN")
    con.execute("UPDATE dim_feed SET trae_fecha_adjudicacion = feed <> '1044'")

    # ---------- hecho_lote: una fila por expediente-lote ----------
    # ofertas y resultado son del lote (se repiten en cada adjudicatario); el importe se cuenta una vez.
    con.execute("""
    CREATE OR REPLACE TABLE hecho_lote AS
    SELECT id, lote, feed, max(ofertas) AS ofertas, max(resultado_key) AS resultado_key,
           count(*) AS n_adjudicatarios,
           count(*) FILTER (WHERE persona_fisica) AS n_personas_fisicas,
           bool_or(importe_compartido) AS importe_compartido,
           bool_or(importe_sospechoso) AS importe_sospechoso,
           sum(importe_repartido) AS importe_lote,
           min(fecha_adjudicacion) AS fecha_adjudicacion,
           bool_or(pyme) AS pyme_alguna, bool_and(pyme) AS pyme_todas,
           max(ofertas) = 1 AS una_oferta,
           max(resultado_key) = '3' AS desierto,
           max(resultado_key) IN ('8', '9') AS adjudicado
    FROM src_adj GROUP BY id, lote, feed""")

    # ---------- hecho_licitacion: una fila por expediente ----------
    con.execute(f"""
    CREATE OR REPLACE TABLE hecho_licitacion AS
    WITH l AS (SELECT id, count(*) AS n_lotes, sum(importe_lote) AS importe_adjudicado, bool_or(importe_sospechoso) AS importe_sospechoso,
                      min(fecha_adjudicacion) AS fecha_adjudicacion,
                      max(fecha_adjudicacion) AS fecha_ultima_adjudicacion,
                      count(*) FILTER (WHERE adjudicado) AS lotes_adjudicados, count(*) FILTER (WHERE desierto) AS lotes_desiertos,
                      count(*) FILTER (WHERE una_oferta) AS lotes_una_oferta, sum(ofertas) AS ofertas_total
               FROM hecho_lote GROUP BY id)
    SELECT s.id, s.feed, s.expediente, s.objeto, s.link, s.organo_key, s.tipo_key, s.procedimiento_key, s.estado_key,
           coalesce(s.cpv_principal, '?') AS cpv_key, s.n_cpv, s.nuts_key, s.anulada,
           s.fecha_publicacion AS fecha_publicacion_key, s.plazo_presentacion AS plazo_key, l.fecha_adjudicacion AS fecha_adjudicacion_key,
           s.fecha_publicacion_sucia, s.plazo_sucio, s.presupuesto_bruto IS NULL AS sin_presupuesto, s.presupuesto_bruto <= 0 AS presupuesto_cero,
           s.presupuesto_sin_iva, s.valor_estimado, s.presupuesto_con_iva,
           coalesce(l.n_lotes, 0) AS n_lotes, coalesce(l.lotes_adjudicados, 0) AS lotes_adjudicados, coalesce(l.lotes_desiertos, 0) AS lotes_desiertos,
           coalesce(l.lotes_una_oferta, 0) AS lotes_una_oferta, l.ofertas_total,
           l.importe_adjudicado, coalesce(l.importe_sospechoso, false) AS importe_sospechoso,
           CASE WHEN s.presupuesto_sin_iva > 0 AND l.n_lotes = 1 AND l.lotes_adjudicados = 1 AND l.importe_adjudicado > 0
                THEN l.importe_adjudicado / s.presupuesto_sin_iva END AS ratio_adjudicado_presupuesto,
           CASE WHEN l.n_lotes = 1 AND l.lotes_adjudicados = 1 AND l.importe_adjudicado > 0 AND s.presupuesto_sin_iva > 0
                 AND l.importe_adjudicado / s.presupuesto_sin_iva BETWEEN 0.1 AND 1.05 THEN true ELSE false END AS ratio_fiable,
           (s.plazo_presentacion - s.fecha_publicacion) AS dias_plazo,
           (l.fecha_adjudicacion - s.plazo_presentacion) AS dias_hasta_adjudicacion,
           (l.fecha_adjudicacion - s.fecha_publicacion) AS dias_publicacion_adjudicacion,
           l.n_lotes IS NULL AS sin_adjudicacion,
           CASE WHEN s.procedimiento_key = '6' AND s.tipo_key = '3' AND s.presupuesto_sin_iva BETWEEN {UMBRAL_OBRAS * 0.975} AND {UMBRAL_OBRAS - 0.01} THEN true
                WHEN s.procedimiento_key = '6' AND s.tipo_key <> '3' AND s.presupuesto_sin_iva BETWEEN {UMBRAL_RESTO - 1000} AND {UMBRAL_RESTO - 0.01} THEN true
                ELSE false END AS menor_cerca_umbral,
           CASE WHEN s.procedimiento_key = '6' THEN floor(s.presupuesto_sin_iva / 1000) * 1000 END AS tramo_1000
    FROM src_lic s LEFT JOIN l USING (id)""")

    # ---------- hecho_adjudicacion: una fila por expediente-lote-adjudicatario ----------
    con.execute(f"""
    CREATE OR REPLACE TABLE hecho_adjudicacion AS
    WITH g AS (  -- indicio de fraccionamiento: mismo órgano, adjudicatario y tipo, en el mismo año, varios menores que juntos superan el umbral
        SELECT s.organo_key, a.empresa_key, s.tipo_key, year(a.fecha_adjudicacion) AS anio,
               count(*) AS n_menores_grupo, sum(a.importe_repartido) AS importe_grupo
        FROM src_adj a JOIN src_lic s USING (id)
        WHERE s.procedimiento_key = '6' AND a.resultado_key IN ('8', '9') AND a.empresa_key NOT IN ('PERSONA_FISICA', 'SIN_NIF')
        GROUP BY ALL
        HAVING count(*) >= 2 AND sum(a.importe_repartido) > CASE WHEN s.tipo_key = '3' THEN {UMBRAL_OBRAS} ELSE {UMBRAL_RESTO} END)
    SELECT a.id, a.lote, a.n, a.feed, a.empresa_key, s.organo_key, s.tipo_key, s.procedimiento_key, coalesce(s.cpv_principal, '?') AS cpv_key,
           s.nuts_key, coalesce(a.resultado_key, '?') AS resultado_key, a.fecha_adjudicacion AS fecha_adjudicacion_key,
           a.fecha_es_de_contrato, a.fecha_bruta IS NOT NULL AND a.fecha_adjudicacion IS NULL AS fecha_sucia,
           a.importe_fila, a.importe_repartido, a.importe_fila_con_iva, a.importe_compartido, a.adjudicatarios, a.ofertas, a.pyme, a.persona_fisica,
           a.importe_sospechoso, a.contrato, a.expediente_ref,
           g.organo_key IS NOT NULL AS en_grupo_fraccionamiento, g.n_menores_grupo, g.importe_grupo
    FROM (SELECT a.*, s.expediente AS expediente_ref FROM src_adj a JOIN src_lic s USING (id)) a
    JOIN src_lic s USING (id)
    LEFT JOIN g ON g.organo_key = s.organo_key AND g.empresa_key = a.empresa_key AND g.tipo_key = s.tipo_key
               AND g.anio = year(a.fecha_adjudicacion)""")

    # ---------- Escritura ----------
    tablas = ["dim_fecha", "dim_organo", "dim_empresa", "dim_cpv", "dim_territorio", "dim_tipo", "dim_procedimiento",
              "dim_estado", "dim_resultado", "dim_feed", "hecho_licitacion", "hecho_lote", "hecho_adjudicacion"]
    for t in tablas:
        con.execute(f"COPY {t} TO '{SALIDA / (t + '.parquet')}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f"  {t:22s} {n:>9,d} filas  {os.path.getsize(SALIDA / (t + '.parquet')) / 1e6:6.2f} MB")

    # ---------- Cuadres ----------
    print("\nCuadres")
    ok = True

    def check(nombre, a, b, tol=0.5):
        nonlocal ok
        bien = abs((a or 0) - (b or 0)) <= tol
        ok &= bien
        print(f"  [{'OK' if bien else 'FALLA'}] {nombre}: {a:,.2f} frente a {b:,.2f}")

    q = lambda s: con.execute(s).fetchone()[0]  # noqa: E731
    # 1. Filas del hecho de adjudicación = filas de adjudicaciones_ultimo
    check("filas hecho_adjudicacion = adjudicaciones_ultimo", q("SELECT count(*) FROM hecho_adjudicacion"),
          q("SELECT count(*) FROM adjudicaciones_ultimo"), 0)
    # 2. Filas de hecho_licitacion = placsp_ultimo, y lotes = distintos (id, lote)
    check("filas hecho_licitacion = placsp_ultimo", q("SELECT count(*) FROM hecho_licitacion"), q("SELECT count(*) FROM placsp_ultimo"), 0)
    check("filas hecho_lote = lotes distintos en la fuente", q("SELECT count(*) FROM hecho_lote"),
          q("SELECT count(*) FROM (SELECT DISTINCT id, coalesce(lote, '') FROM adjudicaciones_ultimo)"), 0)
    # 3. Importe repartido = fuente tras repartir (importe / adjudicatarios con importe si compartido)
    fuente_reparto = q("""SELECT sum(CASE WHEN importe_compartido THEN importe_sin_iva / con_importe ELSE importe_sin_iva END)
                          FROM (SELECT *, count(importe_sin_iva) OVER (PARTITION BY id, lote) AS con_importe FROM adjudicaciones_ultimo)""")
    fuente_reparto_guia = q("SELECT sum(CASE WHEN importe_compartido THEN importe_sin_iva / adjudicatarios ELSE importe_sin_iva END) FROM adjudicaciones_ultimo")
    fuente_bruta = q("SELECT sum(importe_sin_iva) FROM adjudicaciones_ultimo")
    check("sum(importe_repartido) hecho_adjudicacion = fuente repartida", q("SELECT sum(importe_repartido) FROM hecho_adjudicacion"), fuente_reparto)
    print(f"  (info) la fórmula de guides/almacen.md (importe / adjudicatarios) da {fuente_reparto_guia:,.2f}: "
          f"{fuente_reparto - fuente_reparto_guia:,.2f} € menos por lotes compartidos con algún importe nulo")
    # 4. El importe contado una vez por lote cuadra con el repartido y con 'cada lote una vez' en la fuente
    fuente_por_lote = q("""SELECT sum(x) FROM (SELECT CASE WHEN bool_or(importe_compartido) THEN max(importe_sin_iva) ELSE sum(importe_sin_iva) END AS x
                           FROM adjudicaciones_ultimo GROUP BY id, coalesce(lote, ''))""")
    check("sum(importe_lote) hecho_lote = fuente contando cada lote una vez", q("SELECT sum(importe_lote) FROM hecho_lote"), fuente_por_lote, 5)
    check("sum(importe_lote) hecho_lote = sum(importe_repartido) hecho_adjudicacion", q("SELECT sum(importe_lote) FROM hecho_lote"),
          q("SELECT sum(importe_repartido) FROM hecho_adjudicacion"), 5)
    check("sum(importe_adjudicado) hecho_licitacion = sum(importe_lote) hecho_lote", q("SELECT sum(importe_adjudicado) FROM hecho_licitacion"),
          q("SELECT sum(importe_lote) FROM hecho_lote"), 5)
    print(f"  (info) suma bruta por fila en la fuente: {fuente_bruta / 1e6:,.1f} M€; tras reparto: {fuente_reparto / 1e6:,.1f} M€ "
          f"(los acuerdos marco inflaban {(fuente_bruta - fuente_reparto) / 1e6:,.1f} M€)")
    # 5. Integridad de claves foráneas
    for hecho, col, dim in [("hecho_adjudicacion", "empresa_key", "dim_empresa"), ("hecho_adjudicacion", "organo_key", "dim_organo"),
                            ("hecho_licitacion", "organo_key", "dim_organo"), ("hecho_licitacion", "cpv_key", "dim_cpv"),
                            ("hecho_licitacion", "nuts_key", "dim_territorio"), ("hecho_licitacion", "tipo_key", "dim_tipo"),
                            ("hecho_licitacion", "procedimiento_key", "dim_procedimiento"), ("hecho_licitacion", "estado_key", "dim_estado"),
                            ("hecho_adjudicacion", "resultado_key", "dim_resultado"), ("hecho_adjudicacion", "fecha_adjudicacion_key", "dim_fecha"),
                            ("hecho_licitacion", "fecha_publicacion_key", "dim_fecha"), ("hecho_licitacion", "plazo_key", "dim_fecha")]:
        huerfanas = q(f"SELECT count(*) FROM {hecho} h LEFT JOIN {dim} d ON h.{col} IS NOT DISTINCT FROM d.{dim.replace('dim_', '') + '_key' if dim != 'dim_territorio' else 'nuts_key'} WHERE d.{dim.replace('dim_', '') + '_key' if dim != 'dim_territorio' else 'nuts_key'} IS NULL AND h.{col} IS NOT NULL")
        check(f"claves huérfanas {hecho}.{col} -> {dim}", huerfanas, 0, 0)
    # 6. Nada de doble conteo: cada (id, lote, n) aparece una vez
    check("duplicados (id, lote, n) en hecho_adjudicacion", q("SELECT count(*) - count(DISTINCT (id, lote, n)) FROM hecho_adjudicacion"), 0, 0)
    # 7. Fechas sucias apartadas
    print(f"  (info) fechas de adjudicación fuera de [{FECHA_MIN}, {FECHA_MAX}] apartadas: {q('SELECT count(*) FROM hecho_adjudicacion WHERE fecha_sucia')}; "
          f"plazos sucios: {q('SELECT count(*) FROM hecho_licitacion WHERE plazo_sucio')}; publicaciones sucias: {q('SELECT count(*) FROM hecho_licitacion WHERE fecha_publicacion_sucia')}")
    print(f"  (info) adjudicaciones a persona física: {q('SELECT count(*) FROM hecho_adjudicacion WHERE persona_fisica'):,d}; "
          f"sin NIF y no persona física: {q(chr(39).join(['SELECT count(*) FROM hecho_adjudicacion WHERE empresa_key = ', 'SIN_NIF', '']))}")
    print(f"  (info) importes sospechosos (coma perdida, > 10 × presupuesto): {q('SELECT count(*) FROM hecho_adjudicacion WHERE importe_sospechoso')} filas, "
          f"{q('SELECT sum(importe_repartido) FROM hecho_adjudicacion WHERE importe_sospechoso') / 1e6:,.1f} M€ que el dashboard excluye")
    print(f"  (info) licitaciones en grupo con indicio de fraccionamiento: {q('SELECT count(DISTINCT id) FROM hecho_adjudicacion WHERE en_grupo_fraccionamiento'):,d}; "
          f"menores cerca del umbral: {q('SELECT count(*) FROM hecho_licitacion WHERE menor_cerca_umbral'):,d}")
    print("\nRESULTADO:", "todo cuadra" if ok else "HAY DIFERENCIAS")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
