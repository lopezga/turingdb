/* Offline, dependency-free SVG graph viewer. Data always comes from one named engine. */
(() => {
  const NS = 'http://www.w3.org/2000/svg';
  const colors = {Entity:'#377db5', Officer:'#8c66bd', Intermediary:'#b47735', Address:'#667e88', Other:'#af6686', User:'#36816a'};
  let serial = 0;
  function layout(nodes, edges) {
    const points = new Map();
    nodes.forEach((n,i) => {
      const angle = i * Math.PI * 2 / Math.max(1,nodes.length);
      points.set(n.id, {x:350+Math.cos(angle)*190,y:220+Math.sin(angle)*145});
    });
    if(nodes.length===1)points.set(nodes[0].id,{x:350,y:220});
    for(let tick=0;tick<130;tick++) {
      const force = new Map(nodes.map(n=>[n.id,{x:0,y:0}]));
      for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++){
        const a=points.get(nodes[i].id), b=points.get(nodes[j].id);
        const dx=a.x-b.x,dy=a.y-b.y,d2=Math.max(30,dx*dx+dy*dy),strength=7000/(d2*Math.sqrt(d2));
        force.get(nodes[i].id).x+=dx*strength;force.get(nodes[i].id).y+=dy*strength;
        force.get(nodes[j].id).x-=dx*strength;force.get(nodes[j].id).y-=dy*strength;
      }
      edges.forEach(e=>{const a=points.get(e.source),b=points.get(e.target);if(!a||!b||a===b)return;
        const dx=b.x-a.x,dy=b.y-a.y,d=Math.max(1,Math.hypot(dx,dy)),f=(d-(nodes.length<=10?180:95))*.025;
        force.get(e.source).x+=dx/d*f;force.get(e.source).y+=dy/d*f;
        force.get(e.target).x-=dx/d*f;force.get(e.target).y-=dy/d*f;});
      for(const n of nodes){const p=points.get(n.id),f=force.get(n.id);p.x=Math.max(65,Math.min(635,p.x+Math.max(-4,Math.min(4,f.x+(350-p.x)*.006))));p.y=Math.max(40,Math.min(380,p.y+Math.max(-4,Math.min(4,f.y+(220-p.y)*.006))));}
    }
    return points;
  }
  const html=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;};
  const svgEl=(tag,attrs={})=>{const el=document.createElementNS(NS,tag);for(const [key,value]of Object.entries(attrs))el.setAttribute(key,String(value));return el;};
  function mount(host,data,options={}) {
    host.replaceChildren();
    host.append(html('p',data.message,'graph-description'));
    if(data.limited)host.append(html('p','Vista limitada: no se muestran todas las conexiones.','graph-warning'));
    if(!data.available || !data.nodes.length){
      host.append(html('p',data.available?'No hay nodos para mostrar.':'Este resultado agregado se conserva en la tabla.','empty'));
      if(data.anchor){const explore=html('button','Explorar vecindario del nodo '+data.anchor,'secondary');explore.type='button';explore.onclick=()=>options.onExpand?.(data.anchor);host.append(explore);}
      return;
    }
    const id='graph-arrow-'+(++serial), positions=layout(data.nodes,data.edges), nodeMap=new Map(data.nodes.map(n=>[n.id,n]));
    const toolbar=html('div',undefined,'graph-toolbar');
    toolbar.append(html('span',data.nodes.length+' nodos · '+data.edges.length+' relaciones','graph-count'));
    const zoomIn=html('button','+'),zoomOut=html('button','−'),reset=html('button','Ajustar');
    for(const b of [zoomIn,zoomOut,reset]){b.type='button';toolbar.append(b);}
    zoomIn.setAttribute('aria-label','Acercar grafo de '+data.engine);zoomOut.setAttribute('aria-label','Alejar grafo de '+data.engine);
    reset.setAttribute('aria-label','Ajustar grafo de '+data.engine);
    const labels=html('label',undefined,'graph-label-option'),check=html('input');check.type='checkbox';check.checked=true;labels.append(check,document.createTextNode('Etiquetas'));toolbar.append(labels);
    host.append(toolbar);
    const svg=svgEl('svg',{viewBox:'0 0 700 440',role:'group',tabindex:0,'aria-label':'Grafo de '+data.engine+' con '+data.nodes.length+' nodos y '+data.edges.length+' relaciones',class:'network-svg'});
    const defs=svgEl('defs'),marker=svgEl('marker',{id,viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:6,markerHeight:6,orient:'auto-start-reverse'});
    marker.append(svgEl('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#71877e'}));defs.append(marker);svg.append(defs);
    const edgeLayer=svgEl('g'),nodeLayer=svgEl('g');svg.append(edgeLayer,nodeLayer);host.append(svg);
    const legend=html('div',undefined,'graph-legend');
    [...new Set(data.nodes.map(n=>n.kind))].sort().forEach(kind=>{const item=html('span',kind||'Record');const dot=html('i');dot.style.backgroundColor=colors[kind]||'#377db5';item.prepend(dot);legend.append(item);});host.append(legend);
    const inspector=html('section',undefined,'graph-inspector');inspector.setAttribute('aria-label','Detalles del grafo de '+data.engine);inspector.append(html('p','Selecciona un nodo o una relación para ver sus propiedades.','empty'));host.append(inspector);
    host.append(html('p','Arrastra nodos para colocarlos. Arrastra el fondo para desplazar. Usa +/− o Ctrl+rueda para zoom. Enter selecciona el elemento enfocado.','graph-help'));
    let selected=null,view={x:0,y:0,w:700,h:440},drag=null;
    const nodeElements=new Map(),edgeElements=[];
    function fields(properties){const dl=html('dl');for(const [key,value]of Object.entries(properties)){if(value===undefined||value===null||value==='')continue;dl.append(html('dt',key),html('dd',typeof value==='object'?JSON.stringify(value):String(value)));}return dl;}
    function selectNode(n){selected=n.id;inspector.replaceChildren(html('h4',n.label),fields({ID:n.id,...n.properties}));
      if(n.result_values&&Object.keys(n.result_values).length)inspector.append(html('strong','Valores de la consulta'),fields(n.result_values));
      const expand=html('button','Explorar conexiones','secondary');expand.type='button';expand.setAttribute('aria-label','Explorar conexiones del nodo '+n.id+' en '+data.engine);
      expand.onclick=async()=>{expand.disabled=true;expand.textContent='Cargando conexiones…';try{await options.onExpand?.(n.id);}finally{expand.disabled=false;expand.textContent='Explorar conexiones';}};
      inspector.append(expand,html('p','La exploración añade datos reales fuera del resultado original y de la medición.','graph-help'));redraw();}
    function selectEdge(e){selected=null;inspector.replaceChildren(html('h4',e.label),fields({ID:e.id,origen:e.source,destino:e.target,...e.properties}));redraw();}
    function path(e,index){const a=positions.get(e.source),b=positions.get(e.target);if(!a||!b)return '';
      if(e.source===e.target)return 'M '+(a.x+10)+' '+(a.y-10)+' C '+(a.x+60)+' '+(a.y-75)+' '+(a.x-60)+' '+(a.y-75)+' '+(a.x-10)+' '+(a.y-12);
      const dx=b.x-a.x,dy=b.y-a.y,d=Math.max(1,Math.hypot(dx,dy)),ux=dx/d,uy=dy/d;
      const related=data.edges.filter(x=>x.source===e.source&&x.target===e.target),reverse=data.edges.some(x=>x.source===e.target&&x.target===e.source);
      const lane=related.findIndex(x=>x.id===e.id),curve=reverse?20+lane*12:(lane-(related.length-1)/2)*22;
      return 'M '+(a.x+ux*15)+' '+(a.y+uy*15)+' Q '+((a.x+b.x)/2-uy*curve)+' '+((a.y+b.y)/2+ux*curve)+' '+(b.x-ux*20)+' '+(b.y-uy*20);}
    data.edges.forEach((e,index)=>{const group=svgEl('g',{role:'button',tabindex:0,'aria-label':'Relación '+e.label+' de '+e.source+' a '+e.target});
      const line=svgEl('path',{fill:'none',stroke:'#91a59b','stroke-width':1.6,'marker-end':'url(#'+id+')'}),hit=svgEl('path',{fill:'none',stroke:'transparent','stroke-width':14,class:'graph-edge-hit'}),title=svgEl('title');title.textContent=e.label+' · '+e.source+' → '+e.target;group.append(title,line,hit);
      group.onclick=ev=>{ev.stopPropagation();selectEdge(e);};group.onkeydown=ev=>{if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();selectEdge(e);}};edgeLayer.append(group);edgeElements.push({line,hit,e,index});});
    data.nodes.forEach(n=>{const group=svgEl('g',{role:'button',tabindex:0,'aria-label':n.label+', ID '+n.id,class:'graph-node'}),circle=svgEl('circle',{r:13,fill:colors[n.kind]||'#377db5'}),text=svgEl('text',{y:29,'text-anchor':'middle'}),title=svgEl('title');text.textContent=n.label.length>20?n.label.slice(0,19)+'…':n.label;title.textContent=n.label+' · ID '+n.id;group.append(title,circle,text);
      group.onpointerdown=ev=>{ev.stopPropagation();svg.setPointerCapture(ev.pointerId);drag={type:'node',id:n.id,x:ev.clientX,y:ev.clientY,moved:false,pointer:ev.pointerId};};
      group.onkeydown=ev=>{if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();ev.stopPropagation();selectNode(n);}};
      nodeLayer.append(group);nodeElements.set(n.id,{group,circle,text});});
    function redraw(){svg.setAttribute('viewBox',view.x+' '+view.y+' '+view.w+' '+view.h);for(const [key,el]of nodeElements){const p=positions.get(key);el.group.setAttribute('transform','translate('+p.x+' '+p.y+')');el.circle.setAttribute('stroke',selected===key?'#152f28':'#fff');el.circle.setAttribute('stroke-width',selected===key?4:2);el.text.style.display=check.checked?'':'none';}edgeElements.forEach(item=>{const d=path(item.e,item.index);item.line.setAttribute('d',d);item.hit.setAttribute('d',d);});}
    function point(event){const p=svg.createSVGPoint();p.x=event.clientX;p.y=event.clientY;return p.matrixTransform(svg.getScreenCTM().inverse());}
    function zoom(factor,center){const scale=Math.max(.25,Math.min(4,view.w*factor/700)),w=700*scale,h=440*scale,c=center||{x:view.x+view.w/2,y:view.y+view.h/2};view={x:c.x-(c.x-view.x)*w/view.w,y:c.y-(c.y-view.y)*h/view.h,w,h};redraw();}
    zoomIn.onclick=()=>zoom(.8);zoomOut.onclick=()=>zoom(1.25);reset.onclick=()=>{view={x:0,y:0,w:700,h:440};redraw();};check.onchange=redraw;
    svg.onpointerdown=ev=>{if(ev.button!==0)return;svg.setPointerCapture(ev.pointerId);drag={type:'pan',x:ev.clientX,y:ev.clientY,moved:false,pointer:ev.pointerId,view:{...view}};};
    svg.onpointermove=ev=>{if(!drag)return;if(Math.hypot(ev.clientX-drag.x,ev.clientY-drag.y)>3)drag.moved=true;if(drag.type==='node'){const p=point(ev);positions.set(drag.id,{x:p.x,y:p.y});}else{const rect=svg.getBoundingClientRect();view.x=drag.view.x-(ev.clientX-drag.x)*drag.view.w/rect.width;view.y=drag.view.y-(ev.clientY-drag.y)*drag.view.h/rect.height;}redraw();};
    svg.onpointerup=ev=>{if(!drag)return;const ended=drag;drag=null;if(svg.hasPointerCapture(ev.pointerId))svg.releasePointerCapture(ev.pointerId);if(ended.type==='node'&&!ended.moved)selectNode(nodeMap.get(ended.id));};
    svg.onpointercancel=()=>{drag=null;};
    svg.addEventListener('wheel',ev=>{if(!ev.ctrlKey)return;ev.preventDefault();zoom(ev.deltaY<0?.85:1.18,point(ev));},{passive:false});
    svg.onkeydown=ev=>{if(ev.key==='+'||ev.key==='='){ev.preventDefault();zoom(.8);}else if(ev.key==='-'){ev.preventDefault();zoom(1.25);}else if(ev.key==='0'){view={x:0,y:0,w:700,h:440};redraw();}};
    redraw();
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={layout};
  if(typeof window!=='undefined')window.GraphScopeGraph={mount};
})();
