# Dashboard de contratación pública (PLACSP)

Criterio: cada visual responde a una pregunta de los cuatro perfiles; lo demás se descarta. Las consultas están en `consultas.sql` con el mismo código (Px.y).

## Filtros globales

Feed (los tres separados, nunca sumados sin verlo), año y mes de adjudicación, tipo, procedimiento, CCAA/provincia, división CPV. Interruptores fijos: *excluir importes sospechosos* y *excluir personas físicas* en rankings (ambos activos).

## Cabecera (P0.1)

Tarjetas por feed: licitaciones, lotes adjudicados, importe repartido. Sin ellas un total mezcla menores con grandes obras.

## Página 1. Empresa licitadora

| visual | pregunta | medida |
|---|---|---|
| P1.1 tabla CPV × tipo | ¿qué está abierto en mi sector? | licitaciones abiertas, presupuesto total y mediano |
| P1.2 barras por semana | ¿cuándo vence? | licitaciones abiertas por semana de plazo |
| P1.3 histograma de ofertas por lote | ¿cuántos competidores tendré? | lotes por nº de ofertas, mediana |
| P1.4 barras por CPV × tipo | ¿cuánto hay que bajar? | baja media y mediana, solo `ratio_fiable` |
| P1.5 tabla por órgano, selector de empresa | ¿qué gana mi competidor y con quién? | adjudicaciones, importe repartido, ofertas medias |

## Página 2. Periodista

| visual | pregunta | medida |
|---|---|---|
| P2.1 ranking de adjudicatarios | ¿quién se lleva más dinero? | importe repartido, órganos, % una oferta, formato del NIF |
| P2.2 histograma por tramos de 1.000 € con línea de umbral | ¿se amontonan los menores bajo el umbral? | menores por tramo, paneles 15.000 y 40.000 |
| P2.3 tabla órgano + adjudicatario + tipo + año | ¿indicios de fraccionamiento? | nº menores, suma, veces el umbral |
| P2.4 tabla por órgano | ¿quién usa el negociado sin publicidad? | lotes, % una oferta, importe |

## Página 3. Regulador

| visual | pregunta | medida |
|---|---|---|
| P3.1 barras por procedimiento | ¿cuánta competencia hay? | % lotes con una oferta |
| P3.2 barras feed × tipo | ¿difieren las fuentes? | % una oferta |
| P3.3 barras por división CPV | ¿en qué sectores falta competencia? | % una oferta (mín. 200 lotes) |
| P3.4 tabla por órgano | ¿qué órganos adjudican a una oferta? | % una oferta, lotes, importe (mín. 50) |
| P3.5 cajas por procedimiento | ¿plazos razonables? | mediana, p10, p90 de días publicación → plazo |
| P3.6 tabla tipo × CPV | ¿dónde quedan desiertos? | % lotes desiertos |
| P3.7 barras feed × tipo, aviso "1044 sin dato" | ¿cuota pyme? | % adjudicaciones y % importe a pyme |

## Página 4. Analista

| visual | pregunta | medida |
|---|---|---|
| P4.1 líneas trimestre × procedimiento | ¿cuánto tarda la adjudicación? | mediana de días plazo → adjudicación |
| P4.2 Pareto de órganos | ¿cuánto concentran pocos órganos? | importe y % acumulado |
| P4.3 mapa CCAA, desglose provincia | ¿dónde se adjudica? | importe y %, con fila "Toda España" |
| P4.4 serie mensual por feed | ¿cómo evoluciona el volumen? | lotes e importe por mes |
| P4.5 tabla de calidad | ¿qué no se puede leer? | % sin DIR3, CPV, fecha; fechas imposibles |

## Descartado

Importe total sin separar feeds; importe con IVA y valor estimado (nadie los pregunta); ranking por nº de contratos (P2.1 ya lo trae); % una oferta por tipo sin feed (P3.2); mapa de abiertas (P1.1 con filtro basta); serie de publicaciones (el corte es de `updated`); estado como visual (solo filtro); tiempo de adjudicación de menores (sin plazo); pyme del 1044 (sin dato).

## Wireframe

```
+-------------------------------------------------------------------------+
| [feed] [año/mes adj] [tipo] [procedimiento] [CCAA] [CPV]                 |
| [x] sin importes sospechosos  [x] sin personas físicas                   |
+-------------------------------------------------------------------------+
| P0.1  Menores 46.553 | 215 M€   643 42.206 | 17.130 M€   1044 17.101 | 12.081 M€ |
+----------------+----------------+----------------+-----------------------+
| Licitador      | Periodista     | Regulador      | Analista              |
+----------------+----------------+----------------+-----------------------+
| P1  [P1.1 abiertas CPV×tipo      ] [P1.2 vencimientos/semana            ] |
|     [P1.3 ofertas] [P1.4 baja por CPV×tipo   ] [P1.5 competidor→órganos] |
| P2  [P2.1 top adjudicatarios     ] [P2.2 tramos | umbral 15k | 40k      ] |
|     [P2.3 fraccionamiento (tabla)         ] [P2.4 negociado sin publ.  ] |
| P3  [P3.1 %1 oferta/proc] [P3.2 feed×tipo] [P3.3 por CPV]               |
|     [P3.4 órganos] [P3.5 plazos] [P3.6 desiertos] [P3.7 pyme (aviso)]    |
| P4  [P4.1 días adjudicar] [P4.2 Pareto órganos] [P4.3 mapa CCAA]         |
|     [P4.4 serie mensual/feed] [P4.5 calidad del dato]                    |
+-------------------------------------------------------------------------+
```
