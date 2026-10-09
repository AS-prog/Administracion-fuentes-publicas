import sys, json; sys.path.insert(0,'.')
from scripts.clientes.almacen import conectar
con=conectar()
def rows(s):
    r=con.execute(s); c=[x[0] for x in r.description]; return [dict(zip(c,v)) for v in r.fetchall()]
con.execute("""create temp view base as
select a.feed,a.id,a.lote,a.nif,a.nombre,a.pyme,a.persona_fisica,a.ofertas,
 coalesce(a.fecha_adjudicacion,a.fecha_contrato) f,
 case when a.importe_compartido then a.importe_sin_iva/a.adjudicatarios else a.importe_sin_iva end imp,
 p.organo,p.tipo,p.procedimiento,substr(p.nuts,1,4) nuts
from adjudicaciones_ultimo a left join placsp_ultimo p on p.id=a.id and p.feed=a.feed
where coalesce(a.fecha_adjudicacion,a.fecha_contrato) between '2026-09-01' and '2026-09-30' and a.resultado in ('8','9')""")
out={}
out['kpi']=rows("""select count(*) adjudicaciones, count(distinct feed||id) expedientes, sum(imp) importe, median(imp) mediana,
 avg(pyme::int) pct_pyme, count(distinct nif) empresas, sum(persona_fisica::int) pf from base""")[0]
out['dia']=rows("select f::varchar d, feed, count(*) n, sum(imp) imp from base group by 1,2 order by 1")
out['empresas']=rows("""select nif, any_value(nombre) nombre, count(*) n, sum(imp) imp from base
 where nif is not null and not coalesce(persona_fisica,false) group by nif order by imp desc nulls last limit 15""")
out['top10_share']=rows("""with t as (select nif,sum(imp) i from base where nif is not null group by 1 order by 2 desc limit 10)
 select (select sum(i) from t)/(select sum(imp) from base) s""")[0]['s']
out['organos']=rows("select organo, count(*) n, sum(imp) imp from base where organo is not null group by 1 order by imp desc nulls last limit 12")
out['tipo']=rows("select tipo, count(*) n, sum(imp) imp from base group by 1 order by imp desc nulls last")
out['proc']=rows("select procedimiento p, count(*) n, sum(imp) imp from base group by 1 order by n desc")
out['nuts']=rows("select nuts, count(*) n, sum(imp) imp from base group by 1 order by imp desc nulls last")
out['ofertas']=rows("""select case when ofertas is null then 'sd' when ofertas<=1 then '1' when ofertas=2 then '2' when ofertas=3 then '3' when ofertas<=5 then '4-5' else '6+' end b, count(*) n
 from base where feed<>'1143' group by 1""")
out['feed']=rows("select feed, count(*) n, sum(imp) imp from base group by 1")
json.dump(out,open('dashboards/contratacion-publica/datos-septiembre.json','w'),ensure_ascii=False,default=str)
print(json.dumps({k:out[k] for k in ['kpi','top10_share','feed','tipo','proc','ofertas']},ensure_ascii=False,default=str,indent=0))
print(out['organos'][:4]); print(out['nuts'][:6])
