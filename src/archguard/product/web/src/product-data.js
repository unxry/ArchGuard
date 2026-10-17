'use strict';
(() => {
 const A=window.AG,original=A.adapters.importArtifact;
 A.groupLabel=name=>A.locales[A.state.locale][name]||name;
 A.layerNames=()=>[...new Set(A.state.dataset.nodes.map(n=>n.group))].sort((a,b)=>{const order=['interface','application','infrastructure'];return (order.includes(a)?order.indexOf(a):3)-(order.includes(b)?order.indexOf(b):3)||a.localeCompare(b);});
 A.setEmpty=()=>{A.state.mode='LOCAL_RESULT';A.state.dataset={project:{id:'none',name:'ArchGuard',revision:'—'},kind:'EMPTY',nodes:[],edges:[],findings:[],coverage:[],diagnostics:[],provenance:{status:'NOT_RUN'},raw:null};A.state.selected=A.state.selectedNode=null;};
 A.adapters.importArtifact=(raw,name)=>{
  if(raw?.schema!=='archguard-product-v1')return original(raw,name);
  if(raw.mode!=='LOCAL_RESULT'||!raw.project||typeof raw.project.name!=='string'||!Array.isArray(raw.security)||raw.security.length>2||!raw.provenance||!/^[a-f0-9]{64}$/.test(raw.provenance.source_digest)||!raw.iam?.source_files||!raw.sources)throw Error('INVALID_ARTIFACT');
  const d=original(raw.graph,name),parts=[d,...(raw.architecture?[original(raw.architecture,name)]:[]),...raw.security.map(s=>original(s,name))];
  d.findings=[...new Map(parts.flatMap(p=>p.findings).map(f=>[f.id,f])).values()];
  d.coverage=[...new Set(parts.flatMap(p=>p.coverage.map(c=>c.rule)))].map(rule=>{const cs=parts.flatMap(p=>p.coverage.filter(c=>c.rule===rule));const outcomes=['FAILED','DEFINITIVE_POSITIVE','POTENTIAL','INSUFFICIENT_EVIDENCE','PARTIAL','UNSUPPORTED','NOT_APPLICABLE'];return {...cs[0],outcome:outcomes.find(o=>cs.some(c=>c.outcome===o)),scope:{ru:'Фактический локальный анализ · V2',en:'Actual local analysis · V2'},detail:{ru:'Ограниченная область V2. Нулевой результат не доказывает безопасность. Подробности по языкам — в исходном результате.',en:'Bounded V2 scope. Zero findings does not prove safety. Per-language details are retained in the result.'}}});
  for(const n of d.nodes){n.label=n.path.split('/').pop()||n.label;const matches=raw.classification?.nodes?.filter(c=>c.file_path===n.path)||[],layers=[...new Set(matches.map(c=>c.layer).filter(Boolean))];n.group=layers.length===1?layers[0]:'unclassified';if(d.nodes.length<=24)n.domain=n.group;}
  for(const f of d.findings){f.nodeIds=d.nodes.filter(n=>f.evidence.some(v=>v.path===n.path)).map(n=>n.id);for(const v of f.evidence){const lines=Object.hasOwn(raw.sources,v.path)?raw.sources[v.path]:null;if(lines&&Array.isArray(lines)&&lines.every(x=>typeof x==='string')){v.startLine=Math.max(1,(v.line||1)-2);v.code=lines.slice(v.startLine-1,v.startLine+7);}}}
  for(const edge of d.edges)edge.findingIds=d.findings.filter(f=>f.edgeIds.includes(edge.id)||f.nodeIds.includes(edge.source)&&f.nodeIds.includes(edge.target)).map(f=>f.id);
  d.project={...d.project,...raw.project,revision:raw.provenance.snapshot_fingerprint,language:[...new Set(raw.iam.source_files.map(f=>f.language))].join(' / ')};
  d.kind='PRODUCT';d.raw=raw;d.provenance={...raw.provenance,status:raw.graph.status!=='COMPLETE'?raw.graph.status:raw.security.length?'PARTIAL':'COMPLETE',component_status:{graph:raw.graph.status,security:raw.security.length?'PARTIAL':'NOT_RUN'},synthetic:false,validation:'PRODUCT_STRUCTURE_ONLY'};d.diagnostics=parts.flatMap(p=>p.diagnostics);return d;
 };
})();
