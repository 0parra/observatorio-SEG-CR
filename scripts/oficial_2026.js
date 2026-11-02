/* Módulo de publicación de exportaciones oficiales estructuradas 2026.
   Solo utiliza data/series_sugese.json procesado por ingestión y validación.
   Nunca mezcla unidades, agregaciones ni tipo de serie. */
"use strict";
window.renderOfficial2026=function(payload,api){
  const {$,fmt,esc,card}=api;
  const data=payload.series||[];
  const meta=payload.meta||{};
  const allowed=["conciliado_con_totales","validado_estructuralmente_sin_conciliacion_externa"];
  if(!allowed.includes(meta.estado)||!data.length)return false;
  const isMarket=x=>["mercado","total","total mercado"].includes(String(x.aseguradora||"").trim().toLowerCase());
  const isAll=x=>["todos","total","mercado","general"].includes(String(x.ramo||"").trim().toLowerCase());
  const same=(x,m,kind,period)=>x.indicador===m&&x.tipo_serie===kind&&x.periodo===period&&isAll(x);
  const marketRows=data.filter(x=>isMarket(x)&&isAll(x)&&x.unidad==="millones CRC");
  const seriesTypes=["acumulado_anual","12m_movil","mensual","trimestral"];
  const kind=seriesTypes.find(k=>marketRows.some(r=>r.tipo_serie===k));
  if(!kind){$("cards").innerHTML='<div class="notice">La exportación 2026 contiene datos por aseguradora pero no un total Mercado/Todos, por lo que no se pueden publicar importes consolidados de forma verificada.</div>';return true;}
  const periods=[...new Set(marketRows.filter(r=>r.tipo_serie===kind).map(x=>x.periodo))].sort();
  const last=periods.at(-1);
  const amount=m=>marketRows.find(x=>same(x,m,kind,last));
  const p=amount("primas_emitidas"),s=amount("siniestros_pagados");
  const prevPeriod=periods.filter(x=>x<last).at(-1);
  const prev=m=>marketRows.find(x=>same(x,m,kind,prevPeriod));
  const fmtMM=v=>"₡"+fmt(v/1000,2)+" mil millones";
  const labelKind={mensual:"valor del mes",acumulado_anual:"acumulado del año", "12m_movil":"doce meses móviles",trimestral:"trimestre"}[kind]||kind;
  const change=(v,b)=>v&&b&&b.valor!==0?100*(v.valor-b.valor)/Math.abs(b.valor):null;
  const chP=change(p,prev("primas_emitidas")),chS=change(s,prev("siniestros_pagados"));
  const msgRate=(v,base,rate)=>rate===null?"Sin periodo anterior comparable":(rate>=0?"+":"")+fmt(rate,2)+"% entre cortes "+base+" y "+last+" ("+labelKind+")";
  $("cards").innerHTML=[
    card("Primas · "+labelKind,p?fmtMM(p.valor):"Sin dato",p?("Fuente SUGESE importada · corte "+last):"Falta agregado oficial"),
    card("Siniestros · "+labelKind,s?fmtMM(s.valor):"Sin dato",s?("Fuente SUGESE importada · corte "+last):"Falta agregado oficial"),
    card("Variación de primas",chP===null?"Sin comparación":(chP>=0?"+":"")+fmt(chP,2)+"%",msgRate(p,prevPeriod||"—",chP)),
    card("Control de información",meta.estado==="conciliado_con_totales"?"Conciliado":"Validado","Periodo "+last+" · "+data.length+" observaciones")
  ].join("");
  const insurer=data.filter(x=>!isMarket(x)&&same(x,"primas_emitidas",kind,last));
  insurer.sort((a,b)=>b.valor-a.valor);
  if(p&&p.valor>0&&insurer.length){
    $("share-title").textContent="Participación de primas por aseguradora";
    $("share").innerHTML=insurer.map(x=>{
      const pct=100*x.valor/p.valor;
      return '<div class="barrow"><span class="barlabel" title="'+esc(x.aseguradora)+'">'+esc(x.aseguradora)+'</span><div class="bartrack"><div class="barfill" style="width:'+Math.min(100,Math.max(0,pct/70*100))+'%"></div></div><span class="num">'+fmt(pct,2)+'%</span></div>'
    }).join("");
    $("share-explain").innerHTML='<strong>Interpretación calculada:</strong> '+esc(insurer[0].aseguradora)+' lidera en primas del corte '+esc(last)+', con '+fmt(100*insurer[0].valor/p.valor,2)+'% del mercado. Esta cuota depende de que los importes del reporte correspondan a entidades y periodos comparables. '+(meta.estado==="conciliado_con_totales"?"Suma reconciliada contra el total suministrado.":"Suma por entidades aún sin conciliación contra total de mercado.");
  }else if(p&&p.valor>0){
    const branch=data.filter(x=>isMarket(x)&&!isAll(x)&&x.indicador==="primas_emitidas"&&x.tipo_serie===kind&&x.periodo===last&&x.unidad==="millones CRC").sort((a,b)=>b.valor-a.valor);
    if(branch.length){
      $("share-title").textContent="Composición de primas 2026 por ramo";
      $("share").innerHTML=branch.map(x=>{const pct=100*x.valor/p.valor;return '<div class="barrow"><span class="barlabel" title="'+esc(x.ramo)+'">'+esc(x.ramo)+'</span><div class="bartrack"><div class="barfill" style="width:'+Math.min(100,Math.max(0,pct/35*100))+'%"></div></div><span class="num">'+fmt(pct,2)+'%</span></div>'}).join("");
      const py=String(Number(last.slice(0,4))-1)+last.slice(4);
      const changes=branch.map(x=>{const prev=data.find(y=>isMarket(y)&&y.ramo===x.ramo&&y.indicador==="primas_emitidas"&&y.tipo_serie===kind&&y.periodo===py);return prev?{ramo:x.ramo,diferencia:x.valor-prev.valor,variacion:prev.valor?100*(x.valor-prev.valor)/Math.abs(prev.valor):null}:null}).filter(Boolean).sort((a,b)=>b.diferencia-a.diferencia);
      $("share-explain").innerHTML='<strong>Interpretación por ramo:</strong> '+esc(branch[0].ramo)+' representa '+fmt(100*branch[0].valor/p.valor,2)+'% del primaje acumulado del corte '+esc(last)+'. '+(changes.length?'El mayor aumento absoluto respecto a '+esc(py)+' se observa en '+esc(changes[0].ramo)+' (₡'+fmt(changes[0].diferencia/1000,2)+' mil millones).':'Aún no hay comparación por ramo con igual periodo del año anterior.')+' Son datos oficiales del cuadro público de SUGESE.';
    }else{
      $("share").innerHTML='<div class="notice">La exportación requiere datos desagregados por aseguradora o ramo para calcular participaciones.</div>';
      $("share-explain").innerHTML="No existen desgloses homologados para este corte.";
    }
  }else{
    $("share").innerHTML='<div class="notice">Para participación por aseguradora se requiere la exportación con desglose por entidad y total Mercado del mismo periodo y tipo de serie.</div>';
    $("share-explain").innerHTML='No se atribuyen participaciones a 2026 si falta el detalle de aseguradoras.';
  }
  const primes=marketRows.filter(x=>x.indicador==="primas_emitidas"&&x.tipo_serie===kind).sort((a,b)=>a.periodo.localeCompare(b.periodo));
  const claims=marketRows.filter(x=>x.indicador==="siniestros_pagados"&&x.tipo_serie===kind);
  const cmap=new Map(claims.map(r=>[r.periodo,r]));
  const maxi=Math.max(1,...primes.map(r=>r.valor),...claims.map(r=>r.valor));
  $("comparativo").innerHTML=primes.length?primes.slice(-12).map(r=>'<div style="margin-bottom:11px"><strong>'+esc(r.periodo)+'</strong><div class="barrow"><span>Primas</span><div class="bartrack"><div class="barfill" style="width:'+(r.valor/maxi*100)+'%"></div></div><span class="num">'+fmt(r.valor/1000,1)+'</span></div>'+ (cmap.has(r.periodo)?'<div class="barrow"><span>Siniestros</span><div class="bartrack"><div class="barfill alt" style="width:'+(cmap.get(r.periodo).valor/maxi*100)+'%"></div></div><span class="num">'+fmt(cmap.get(r.periodo).valor/1000,1)+'</span></div>':'')+'</div>').join(""):'<p>No se importó una serie temporal de primas con agregados de mercado.</p>';
  $("trend-explain").innerHTML='<strong>Interpretación calculada:</strong> '+(chP===null?"No existen dos cortes de primas comparables para calcular variación.":'Primas '+msgRate(p,prevPeriod,chP)+'.')+' '+(chS===null?"Sin comparación completa de siniestros.":'Siniestros '+msgRate(s,prevPeriod,chS)+'.')+' No se compara acumulado anual con dato mensual ni se infiere índice técnico de siniestralidad.';
  $("results").innerHTML='<tr><td colspan="4">Resultados contables 2026 no incluidos en esta exportación; se requiere informe financiero separado.</td></tr>';
  $("results-explain").innerHTML='No se interpreta rentabilidad sin resultados técnicos o contables comparables.';
  $("download").disabled=true;
  $("notes").innerHTML='<div class="notice"><strong>Estado de calidad: '+esc(meta.estado)+'</strong><div>'+esc(meta.nivel||"")+" · "+esc(meta.origen||"")+'</div></div><div class="notice"><strong>Fuente y corte</strong><div>Periodo '+esc(last)+' · '+esc(labelKind)+'. <a target="_blank" rel="noopener noreferrer" href="'+esc((p||s)?.fuente_url||"https://www.sugese.fi.cr/cr/es/estadisticas.html")+'">Consultar fuente oficial</a></div></div>';
  $("live-period-note").textContent="Observaciones oficiales importadas hasta "+last+" ("+labelKind+"). Actualización de datos validada estructuralmente en GitHub; no equivale a sincronización automática con Power BI.";
  const select=$("year");if(select.options[0].value==="2026")select.options[0].textContent="2026 · "+last+" ("+labelKind+")";
  return true;
};