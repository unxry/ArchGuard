'use strict';
(() => {
 const A=window.AG;
 const M=A.motion={quality:['full','restrained','off'].includes(A.pref.get('scene-quality','full'))?A.pref.get('scene-quality','full'):'full',flow:A.pref.get('edge-flow','on')==='on',speed:Number(A.pref.get('flow-speed','1'))||1,scopes:new Set(),seen:new Set(),datasetIds:new WeakMap(),nextId:0};
 Object.defineProperties(M,{enabled:{get:()=>A.state.motion&&M.quality!=='off'&&!A.reduced.matches},rich:{get:()=>M.enabled&&M.quality==='full'}});
 M.key=()=>{const d=A.state.dataset;if(!M.datasetIds.has(d))M.datasetIds.set(d,++M.nextId);return [M.datasetIds.get(d),A.state.view,A.state.size,A.state.cluster,A.state.clusterPage].join(':')};
 class Scope{
  constructor(host){this.host=host;this.animations=new Set();this.closed=false;if(M.enabled)M.scopes.add(this)}
  animate(node,keyframes,options={}){if(this.closed||!M.enabled||document.hidden)return null;const a=node.animate(keyframes,{easing:'cubic-bezier(.22,1,.36,1)',...options});this.animations.add(a);a.finished.then(()=>this.animations.delete(a)).catch(()=>this.animations.delete(a));return a}
  after(ms,fn){const a=this.animate(this.host,[{opacity:1},{opacity:1}],{duration:ms});if(a)a.finished.then(()=>{if(!this.closed)fn()}).catch(()=>{});else if(!this.closed)fn()}
  pause(){for(const a of this.animations)if(a.playState==='running')a.pause()}
  resume(){if(!M.enabled)return;for(const a of this.animations)if(a.playState==='paused')a.play()}
  dispose(){this.closed=true;for(const a of this.animations)a.cancel();this.animations.clear();M.scopes.delete(this)}
 }
 M.Scope=Scope;
 M.refresh=()=>{document.documentElement.dataset.motion=M.enabled?M.quality:'off';if(!M.enabled){for(const scope of [...M.scopes])scope.dispose();A.graph?.stop();cancelAnimationFrame(A.graph?.cameraFrame);cancelAnimationFrame(A.graph?.parallaxFrame);if(A.graph)A.graph.parallaxFrame=0;A.graph?.settle?.()}else if(!M.flow)A.graph?.stop()};
 document.addEventListener('visibilitychange',()=>{for(const scope of M.scopes)document.hidden?scope.pause():scope.resume()});
 A.reduced.addEventListener('change',M.refresh);M.refresh();
})();
