'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const demo = window.DEMO;
  if (!demo) { $('inspectorContent').textContent = 'Demo fixtures could not be loaded. Keep fixtures.js beside index.html.'; return; }
  const state = {view:'atlas',scenario:'small',query:'',node:null,finding:demo.findings[0].id,coverage:'SEC002',inspector:true,focus:false,overlay:true,tab:'evidence',evidence:0,page:0,zoom:1,panX:0,panY:0};
  let nodes = [], edges = [], findings = [], graphHeight = 560, transformFrame = 0, toastTimer;
  const outcome = {
    DEFINITIVE_POSITIVE:{label:'Definitive positive',short:'Positive',symbol:'◆',class:'positive'},
    POTENTIAL:{label:'Potential',short:'Potential',symbol:'◇',class:'potential'},
    INSUFFICIENT_EVIDENCE:{label:'Insufficient evidence',short:'Insufficient',symbol:'?',class:'insufficient'},
    PARTIAL:{label:'Partial analysis',short:'Partial',symbol:'◐',class:'partial'},
    UNSUPPORTED:{label:'Unsupported',short:'Unsupported',symbol:'—',class:'unsupported'},
    DEFINITIVE_NEGATIVE:{label:'Negative · scoped',short:'Scoped negative',symbol:'✓',class:'negative'},
    FAILED:{label:'Analysis failed',short:'Failed',symbol:'!',class:'positive'}
  };
  const confirmed = f => ['CONFIRMED','CONFIRMED_PATTERN','SUPPORTED'].includes(f.status);
  const findFinding = () => findings.find(f=>f.id===state.finding) || findings[0];
  const statusLabel = f => ({CONFIRMED:'Confirmed · rule proof',SUPPORTED:'Supported evidence',CONFIRMED_PATTERN:'Confirmed pattern',CANDIDATE:'Candidate · uncalibrated',POTENTIAL:'Potential · review needed',INSUFFICIENT_EVIDENCE:'Insufficient evidence'}[f.status] || f.status);
  const statusBadge = f => `<span class="status-badge ${confirmed(f)?'':'uncertain'}"><span class="status-symbol" aria-hidden="true">${confirmed(f)?'◆':'◇'}</span>${esc(statusLabel(f))}</span>`;
  const severityBadge = f => `<span class="severity ${(f.severity||'unrated').toLowerCase()}">${esc(f.severity||'Unrated')}</span>`;
  function announce(message) { $('announcement').textContent=message; }
  function toast(message) { clearTimeout(toastTimer); $('toast').textContent=message; $('toast').hidden=false; toastTimer=setTimeout(()=>$('toast').hidden=true,3200); }
  function loadScenario() {
    document.body.dataset.scenario=state.scenario;
    nodes=demo.nodes.map(n=>({...n})); edges=demo.edges.map(e=>({...e})); findings=demo.findings.map(f=>({...f})); graphHeight=560;
    if(state.scenario==='dense') {
      const layers=['interface','application','infrastructure'];
      for(let i=0;i<28;i++) {
        const layer=layers[i%3], id=`extended-${i+1}`;
        nodes.push({id,label:`${['Entry','Service','Adapter'][i%3]} ${String(i+1).padStart(2,'0')}`,layer,role:'Density study module',path:`demo/density/${id}.ts`,x:[165,505,845][i%3],y:0});
      }
      layers.forEach(layer=>nodes.filter(n=>n.layer===layer).forEach((n,i)=>n.y=110+i*84));
      nodes.slice(12).forEach((n,i)=>{
        const possible=nodes.filter(m=>m.layer!==n.layer);
        [possible[(i*3)%possible.length],possible[(i*3+4)%possible.length]].forEach((target,j)=>edges.push({id:`density-edge-${i}-${j}`,source:n.id,target:target.id,relation:j?'CALLS':'IMPORTS',violation:false}));
      });
      graphHeight=1290;
    }
    if(state.scenario==='many') {
      findings=Array.from({length:240},(_,i)=>{const base=demo.findings[i%demo.findings.length];return {...base,id:`${base.id}-sample-${i+1}`,sample:i+1,baseId:base.id,syntheticRepetition:true};});
    }
    state.finding=findings[0].id;state.node=null;state.tab='evidence';state.evidence=0;state.page=0;state.focus=false;state.zoom=1;state.panX=0;state.panY=0;
    $('sceneCount').textContent=`${nodes.length} modules`;
    $('recordCount').textContent=String(findings.length).padStart(2,'0');
    $('queueSummary').textContent=state.scenario==='many'?'240 synthetic repetitions for queue testing.':`${demo.findings.filter(confirmed).length} supported / confirmed · ${demo.findings.filter(f=>!confirmed(f)).length} candidates / uncertain`;
    drawGraph();render();
  }
  function switchView(view, focusHeading=false) {
    if(!['atlas','findings','coverage'].includes(view)) return;
    state.view=view;
    document.querySelectorAll('[data-view]').forEach(b=>{b.classList.toggle('active',b.dataset.view===view);if(b.dataset.view===view)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
    ['atlas','findings','coverage'].forEach(v=>$(v+'View').hidden=v!==view);
    const titles={atlas:['01','Architecture atlas','Commerce, <em>in context.</em>','Understand the structure. Follow the evidence.'],findings:['02','Findings & candidates','Evidence, <em>before conclusions.</em>','A focused queue. Every observation keeps its provenance.'],coverage:['03','Security coverage','Know what <em>you know.</em>','Visible findings. Visible limits. No implied safety.']};
    const t=titles[view];$('viewNumber').textContent=t[0];$('viewCaption').textContent=t[1];$('pageTitle').innerHTML=t[2];$('pageDescription').textContent=t[3];
    render();
    if(focusHeading){$('pageTitle').tabIndex=-1;$('pageTitle').focus({preventScroll:true});}
  }
  function setInspector(open) {
    state.inspector=open;$('inspector').hidden=!open;$('workspace').classList.toggle('inspector-closed',!open);$('inspectorToggle').setAttribute('aria-expanded',String(open));
  }
  function render() {updateGraph();renderFindings();renderCoverage();renderInspector();setInspector(state.inspector);}
  function drawGraph() {
    $('graph').setAttribute('viewBox',matchMedia('(max-width:700px)').matches&&state.scenario!=='dense'?'20 60 460 480':`0 0 1010 ${graphHeight}`);
    const bands=['interface','application','infrastructure'].map((layer,i)=>`<rect class="layer-band" x="${50+i*340}" y="72" width="230" height="${graphHeight-102}" rx="20"/><text class="layer-index" x="${62+i*340}" y="43">0${i+1}</text><text class="layer-heading" x="${90+i*340}" y="43">${layer.toUpperCase()}</text>`).join('');
    const edgeMarkup=edges.map(e=>{const a=nodes.find(n=>n.id===e.source),b=nodes.find(n=>n.id===e.target);let d;
      if(a.x===b.x) {const side=a.y<b.y?1:-1;const x=a.x+side*84;d=`M${x},${a.y} C${x+side*65},${a.y} ${x+side*65},${b.y} ${x},${b.y}`;}
      else if(e.id==='e-checkout-orderstore'){d=`M${a.x+84},${a.y-15} C315,${a.y-15} 295,76 350,76 L660,76 C715,76 705,${b.y-15} ${b.x-84},${b.y-15}`;}
      else {const direction=b.x>a.x?1:-1,sx=a.x+84*direction,tx=b.x-84*direction;d=`M${sx},${a.y} C${sx+direction*110},${a.y} ${tx-direction*110},${b.y} ${tx},${b.y}`;}
      return `<path class="graph-edge ${e.violation?'hot':''}" data-edge="${esc(e.id)}" d="${d}"/><path class="edge-hit" data-edge-hit="${esc(e.id)}" d="${d}" role="button" tabindex="-1" aria-label="${esc(a.label)} depends on ${esc(b.label)} through ${e.relation}${e.violation?', rule violation':''}"><title>${esc(a.label)} → ${esc(b.label)} · ${e.relation}</title></path>`;
    }).join('');
    const label=state.scenario==='dense'?'':`<g class="violation-label" aria-hidden="true"><rect class="edge-label-bg" x="430" y="64" width="150" height="23" rx="11.5"/><text class="edge-label" x="505" y="79" text-anchor="middle">↗ ARCH001 · FORBIDDEN</text></g>`;
    const nodeMarkup=nodes.map(n=>{const issue=demo.findings.some(f=>f.nodeIds.includes(n.id)&&confirmed(f));const symbol=n.layer==='interface'?'<path class="node-symbol" d="M-65,-10 L-57,-3 L-65,4 Z"/>':n.layer==='application'?'<rect class="node-symbol" x="-67" y="-8" width="12" height="12" rx="2"/>':'<path class="node-symbol" d="M-67,-8 h13 v5 h-13z M-67,0 h13 v5 h-13z"/>';
      return `<g class="graph-node ${issue?'issue':''}" data-node="${n.id}" transform="translate(${n.x},${n.y})" role="button" tabindex="0" aria-label="${esc(n.label)}, ${n.layer} module${issue?', related finding':''}" aria-pressed="false"><rect class="node-body" x="-84" y="-32" width="168" height="64" rx="${n.layer==='infrastructure'?3:9}"/>${symbol}<text class="node-label" x="-44" y="-2">${esc(n.label)}</text><text class="node-meta" x="-44" y="16">${n.layer==='interface'?'ENTRY':n.layer==='application'?'SERVICE':'ADAPTER'} · TS</text>${issue?'<circle class="node-status" cx="73" cy="-23" r="6"/><text class="node-status-text" x="73" y="-20" text-anchor="middle">!</text>':''}</g>`;
    }).join('');
    $('graphWorld').innerHTML=bands+edgeMarkup+label+nodeMarkup;applyTransform();
  }
  function selectedGraph() {
    if(state.node){const connected=edges.filter(e=>e.source===state.node||e.target===state.node);return {nodes:new Set([state.node,...connected.flatMap(e=>[e.source,e.target])]),edges:new Set(connected.map(e=>e.id))};}
    const f=findFinding();return {nodes:new Set(f.nodeIds),edges:new Set(f.edgeIds)};
  }
  function updateGraph() {
    const selected=selectedGraph(),q=state.query.toLowerCase();
    const matches=new Set(nodes.filter(n=>`${n.label} ${n.role} ${n.layer} ${n.path}`.toLowerCase().includes(q)).map(n=>n.id));
    const matchingFindings=findings.filter(f=>`${f.rule} ${f.title} ${f.description}`.toLowerCase().includes(q));
    if(q) matchingFindings.forEach(f=>f.nodeIds.forEach(id=>matches.add(id)));
    document.querySelectorAll('[data-node]').forEach(el=>{const id=el.dataset.node;el.classList.toggle('selected',state.node?state.node===id:selected.nodes.has(id));el.classList.toggle('issue',state.overlay&&demo.findings.some(f=>f.nodeIds.includes(id)&&confirmed(f)));el.setAttribute('aria-pressed',String(state.node===id));el.classList.toggle('dimmed',(state.focus&&!selected.nodes.has(id))||(q&&!matches.has(id)));});
    edges.forEach(e=>{const el=document.querySelector(`[data-edge="${e.id}"]`);el.classList.toggle('hot',state.overlay&&e.violation);el.classList.toggle('selected-edge',selected.edges.has(e.id));el.classList.toggle('dimmed',(state.focus&&!selected.edges.has(e.id))||(q&&(!matches.has(e.source)&&!matches.has(e.target))));});
    document.querySelectorAll('.violation-label').forEach(el=>el.style.display=state.overlay?'':'none');
    document.querySelectorAll('.node-status,.node-status-text').forEach(el=>el.style.display=state.overlay?'':'none');
    $('graphEmpty').hidden=!q||matches.size>0;
    $('focusGraph').setAttribute('aria-pressed',String(state.focus));
    $('overlayButton').setAttribute('aria-pressed',String(state.overlay));$('overlayButton').classList.toggle('active',state.overlay);
    $('mapHeadline').textContent=state.node?`${nodes.find(n=>n.id===state.node).label} · ${selected.edges.size} direct relationships`:state.focus?'The evidence path, isolated in context.':'A boundary deserves a closer look.';
  }
  function applyTransform() {
    cancelAnimationFrame(transformFrame);transformFrame=requestAnimationFrame(()=>{
      $('graphWorld').setAttribute('transform',`translate(${state.panX} ${state.panY}) scale(${state.zoom})`);
      $('zoomValue').textContent=`${Math.round(state.zoom*100)}%`;
    });
  }
  function zoom(factor, cx=505, cy=graphHeight/2) {
    const next=Math.max(.5,Math.min(3.5,state.zoom*factor));const ratio=next/state.zoom;
    state.panX=cx-(cx-state.panX)*ratio;state.panY=cy-(cy-state.panY)*ratio;state.zoom=next;applyTransform();
  }
  function fitGraph(){state.zoom=1;state.panX=0;state.panY=0;$('graph').setAttribute('viewBox',`0 0 1010 ${graphHeight}`);applyTransform();}
  function focusSelection(){state.focus=!state.focus;updateGraph();announce(state.focus?'Connected evidence path highlighted.':'Full graph context restored.');}
  function selectFinding(id, jump=false) {
    const f=findings.find(item=>item.id===id);if(!f)return;
    state.finding=id;state.node=null;state.tab='evidence';state.evidence=0;setInspector(true);
    if(jump){state.focus=true;switchView('atlas');fitGraph();}else render();
    announce(`${f.rule}. ${f.title}. ${statusLabel(f)}.`);
    if(state.view==='findings')document.querySelector(`[data-finding="${f.id}"]`)?.focus({preventScroll:true});
    if(matchMedia('(max-width:700px)').matches){$('inspector').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'instant':'smooth',block:'start'});}
  }
  function selectNode(id){state.node=id;state.tab='evidence';setInspector(true);render();announce(`${nodes.find(n=>n.id===id).label} selected. Inspector shows direct dependencies.`);if(matchMedia('(max-width:700px)').matches)$('inspector').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'instant':'smooth',block:'start'});}
  function filteredFindings() {
    const ns=$('namespaceFilter').value,status=$('stateFilter').value,severity=$('severityFilter').value,q=state.query.toLowerCase();
    return findings.filter(f=>(ns==='all'||f.namespace===ns)&&(status==='all'||(status==='confirmed'?confirmed(f):!confirmed(f)))&&(severity==='all'||(severity==='unrated'?!f.severity:f.severity===severity))&&`${f.rule} ${f.title} ${f.status} ${f.evidence.map(e=>`${e.path} ${e.detail}`).join(' ')}`.toLowerCase().includes(q));
  }
  function renderFindings(){
    const filtered=filteredFindings(),pages=Math.max(1,Math.ceil(filtered.length/6));state.page=Math.min(state.page,pages-1);
    $('resultCount').textContent=`${filtered.length} record${filtered.length===1?'':'s'}`;
    $('findingsList').innerHTML=filtered.slice(state.page*6,state.page*6+6).map(f=>`<button class="finding-row ${f.id===state.finding?'selected':''}" data-finding="${esc(f.id)}" aria-pressed="${f.id===state.finding}"><div><span class="rule-id">${f.rule} <span class="divider">/</span> ${f.namespace==='ARCH'?'ARCHITECTURE':'SECURITY'}${f.sample?` / SAMPLE ${f.sample}`:''}</span><h3>${esc(f.title)}</h3><p>${esc(f.evidence[0].path)}:${f.evidence[0].line}</p></div><div class="row-status">${severityBadge(f)}${statusBadge(f)}</div></button>`).join('')||'<div class="empty-state">No records match these filters.<br><button class="text-button" data-action="reset-filters">Reset filters and search</button></div>';
    $('pageCount').textContent=`Page ${state.page+1} of ${pages}`;$('previousPage').disabled=state.page===0;$('nextPage').disabled=state.page>=pages-1;
  }
  function renderCoverage(){
    const q=state.query.toLowerCase(),rows=demo.coverage.filter(c=>`${c.rule} ${c.name} ${c.outcome} ${c.scope}`.toLowerCase().includes(q));
    $('coverageSummary').innerHTML=Object.entries(outcome).filter(([key])=>demo.coverage.some(c=>c.outcome===key)).map(([key,o])=>`<span class="outcome-${o.class}"><span aria-hidden="true">${o.symbol}</span> ${demo.coverage.filter(c=>c.outcome===key).length} ${o.short.toLowerCase()}</span>`).join('');
    $('coverageList').innerHTML=rows.map(c=>{const o=outcome[c.outcome];return `<button class="coverage-row ${c.rule===state.coverage?'selected':''}" data-coverage="${c.rule}" aria-pressed="${c.rule===state.coverage}"><span class="coverage-rule"><span class="outcome-symbol outcome-${o.class}" aria-hidden="true">${o.symbol}</span><span><strong>${c.rule} · ${esc(c.name)}</strong><small>${esc(c.scope)}</small></span></span><span class="coverage-outcome outcome-${o.class}">${o.label}</span></button>`;}).join('')||'<div class="empty-state">No rules match this search.<br><button class="text-button" data-action="clear-search">Clear search</button></div>';
  }
  function sourceMarkup(e) {
    return `<div class="code-header">${esc(e.path)} <span class="divider">/</span> SYNTHETIC SOURCE</div><pre class="code-block" tabindex="0" aria-label="Synthetic source excerpt"><code>${e.code.map((line,i)=>`<span class="code-line ${e.startLine+i===e.line?'target-line':''}"><span class="line-number">${e.startLine+i}</span>${esc(line)}</span>`).join('')}</code></pre><p class="source-caption">One-based source coordinates. This excerpt is an authored demonstration, not source from your repository.</p>`;
  }
  function renderInspector(){
    $('inspectorIndex').textContent=`/ ${state.view==='coverage'?'03':state.node?'02':'01'}`;
    if(state.view==='coverage'){renderCoverageInspector();return;}
    if(state.view==='atlas'&&state.node){renderNodeInspector();return;}
    const f=findFinding(),e=f.evidence[Math.min(state.evidence,f.evidence.length-1)];
    $('inspectorContent').innerHTML=`<div class="inspector-body"><div class="dossier-top"><span class="rule-id">${f.rule} / ${f.namespace}</span>${severityBadge(f)}</div><h2>${esc(f.title)}</h2>${statusBadge(f)}<p class="description">${esc(f.description)}</p><dl class="dossier-meta"><div><dt>Detector</dt><dd>${esc(f.detector)}</dd></div><div><dt>Confidence</dt><dd>${f.status==='CANDIDATE'?'Uncalibrated':'Not supplied'}</dd></div></dl><div class="inspector-tabs" role="tablist" aria-label="Finding detail"><button role="tab" id="evidenceTab" aria-controls="evidencePanel" aria-selected="${state.tab==='evidence'}" tabindex="${state.tab==='evidence'?0:-1}" data-detail-tab="evidence">Evidence <span class="divider">${f.evidence.length}</span></button><button role="tab" id="sourceTab" aria-controls="evidencePanel" aria-selected="${state.tab==='source'}" tabindex="${state.tab==='source'?0:-1}" data-detail-tab="source">Source</button></div><div id="evidencePanel" role="tabpanel" aria-labelledby="${state.tab==='evidence'?'evidenceTab':'sourceTab'}">${state.tab==='evidence'?f.evidence.map((ev,i)=>`<article class="evidence-step"><span class="step-number">0${i+1}</span><h3>${esc(ev.title)}</h3><p>${esc(ev.detail)}</p><button class="source-link" data-source="${i}">${esc(ev.path)}:${ev.line} ↗</button></article>`).join(''):sourceMarkup(e)+`<div>${f.evidence.map((ev,i)=>`<button class="related-link" data-source="${i}" aria-pressed="${state.evidence===i}">${esc(ev.title)} <small>0${i+1}</small></button>`).join('')}</div>`}</div><div class="action-label">NEXT INVESTIGATION</div><p class="recommendation">${esc(f.recommendation)}</p><button class="primary-button" data-action="trace">${f.edgeIds.length?'Trace this dependency':'Show related modules'} <span aria-hidden="true">↗</span></button><p class="scope-note">${f.namespace==='SEC'?'Security evidence is independent of ARCH. Related module placement is illustrative; no runtime flow is inferred.':'Static dependency evidence. Arrows do not represent runtime execution.'}</p></div>`;
  }
  function renderNodeInspector(){
    const n=nodes.find(item=>item.id===state.node),incoming=edges.filter(e=>e.target===n.id),outgoing=edges.filter(e=>e.source===n.id),related=findings.filter(f=>f.nodeIds.includes(n.id));
    const unique=related.filter((f,i)=>related.findIndex(other=>other.rule===f.rule)===i);
    const connection=(e,dir)=>{const target=nodes.find(item=>item.id===(dir==='in'?e.source:e.target));return `<div class="connection-row">${dir==='in'?'←':'→'} <button data-select-node="${target.id}">${esc(target.label)}</button> <small>${e.relation}</small></div>`;};
    $('inspectorContent').innerHTML=`<div class="inspector-body"><div class="dossier-top"><span class="rule-id">MODULE / TYPESCRIPT</span><span class="rule-id">${n.layer==='interface'?'△':n.layer==='application'?'□':'▤'}</span></div><h2>${esc(n.label)}</h2><span class="status-badge">${esc(n.layer)} · assigned layer</span><p class="description">${esc(n.role)}. A module aggregate in the synthetic architecture model.</p><div class="code-header">${esc(n.path)}</div><dl class="dossier-meta"><div><dt>Incoming</dt><dd>${incoming.length} relationships</dd></div><div><dt>Outgoing</dt><dd>${outgoing.length} relationships</dd></div></dl><div class="action-label">LINKED FINDINGS / CANDIDATES</div>${unique.map(f=>`<button class="related-link" data-finding="${f.id}"><span><small>${f.rule}</small><br>${esc(f.title)}</span><span aria-hidden="true">↗</span></button>`).join('')||'<p class="description">No linked findings in this demo. This does not establish safety or complete analysis.</p>'}<div class="node-connections"><h3>DEPENDS ON</h3>${outgoing.map(e=>connection(e,'out')).join('')||'<p class="description">No resolved outgoing edges in this fixture.</p>'}</div><div class="node-connections"><h3>DEPENDENTS</h3>${incoming.map(e=>connection(e,'in')).join('')||'<p class="description">No resolved incoming edges in this fixture.</p>'}</div><button class="primary-button" data-action="focus-node">${state.focus?'Restore full graph':'Focus direct neighbours'} <span aria-hidden="true">↗</span></button><p class="scope-note">Incoming relationships show direct dependents, not a complete change-impact estimate. Unresolved dependencies are not represented.</p></div>`;
  }
  function renderCoverageInspector(){
    const c=demo.coverage.find(item=>item.rule===state.coverage),o=outcome[c.outcome],linked=findings.find(f=>f.rule===c.rule),cert=c.certificate;
    $('inspectorContent').innerHTML=`<div class="inspector-body"><div class="dossier-top"><span class="rule-id">${c.rule} / SECURITY</span><span class="rule-id">${o.symbol}</span></div><h2>${esc(c.name)}</h2><span class="status-badge ${['PARTIAL','POTENTIAL','INSUFFICIENT_EVIDENCE','UNSUPPORTED'].includes(c.outcome)?'uncertain':''}">${o.symbol} ${o.label}</span><p class="description">${esc(c.detail)}</p><div class="action-label">EVALUATED SCOPE</div><p class="recommendation">${esc(c.scope)}</p><dl class="dossier-meta"><div><dt>State</dt><dd>${esc(c.status)}</dd></div><div><dt>Scope certificate</dt><dd>${cert?'COMPLETE · synthetic':'Not proven'}</dd></div></dl>${cert?`<div class="certificate"><strong>SYNTHETIC CERTIFICATE</strong><span>${esc(cert.rule_id)} / ${esc(cert.language)}</span><span>✓ Scope and source coverage</span><span>✓ Sink and call resolution</span><span>✓ Summary and dataflow scope</span><span>✓ Framework and proof checks</span><span>✓ No unsupported constructs or failures</span></div><p class="description">${esc(cert.declared_scope)}</p>${sourceMarkup({...cert,line:2})}`:''}${linked?`<button class="primary-button" data-coverage-finding="${linked.id}">Inspect linked evidence <span aria-hidden="true">↗</span></button>`:''}<p class="scope-note">${cert?'No weak algorithm in this certified scope. This is not “repository secure”.':'Coverage and finding status are separate. Zero findings never implies a security guarantee.'}<br>DEMO DATA · No analyzer was executed.</p></div>`;
  }
  function exportBrief(){
    const payload={label:'DEMO DATA',prototype:'STRATA v1',synthetic:true,backendConnected:false,scenario:state.scenario,view:state.view,selectedNode:state.node,selectedFinding:findFinding(),securityScope:state.view==='coverage'?demo.coverage.find(c=>c.rule===state.coverage):null,graph:{nodes,edges},limitations:['Synthetic data only; no analysis performed.','No findings is not a safety guarantee.','Source coordinates and fixture evidence are illustrative.']};
    const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='archguard-strata-demo-brief.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('Demo brief exported · JSON');
  }
  document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>switchView(b.dataset.view)));
  document.querySelector('.brand').addEventListener('click',e=>{e.preventDefault();switchView('atlas');});
  $('reviewQueue').addEventListener('click',()=>switchView('findings',true));
  $('search').addEventListener('input',e=>{state.query=e.target.value;state.page=0;updateGraph();renderFindings();renderCoverage();announce(`${state.view==='findings'?filteredFindings().length:state.view==='coverage'?$('coverageList').querySelectorAll('button[data-coverage]').length:nodes.filter(n=>`${n.label} ${n.layer}`.toLowerCase().includes(state.query.toLowerCase())).length} search results.`);});
  ['namespaceFilter','stateFilter','severityFilter'].forEach(id=>$(id).addEventListener('change',()=>{state.page=0;renderFindings();announce(`${filteredFindings().length} filtered records.`);}));
  $('scenario').addEventListener('change',e=>{state.scenario=e.target.value;state.query='';$('search').value='';['namespaceFilter','stateFilter','severityFilter'].forEach(id=>$(id).value='all');loadScenario();if(state.scenario==='many')switchView('findings');announce(`${state.scenario} demo scenario loaded. ${nodes.length} modules and ${findings.length} queue records.`);});
  $('inspectorToggle').addEventListener('click',()=>setInspector(!state.inspector));
  $('closeInspector').addEventListener('click',()=>{setInspector(false);$('inspectorToggle').focus();});
  $('overlayButton').addEventListener('click',()=>{state.overlay=!state.overlay;updateGraph();});
  $('zoomIn').addEventListener('click',()=>zoom(1.2));$('zoomOut').addEventListener('click',()=>zoom(1/1.2));$('fitGraph').addEventListener('click',()=>{fitGraph();state.focus=false;updateGraph();});$('focusGraph').addEventListener('click',focusSelection);
  $('previousPage').addEventListener('click',()=>{state.page--;renderFindings();announce($('pageCount').textContent);});$('nextPage').addEventListener('click',()=>{state.page++;renderFindings();announce($('pageCount').textContent);});
  $('exportButton').addEventListener('click',exportBrief);
  $('guideButton').addEventListener('click',()=>$('guide').showModal());$('closeGuide').addEventListener('click',()=>$('guide').close());$('beginExploring').addEventListener('click',()=>{$('guide').close();switchView('atlas');});
  document.addEventListener('click',e=>{
    const b=e.target.closest('button,[data-node],[data-edge-hit]');if(!b)return;
    if(b.dataset.finding)selectFinding(b.dataset.finding);
    if(b.dataset.node)selectNode(b.dataset.node);
    if(b.dataset.selectNode)selectNode(b.dataset.selectNode);
    if(b.dataset.edgeHit){const edge=edges.find(item=>item.id===b.dataset.edgeHit),f=findings.find(item=>item.edgeIds.includes(edge.id));if(f)selectFinding(f.id);else{selectNode(edge.source);toast(`${edge.relation}: ${nodes.find(n=>n.id===edge.source).label} → ${nodes.find(n=>n.id===edge.target).label}`);}}
    if(b.dataset.coverage){state.coverage=b.dataset.coverage;setInspector(true);renderCoverage();renderInspector();document.querySelector(`[data-coverage="${state.coverage}"]`).focus({preventScroll:true});announce(`${b.dataset.coverage} coverage selected.`);}
    if(b.dataset.coverageFinding){switchView('findings');selectFinding(b.dataset.coverageFinding);}
    if(b.dataset.detailTab){state.tab=b.dataset.detailTab;renderInspector();$(state.tab==='source'?'sourceTab':'evidenceTab').focus({preventScroll:true});}
    if(b.dataset.source!==undefined){state.evidence=Number(b.dataset.source);state.tab='source';renderInspector();$('sourceTab').focus({preventScroll:true});}
    if(b.dataset.action==='trace'){state.focus=true;switchView('atlas');fitGraph();announce('Related evidence path highlighted in the atlas.');}
    if(b.dataset.action==='focus-node'){focusSelection();renderInspector();}
    if(b.dataset.action==='clear-search'||b.dataset.action==='reset-filters'){state.query='';$('search').value='';state.page=0;if(b.dataset.action==='reset-filters')['namespaceFilter','stateFilter','severityFilter'].forEach(id=>$(id).value='all');render();$('search').focus();}
  });
  document.addEventListener('keydown',e=>{
    const editable=/INPUT|TEXTAREA|SELECT/.test(e.target.tagName);
    if(e.key==='/'&&!editable&&!$('guide').open){e.preventDefault();$('search').focus();}
    if(e.key==='Escape'&&!$('guide').open){state.focus=false;state.query='';$('search').value='';render();}
    if(e.target.matches('[data-node]')){
      if(['Enter',' '].includes(e.key)){e.preventDefault();selectNode(e.target.dataset.node);}
      if(['ArrowRight','ArrowDown','ArrowLeft','ArrowUp'].includes(e.key)){e.preventDefault();const elements=[...document.querySelectorAll('[data-node]')],index=elements.indexOf(e.target),step=['ArrowRight','ArrowDown'].includes(e.key)?1:-1;elements[(index+step+elements.length)%elements.length].focus();}
    }
    if(e.target.matches('[data-detail-tab]')&&['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();state.tab=state.tab==='source'?'evidence':'source';renderInspector();$(state.tab==='source'?'sourceTab':'evidenceTab').focus();}
  });
  let drag=null;
  function svgPoint(event){const matrix=$('graph').getScreenCTM();return new DOMPoint(event.clientX,event.clientY).matrixTransform(matrix.inverse());}
  $('graph').addEventListener('pointerdown',e=>{if(e.button!==0||e.target.closest('[data-node],[data-edge-hit]'))return;const p=svgPoint(e);drag={x:p.x,y:p.y,panX:state.panX,panY:state.panY};$('graph').setPointerCapture(e.pointerId);$('graph').classList.add('panning');});
  $('graph').addEventListener('pointermove',e=>{if(!drag)return;const p=svgPoint(e);state.panX=Math.max(-2200,Math.min(2200,drag.panX+p.x-drag.x));state.panY=Math.max(-graphHeight*2,Math.min(graphHeight*2,drag.panY+p.y-drag.y));applyTransform();});
  const stopDrag=()=>{drag=null;$('graph').classList.remove('panning');};$('graph').addEventListener('pointerup',stopDrag);$('graph').addEventListener('pointercancel',stopDrag);
  $('graph').addEventListener('wheel',e=>{if(!e.ctrlKey&&!e.metaKey)return;e.preventDefault();const p=svgPoint(e);zoom(e.deltaY<0?1.08:1/1.08,p.x,p.y);},{passive:false});
  matchMedia('(max-width:700px)').addEventListener('change',()=>{drawGraph();updateGraph();});
  loadScenario();
  window.STRATA={getState:()=>({...state,nodeCount:nodes.length,edgeCount:edges.length,findingCount:findings.length}),exportBrief};
})();
