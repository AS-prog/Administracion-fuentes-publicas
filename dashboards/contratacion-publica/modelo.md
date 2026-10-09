# Modelo dimensional de contratación pública (PLACSP)

Fuente: almacén local de septiembre de 2026 (`placsp_ultimo`, 105.880 expedientes; `adjudicaciones_ultimo`, 108.253 filas), feeds 643 (perfiles alojados), 1044 (agregadas) y 1143 (menores). Lo construye `build_modelo.py` en Parquet.

## Estrella: tres hechos con dimensiones conformadas

La fuente tiene tres granos y ninguno sirve para todas las preguntas:

| hecho | una fila por | filas | para qué |
|---|---|---|---|
| `hecho_licitacion` | expediente (`id`) | 105.880 | presupuesto, plazos, estado, baja, umbral de menores |
| `hecho_lote` | expediente + lote | 99.457 | ofertas, desiertos, % una oferta, importe del lote contado una vez |
| `hecho_adjudicacion` | expediente + lote + adjudicatario (`n`) | 108.253 | quién cobra, con qué órgano, pyme, fraccionamiento |

**Por qué no una sola a lote-adjudicatario**: el presupuesto, la publicación y el plazo son del expediente (no hay presupuesto por lote); las ofertas y el resultado son del lote y se repiten en cada adjudicatario (contarlos ahí sesga el % de una oferta hacia los acuerdos marco); y en los acuerdos marco el importe se repite en cada adjudicatario.

**Cómo no duplicar importes**: `importe_repartido = importe_fila / adjudicatarios_con_importe` cuando `importe_compartido` (varios adjudicatarios con el mismo importe en el lote), y `importe_fila` si no. Es la única medida de importe que se suma; `hecho_lote.importe_lote` y `hecho_licitacion.importe_adjudicado` son sus agregados y las tres sumas cuadran (31.416,7 M€, frente a 58.622 M€ sumando filas). Matiz sobre `guides/almacen.md`: dividir entre `adjudicatarios` pierde 459.746 € en 13 lotes con algún importe nulo; se divide entre los que traen importe.

## Medidas

Aditivas: `importe_repartido`, `importe_lote`, `importe_adjudicado`, `presupuesto_sin_iva`, recuentos y banderas (`una_oferta`, `desierto`, `adjudicado`, `pyme`, `persona_fisica`, `menor_cerca_umbral`, `en_grupo_fraccionamiento`, `importe_sospechoso`).

No aditivas (mediana, percentil o media, nunca suma): `ofertas` (del lote), `ratio_adjudicado_presupuesto` (solo con `ratio_fiable`: un lote, adjudicado, ratio entre 0,1 y 1,05), `dias_plazo` (publicación → plazo), `dias_hasta_adjudicacion` (plazo → adjudicación). Los porcentajes son cocientes de recuentos en la consulta.

## Dimensiones

| dimensión | clave | atributos | nulos y sucios |
|---|---|---|---|
| `dim_fecha` (rol: publicación, plazo, adjudicación) | `fecha_key` | año, trimestre, mes, año-mes, día de semana | fila `desconocido`; fechas fuera de 2015..2027 pasan a NULL con bandera: 13 adjudicaciones (años 0203, 0206), 164 plazos (2029-2080), 2 publicaciones (año 1) |
| `dim_organo` | coalesce(DIR3, NIF, ID_PLATAFORMA) | nombre (moda), variantes, tipo de identificador, NUTS frecuente, feeds | el 1044 solo trae ID_PLATAFORMA (80,6 % sin DIR3): un órgano puede partirse en dos claves; 7.176 claves por 8.865 nombres |
| `dim_empresa` | NIF en mayúsculas | nombre (moda), `formato_identificador` (NIF español, DNI/NIE, extranjero, inválido, sin identificador), pyme alguna vez | personas físicas → clave `PERSONA_FISICA` (14.395 filas); sin NIF y no física → `SIN_NIF` (5.402, casi todas desiertos); NIF de relleno (A00000000) e inválidos se etiquetan, no se corrigen |
| `dim_cpv` | primer CPV del expediente | división etiquetada, grupo, clase, `sin_cpv` | 47,8 % de menores sin CPV → `?`; los demás CPV del expediente (hasta 157) se descartan: sin tabla puente en v1 |
| `dim_territorio` | `nuts_key` | provincia (nuts3), CCAA (nuts2), nivel | `ES` sin desglose (9,8 % del importe); 20 fuera de España; 109 sin NUTS |
| `dim_tipo`, `dim_procedimiento`, `dim_estado`, `dim_resultado`, `dim_feed` | código del feed | etiqueta; `desierto/adjudicado`; `trae_pyme`, `trae_fecha_adjudicacion` | códigos fuera del enunciado llevan `(*)` (de memoria, sin verificar) |

Otros sucios: presupuesto ≤ 0 pasa a NULL; `importe_sospechoso` marca adjudicaciones mayores que 10 veces el presupuesto (20 filas, 1.991 M€; una galería de arte con 1.954 M€ sobre 22.000 €): el cuadre las incluye y el dashboard las excluye; el 1044 usa `fecha_contrato` (bandera `fecha_es_de_contrato`) y sus desiertos y 4.742 adjudicados no tienen fecha; `placsp_ultimo` arrastra versiones desde 2021, así que todo visual temporal filtra por fecha de adjudicación o publicación, no por `updated`.

## Pregunta → medida → dimensiones → trampa

| pregunta | hecho y medida | dimensiones | trampa tratada |
|---|---|---|---|
| Licitaciones abiertas | `hecho_licitacion` recuento y presupuesto; PUB/PRE, plazo ≥ hoy | CPV, tipo, fecha de plazo | anuladas fuera; plazos 2029-2080 a NULL |
| Competidores | `hecho_lote.ofertas` (histograma, mediana) | procedimiento, CPV | por lote, no por adjudicatario |
| Baja media | `ratio_adjudicado_presupuesto` con `ratio_fiable` | CPV, tipo | solo un lote; coma perdida fuera |
| Qué gana un competidor | `importe_repartido`, recuento | empresa, órgano, fecha | reparto en acuerdos marco |
| Quién se lleva más dinero | `importe_repartido` | empresa | sin físicas, `SIN_NIF` ni sospechosos |
| Menores cerca del umbral | `tramo_1000`, `menor_cerca_umbral` | tipo | obras 40.000, resto 15.000 |
| Fraccionamiento | `en_grupo_fraccionamiento` (órgano + NIF + tipo + año, ≥ 2 menores, suma > umbral) | órgano, empresa | físicas fuera (sin NIF) |
| Negociado sin publicidad | `hecho_lote.una_oferta`, procedimiento 3 | órgano | por lote |
| % una oferta | `una_oferta / ofertas no nulas` | órgano, procedimiento, CPV, feed | feeds separados |
| Plazos | `dias_plazo` | procedimiento | 141 plazos anteriores a la publicación se muestran |
| Desiertos | `hecho_lote.desierto` | tipo, CPV | desiertos del 1044 sin fecha |
| Cuota pyme | `pyme` | tipo, feed | solo 643 y 1143 |
| Tiempo de adjudicación | `dias_hasta_adjudicacion` | procedimiento, trimestre | 1044 con fecha de contrato |
| Concentración | `importe_repartido`, Pareto | órgano, territorio | `ES` sin desglose; 1044 sin DIR3 |

## Lo que no se puede responder

- **Cuota pyme del 1044**: el campo no viene.
- **Tiempo de adjudicación de menores**: el 1143 no trae plazo (76,6 % nulo) ni publicación (96,9 %).
- **Baja por lote con varios lotes**: no hay presupuesto por lote; `ratio_fiable` deja fuera unos 4.000 expedientes.
- **Órgano consolidado en el 1044**: sin DIR3 la concentración puede partir un órgano.
- **Serie histórica**: el corte es un mes de `updated`; lo anterior a 2026 son expedientes viejos reeditados.
- **Lo de hoy**: solo en el buscador del portal; el modelo llega al 2026-10-01.
- **Fraccionamiento como prueba**: 790 grupos y 3.818 menores son una lista de revisión, no una conclusión.
