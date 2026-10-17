'use strict';
window.AG = window.AG || {};
(() => {
 const A=window.AG;
 A.$=id=>document.getElementById(id);
 A.escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 A.pref={get(key,fallback){try{return localStorage.getItem('ag-v2-'+key)||fallback}catch{return fallback}},set(key,value){try{localStorage.setItem('ag-v2-'+key,value)}catch{}}};
 A.state={locale:A.pref.get('locale','ru'),view:'projects',mode:'LOCAL_DEMO',dataset:null,selected:null,selectedNode:null,selectedRule:'SEC002',query:'',namespace:'all',status:'all',severity:'all',modelTab:'rules',run:null,runs:[],motion:A.pref.get('motion','on')==='on',size:12,cluster:null,clusterPage:0,relation:'all',direction:'both',inspector:true,sourceIndex:0,service:null};
 A.reduced=matchMedia('(prefers-reduced-motion: reduce)');
 A.emit=(name,detail)=>document.dispatchEvent(new CustomEvent('ag:'+name,{detail}));
 A.announce=text=>{A.$('liveRegion').textContent=text};
 let toastTimer;
 A.toast=text=>{clearTimeout(toastTimer);A.$('toast').textContent=text;A.$('toast').hidden=false;toastTimer=setTimeout(()=>A.$('toast').hidden=true,3200);A.announce(text)};
 A.download=(name,value)=>{const link=document.createElement('a'),url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
 A.isConfirmed=f=>['CONFIRMED','CONFIRMED_PATTERN','SUPPORTED'].includes(f.status);
 A.record=()=>A.state.dataset.findings.find(f=>f.id===A.state.selected)||A.state.dataset.findings[0];
 A.setDemo=(name)=>{A.state.dataset=structuredClone(A.demo);if(name)A.state.dataset.project.name=name;A.state.mode='LOCAL_DEMO';A.state.selected=A.demo.findings[0].id;A.state.selectedNode=null;A.state.size=12;A.state.cluster=null;A.state.query='';A.state.clusterPage=0;A.state.namespace=A.state.status=A.state.severity=A.state.relation='all';};
 A.newRun=(config={})=>({id:'demo-run-'+(A.state.runs.length+1),time:new Date().toISOString(),mode:'LOCAL_DEMO',projectId:A.state.dataset.project.id,status:'PARTIAL',findings:A.state.dataset.findings.map(f=>f.id),config});
})();
