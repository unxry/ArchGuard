'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const sandbox = {window:{AG:{}}, URL};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../src/adapters.js'),'utf8'),sandbox);
const {importArtifact, safeRelative, validateGit, validatePath, command} = sandbox.window.AG.adapters;
const uuid = n => `10000000-0000-4000-8000-${String(n).padStart(12,'0')}`;
const canonical = value => JSON.stringify(value,(_,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.keys(x).sort().map(k=>[k,x[k]])):x);
const hash = value => crypto.createHash('sha256').update(canonical(value)).digest('hex');
const uuid5 = (namespace,value) => {const b=crypto.createHash('sha1').update(Buffer.from(namespace.replaceAll('-',''),'hex')).update(canonical(value)).digest().subarray(0,16);b[6]=(b[6]&15)|80;b[8]=(b[8]&63)|128;const h=b.toString('hex');return `${h.slice(0,8)}-${h.slice(8,12)}-${h.slice(12,16)}-${h.slice(16,20)}-${h.slice(20)}`;};
const loc = line => ({file_path:'src/demo.ts',start_line:line,start_column:1,end_line:line,end_column:8});
const source = line => ({file_id:uuid(4),location:loc(line),language:'TYPESCRIPT',symbol_id:null,module_id:null,input_category:'SOURCE',configuration_category:null});
const clone = value => JSON.parse(JSON.stringify(value));
const rejects = (factory,change) => {const value=factory();change(value);assert.throws(()=>importArtifact(value),error=>error.message==='INVALID_ARTIFACT');};

function securityFinding(status='SUPPORTED',complete=true) {
 const evidence=[5,6,7].map((line,i)=>({namespace:'SEC',id:uuid(10+i),kind:['DATAFLOW_SOURCE','DATAFLOW_STEP','DATAFLOW_SINK'][i],source:source(line),summary:['request input','local string construction','query sink'][i],analysis_version:'security-interprocedural-v2',related_evidence:[],metadata:{step_kind:'synthetic-local-step'}}));
 const flow={protocol_version:'security-interprocedural-v2',steps:evidence.map((e,i)=>({role:['SOURCE','PROPAGATION','SINK'][i],evidence_ref:e.id})),complete,uncertainty:complete?[]:['CALL_UNRESOLVED']};
 const f={schema_version:'security-finding-v1',namespace:'SEC',repository_id:uuid(1),snapshot_id:uuid(2),rule_id:'SEC002',title:'Synthetic SQL evidence',description:'Authored contract fixture; no analysis performed.',severity:'HIGH',evidence_strength:'HIGH',status,language:'TYPESCRIPT',primary_source:source(7),evidence,evidence_refs:evidence.map(e=>e.id),source_ref:evidence[0].id,sink_ref:evidence[2].id,flow,remediation:'Review the parameter boundary.',metadata:{raw_values:'OMITTED'},analyzer_version:'security-interprocedural-v2'};
 f.id=uuid5(f.repository_id,{snapshot:f.snapshot_id,rule:f.rule_id,primary:f.primary_source,sink:f.primary_source,flow});return f;
}
function security(findings=[securityFinding()]) {return {namespace:'SEC',findings,requested_rules:['SEC002'],analyzed_rules:['SEC002'],applicable_rules:findings.length?['SEC002']:[],unsupported_rules:[],diagnostics:[],analyzer_version:'security-interprocedural-v2',analysis_metadata:{coverage:{SEC002:{requested:true,supported:true,evaluated:true,status:'SUPPORTED_PARTIAL_V2_SCOPE'}},partial:true},zero_findings_is_security_guarantee:false};}
function graph() {return {result_schema_version:'1.0',status:'COMPLETE',is_valid:true,is_complete:true,graph:{graph_schema_version:'1.0',project_id:uuid(1),projection:{projection:'component',included_relations:['IMPORTS'],include_external:false,include_self_edges:false},nodes:[{id:uuid(20),label:'Checkout',kind:'CLASS',iam_node_ids:[uuid(30)],locations:[loc(1)],member_count:0,method_count:0},{id:uuid(21),label:'Orders',kind:'CLASS',iam_node_ids:[uuid(31)],locations:[loc(2)],member_count:0,method_count:0}],edges:[{id:uuid(22),source_id:uuid(20),target_id:uuid(21),relation_kinds:['IMPORTS'],proofs:[{iam_edge_id:uuid(40),source_node_id:uuid(30),target_node_id:uuid(31),relation:'IMPORTS',locations:[loc(1)],provenance:[{source:'synthetic-fixture'}],occurrences:1,provenance_truncated:0}]}]},projection_statistics:{iam_nodes_input:2,iam_edges_input:1,graph_nodes:2,graph_edges:1,self_edges_removed:0,external_nodes_excluded:0,unmapped_nodes:0,unclassified_nodes_excluded:0,filtered_edges:0,unproven_edges:0},statistics:{scc_count:0,cyclic_scc_count:0,cycle_observation_count:0,cycle_findings:0,candidate_count_by_rule:{},metric_node_count:0,metrics_computed:[],metrics_skipped:[]},metrics:[],sccs:[],cycles:[],findings:[],candidates:[],conformance:null,diagnostics:[],reproducibility:{project_id:uuid(1),snapshot_fingerprint:null,iam_schema_version:'1.0',iam_fingerprint:'a'.repeat(64),graph_engine_version:'1.0.0',networkx_version:'3.4',configuration:{},configuration_fingerprint:'b'.repeat(64),projection_fingerprint:'c'.repeat(64),architecture_spec_fingerprint:null,canonical_float_decimal_places:12}};}
function context() {return {context_schema_version:'1.0',target_node_id:uuid(20),configuration:{strategy:'GRAPH_GUIDED',hop_count:1,direction:'BOTH',included_relations:['IMPORTS'],max_nodes:20,max_files:10,max_fragments:20,max_fragment_chars:4000,max_total_chars:20000,max_lines_per_fragment:120,before_lines:2,after_lines:2,max_line_bytes:65536,max_scan_bytes_per_file:33554432,include_spec:true,include_discovery:true,include_metrics:true,include_dependency_paths:true,token_budget:null},selected_nodes:[{node_id:uuid(20),distance:0,reason:'TARGET'}],fragments:[{evidence_id:'fragment-1',relative_path:'src/demo.ts',start_line:1,end_line:1,node_ids:[uuid(20)],language:'TYPESCRIPT',purpose:'TARGET',truncated:false,content_hash:'a'.repeat(64),chars:8}],evidence:[],context_fingerprint:'b'.repeat(64),context_chars:128,files:1,truncated:false,dropped_nodes:0,dropped_files:0,dropped_fragments:0,dropped_evidence:0,redactor_id:null,diagnostics:[]};}
function hybrid() {
 const policy={policy_id:'fixture-review',policy_version:'1.0',feature_schema_version:'fixture-features-v1',calibration_status:'UNCALIBRATED'};
 const completeness=Object.fromEntries(['iam_complete','parse_errors_present','unresolved_references','ambiguous_references','graph_complete','metrics_skipped','discovery_complete','discovery_unknown','discovery_ambiguous','ai_requested','ai_completed','ai_partial','ai_insufficient','context_truncated'].map(k=>[k,null]));
 const bundle={bundle_id:uuid(51),static:[],graph:[],graph_measurements:[],ai:[],discovery:[],context:[],completeness,alignments:[]};
 const vector={case_id:uuid(50),schema_version:'fixture-features-v1',values:[],fingerprint:hash({schema_version:'fixture-features-v1',values:[]})};
 return {result_schema_version:'hybrid-analysis-v1',cases:[{case_id:uuid(50),case_type:'GRAPH_STRUCTURAL',primary_subject_ids:[uuid(20)],related_subject_ids:[],subject_pairs:[],origin:'CALLER',rule_id:'ARCH101',anchor_ids:[uuid(52)],scope:'Synthetic review context',bundle_id:uuid(51)}],evidence_bundles:[bundle],feature_schema:{version:'fixture-features-v1',definitions:[]},features:[vector],decisions:[{decision_id:uuid(53),case_id:uuid(50),state:'REVIEW_REQUIRED',policy,calibration_status:'UNCALIBRATED',feature_fingerprint:vector.fingerprint,evidence_fingerprint:hash(bundle),reason_codes:['SYNTHETIC_REVIEW'],supporting_refs:[],contradicting_refs:[],missing_refs:[],confirmed_finding_ids:[],severity:null,confidence:null,model_score:null,model_artifact_fingerprint:null}],confirmed_finding_ids:[],review_case_ids:[uuid(50)],diagnostics:[],statistics:{cases_by_type:{GRAPH_STRUCTURAL:1},decisions_by_state:{REVIEW_REQUIRED:1},channel_cases:{},ai_decisions:{},agreements:0,conflicts:0,missing:1,omitted_candidate_cases:0},reproducibility:{max_candidate_cases:100,iam_fingerprint:'a'.repeat(64),iam_schema_version:'1.0',snapshot_fingerprint:null,static_engine_version:null,spec_fingerprint:null,graph_engine_version:null,graph_configuration_fingerprint:null,graph_projection_fingerprint:null,discovery_engine_version:null,discovery_configuration_fingerprint:null,ai_inputs:[],feature_schema_version:'fixture-features-v1',policy,hybrid_engine_version:'1.0.0'}};
}

test('Security result/report imports preserve supplied evidence without fabricating source code',()=>{
 const result=importArtifact(security());assert.equal(result.kind,'SECURITY');assert.equal(result.coverage[0].outcome,'DEFINITIVE_POSITIVE');assert.equal(result.findings[0].evidence[0].code,undefined);assert.equal(result.provenance.validation,'PROTOTYPE_STRUCTURE_ONLY');assert.equal(result.provenance.fingerprints_verified,false);
 assert.equal(importArtifact({domain:'SECURITY',result:security(),effectiveness_metrics_available:false}).kind,'SECURITY');
});
test('unknown roles and incomplete paths visibly break proof continuity',()=>{
 const f=securityFinding('POTENTIAL',false);f.flow.steps[1].role='UNKNOWN_FLOW';assert.equal(importArtifact(security([f])).findings[0].flow[1].state,'unknown');
 const result=importArtifact(security([securityFinding('POTENTIAL',false)]));assert.equal(result.findings[0].flow.filter(s=>s.state==='unknown').length,1);
});
test('Security execution failures outrank unsupported partition; no findings never means negative',()=>{
 const p=security([]);p.analyzed_rules=[];p.unsupported_rules=['SEC002'];p.analysis_metadata.coverage.SEC002={requested:true,supported:true,evaluated:false,status:'FAILED'};assert.equal(importArtifact(p).coverage[0].outcome,'FAILED');
 assert.equal(importArtifact(security([])).coverage[0].outcome,'PARTIAL');assert.equal(importArtifact(security([])).project.id,'unbound-security-artifact');
});
test('Security outcome considers every finding, independent of input order',()=>{
 const uncertain=securityFinding('POTENTIAL',false),supported=securityFinding();const p=security([uncertain,supported]);assert.equal(importArtifact(p).coverage[0].outcome,'DEFINITIVE_POSITIVE');p.findings.reverse();assert.equal(importArtifact(p).coverage[0].outcome,'DEFINITIVE_POSITIVE');
});
test('Security rejects malformed identity, evidence references, statuses and completeness',()=>{
 for(const change of [p=>p.findings[0].repository_id='bad',p=>p.findings[0].evidence_strength='99%',p=>p.findings[0].evidence_refs.pop(),p=>p.findings[0].evidence_refs[1]=p.findings[0].evidence_refs[0],p=>p.findings[0].sink_ref=uuid(99),p=>p.findings[0].evidence[0].related_evidence=[uuid(99)],p=>p.findings[0].evidence[0].namespace='ARCH',p=>p.findings[0].evidence[0].analysis_version='other',p=>p.findings[0].primary_source=source(100),p=>p.findings[0].flow.steps[1].role='UNKNOWN',p=>p.findings[0].flow.complete=false,p=>p.findings[0].flow.uncertainty=['UNKNOWN'],p=>p.findings[0].flow.steps[0].role='PROPAGATION',p=>p.analyzer_version='future-v99',p=>p.zero_findings_is_security_guarantee=true,p=>p.unknown=1,p=>p.analysis_metadata.coverage.SEC002.evaluated=false])rejects(security,change);
});
test('canonical field order does not affect source binding',()=>{const p=security();p.findings[0].primary_source=Object.fromEntries(Object.entries(p.findings[0].primary_source).reverse());assert.equal(importArtifact(p).kind,'SECURITY');});
test('source path and ranges must be canonical, with no fabricated missing location',()=>{
 for(const value of ['', ' ', './a.ts','a/../b.ts','a//b.ts','a/','/a.ts','C:/a.ts','a\\b.ts','a\u0000.ts'])assert.equal(safeRelative(value),false,value);
 assert.equal(safeRelative('src/checkout.ts'),true);
 for(const change of [p=>delete p.findings[0].evidence[0].source.location,p=>p.findings[0].evidence[0].source.location.file_path='../private.ts',p=>p.findings[0].evidence[0].source.location.start_column=0,p=>p.findings[0].evidence[0].source.location.end_line=1,p=>delete p.findings[0].evidence[0].source.location.end_column])rejects(security,change);
});
test('graph imports real relation names, proof provenance and counts',()=>{const p=graph();p.graph.edges[0].relation_kinds=['READS'];p.graph.edges[0].proofs[0].relation='READS';assert.equal(importArtifact(p).edges[0].relation,'READS');assert.equal(importArtifact(p).nodes[0].domain,'unclassified');});
test('graph rejects dangling edges, invented relations, missing/contradictory proof and counts',()=>{
 for(const change of [p=>p.graph.project_id='bad',p=>p.graph.nodes[0].locations[0].file_path='a/./b',p=>p.graph.edges[0].target_id=uuid(99),p=>p.graph.edges[0].relation_kinds=['CONTAINS'],p=>p.graph.edges[0].proofs=[],p=>p.graph.edges[0].proofs[0].provenance=[],p=>p.graph.edges[0].proofs[0].occurrences=2,p=>p.graph.edges[0].proofs[0].relation='CALLS',p=>p.graph.edges.push(clone(p.graph.edges[0])),p=>p.status='INVALID',p=>p.projection_statistics.graph_nodes=99,p=>p.findings=[securityFinding()]])rejects(graph,change);
});
test('context manifest requires bounded references, actual target and canonical fragment paths',()=>{
 assert.equal(importArtifact(context()).kind,'CONTEXT');
 for(const change of [p=>delete p.selected_nodes,p=>p.target_node_id=uuid(99),p=>p.fragments[0].relative_path='../hidden',p=>p.fragments[0].node_ids=[uuid(99)],p=>p.files=2,p=>p.configuration.max_fragment_chars=1,p=>p.context_chars=20001,p=>p.fragments[0].end_line=0,p=>p.evidence=[{evidence_id:'fragment-1',kind:'DEPENDENCY',subject_node_ids:[uuid(20)],data:{}}]])rejects(context,change);
 assert.throws(()=>importArtifact({context_schema_version:'1.0'}),/INVALID_ARTIFACT/);
});
test('Hybrid manifests retain review decisions without promoting them to findings',()=>{const result=importArtifact(hybrid());assert.equal(result.kind,'HYBRID');assert.equal(result.findings.length,0);assert.equal(result.provenance.fingerprints_verified,false);});
test('Hybrid rejects missing correspondence, invented confirmation/severity/confidence',()=>{
 for(const change of [p=>p.decisions=[],p=>p.decisions[0].case_id=uuid(99),p=>p.evidence_bundles[0].bundle_id=uuid(99),p=>p.features[0].schema_version='other',p=>p.decisions[0].state='CONFIRMED_DETERMINISTIC',p=>p.decisions[0].severity='HIGH',p=>p.decisions[0].confidence={score:.9,status:'not_calibrated'},p=>p.confirmed_finding_ids=[uuid(99)],p=>p.review_case_ids=[uuid(99)],p=>p.cases[0].rule_id='SEC002'])rejects(hybrid,change);
 assert.throws(()=>importArtifact({result_schema_version:'hybrid-analysis-v1',cases:[],decisions:[],evidence_bundles:[]}),/INVALID_ARTIFACT/);
});
test('unsupported, excessive and hostile input consistently produces an artifact error',()=>{
 for(const p of [null,[],{},42,{context_schema_version:'2.0'},JSON.parse('{"__proto__":{}}'),{x:Infinity},{x:'x'.repeat(50001)}])assert.throws(()=>importArtifact(p),/INVALID_ARTIFACT/);
 const cycle={};cycle.x=cycle;assert.throws(()=>importArtifact(cycle),/INVALID_ARTIFACT/);
});
test('source plan validates source kind, quotes shell literals and rejects credentials/traversal',()=>{
 assert.equal(validateGit('https://github.com/example/project','main'),true);
 for(const url of ['http://github.com/x/y','https://user:pass@github.com/x/y','https://localhost/x','https://127.0.0.1/x','https://example.com/x?q=1'])assert.equal(validateGit(url),false);
 assert.equal(validatePath('/tmp/../private'),false);assert.throws(()=>command('local; echo bad','/tmp/project'),/INVALID_SOURCE/);assert.throws(()=>command('local','/tmp/project','main'),/INVALID_SOURCE/);
 assert.equal(command('local',"/tmp/it's $(literal)"),"archguard graph analyze '/tmp/it'\\''s $(literal)' --source local --output result.json");
});

test('actual CLI exports import all declared architecture formats without demo residue',()=>{
 const expected={'architecture-graph.json':['GRAPH',3,0],'architecture-check.json':['CONFORMANCE',0,1],'architecture-composite.json':['ARCH_CHECK',3,2],'architecture-candidates.json':['GRAPH',3,3],'architecture-iam.json':['IAM',null,0],'architecture-discovery.json':['DISCOVERY',null,0],'architecture-context.json':['CONTEXT',0,0],'architecture-hybrid.json':['HYBRID',0,0]};
 for(const [name,[kind,nodes,findings]]of Object.entries(expected)){
  const raw=JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures',name),'utf8')),result=importArtifact(raw,name);
  assert.equal(result.kind,kind,name);if(nodes!==null)assert.equal(result.nodes.length,nodes,name);assert.equal(result.findings.length,findings,name);assert.equal(result.provenance.synthetic,false);assert.ok(result.findings.every(f=>!f.id.startsWith('demo')));
  if(name.includes('candidates'))assert.ok(result.findings.every(f=>f.status==='CANDIDATE'&&f.severity===null));
 }
});
test('composite, candidate, IAM and static artifacts reject inconsistent shape',()=>{
 const load=name=>JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures',name),'utf8'));
 for(const [name,change]of [['architecture-composite.json',p=>p.findings.pop()],['architecture-composite.json',p=>p.graph_result.graph=null],['architecture-candidates.json',p=>p.candidates[0].not_calibrated=false],['architecture-candidates.json',p=>p.candidates[0].subject_node_id=uuid(999)],['architecture-iam.json',p=>delete p.symbols],['architecture-check.json',p=>p.statistics.findings_total=33]])rejects(()=>load(name),change);
});
