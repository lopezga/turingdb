/* Add graph/table views without changing the measured comparison request. */
const baseRenderEngine = renderEngine;
renderEngine = function(name, result) {
  const card=baseRenderEngine(name,result);
  if(result.error)return card;
  const dataset=active,state=states[dataset],graph=state.graphs?.[name];
  const table=card.querySelector('.table-wrap')||node('p','La consulta no devolvió filas.','empty');
  if(!table.parentNode)card.append(table);
  const switcher=node('div',undefined,'result-switch'),tableButton=node('button','Tabla'),graphButton=node('button','Grafo');
  tableButton.type=graphButton.type='button';tableButton.setAttribute('aria-label','Ver tabla de '+name);graphButton.setAttribute('aria-label','Ver grafo de '+name);
  switcher.append(tableButton,graphButton);card.insertBefore(switcher,table);
  const pane=node('section',undefined,'graph-host');pane.setAttribute('aria-label','Visualización de '+name);card.append(pane);
  function paintGraph(){pane.replaceChildren();
    if(graph?.error){pane.append(node('p',graph.error,'graph-load-error'));const retry=node('button','Reintentar carga','secondary');retry.type='button';retry.disabled=busy;retry.onclick=()=>refreshGraph(dataset,name,'result');pane.append(retry);return;}
    if(!graph||graph.loading){pane.append(node('p','Cargando el grafo fuera de la medición…','graph-loading'));return;}
    window.GraphScopeGraph.mount(pane,graph,{onExpand:id=>refreshGraph(dataset,name,'expand',id)});
    if(state.graphErrors?.[name])pane.append(node('p',state.graphErrors[name],'graph-load-error'));
    if(graph.scope==='exploration'){const reset=node('button','Volver al resultado original','secondary');reset.type='button';reset.disabled=busy;reset.onclick=()=>refreshGraph(dataset,name,'reset');pane.prepend(reset);}
  }
  function select(view){state.resultViews??={};state.resultViews[name]=view;table.hidden=view!=='table';pane.hidden=view!=='graph';tableButton.setAttribute('aria-pressed',String(view==='table'));graphButton.setAttribute('aria-pressed',String(view==='graph'));if(view==='graph')paintGraph();}
  tableButton.onclick=()=>select('table');graphButton.onclick=()=>select('graph');
  select(state.resultViews?.[name]||(graph?.available?'graph':'table'));
  return card;
};

async function graphRequest(comparisonId,engine,action,nodeId='') {
  const response=await fetch('/api/visualize',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({comparison_id:comparisonId,engine,action,node_id:nodeId})});
  const data=await response.json();
  if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));
  return data;
}

async function refreshGraph(dataset,engine,action,nodeId='') {
  if(busy)return;
  const state=states[dataset],id=state.report?.comparison_id;
  if(!id)return;
  busy=true;$('submit').disabled=true;state.graphErrors??={};state.graphErrors[engine]=null;
  try{const data=await graphRequest(id,engine,action,nodeId);if(state.report?.comparison_id===id){state.graphs??={};state.graphs[engine]=data;state.resultViews??={};state.resultViews[engine]='graph';}}
  catch(error){state.graphErrors[engine]=error.message;if(!state.graphs?.[engine]||state.graphs[engine].error){state.graphs??={};state.graphs[engine]={error:error.message};}}
  finally{busy=false;if(active!=='about')renderReport();}
}

const measuredSubmit=$('ask').onsubmit;
$('ask').onsubmit=async event=>{
  if(busy){event.preventDefault();return;}
  const dataset=active,state=states[dataset];state.graphs={};state.resultViews={};state.graphErrors={};
  await measuredSubmit(event);
  const report=state.report;
  if(!report?.comparison_id)return;
  busy=true;$('submit').disabled=true;
  for(const [engine,value]of Object.entries(report.engines))if(!value.error)state.graphs[engine]={loading:true};
  if(active===dataset)renderReport();
  try{
    // Sequential reads share the server's measurement lock. Never fetch with Promise.all.
    for(const [engine,value]of Object.entries(report.engines)){
      if(value.error)continue;
      try{state.graphs[engine]=await graphRequest(report.comparison_id,engine,'result');}
      catch(error){state.graphs[engine]={error:error.message};}
    }
  }finally{busy=false;if(active!=='about')renderReport();}
};

$('download').onclick=()=>{
  if(active==='about'||!states[active].report)return;
  const state=states[active],payload={...state.report,visualizations:state.graphs||{}};
  const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));
  const link=node('a');link.href=url;link.download='graphscope-'+active+'-'+Date.now()+'.json';link.click();URL.revokeObjectURL(url);
};
