'use strict';
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const base=process.env.ARCHGUARD_URL||'http://127.0.0.1:8791',out=process.env.ARCHGUARD_EVIDENCE_DIR||'/tmp/archguard-workflow';
(async()=>{
 const browser=await chromium.launch(),p=await browser.newPage({viewport:{width:1440,height:900}}),errors=[],checks=[];
 p.on('pageerror',e=>errors.push(e.message));
 const check=async(name,fn)=>{await fn();checks.push(name);console.log('PASS',name)};
 await p.goto(base);await p.waitForFunction(()=>AG.product.projects.length>=2);
 const project=await p.evaluate(()=>AG.product.projects.find(x=>!x.architecture_available));assert.ok(project);
 await check('Direct project options: no missing-spec failure; selection and security choice survive rerender',async()=>{
  await p.locator('[data-product-project]').selectOption(project.id);
  assert.equal(await p.locator('[data-product-architecture]').isChecked(),false);assert.equal(await p.locator('[data-product-architecture]').isDisabled(),true);
  await p.locator('[data-product-security]').uncheck();await p.locator('#language').click();assert.equal(await p.locator('[data-product-security]').isChecked(),false);assert.equal(await p.locator('[data-product-project]').inputValue(),project.id);
  await p.locator('[data-product-security]').check();
 });
 let posts=0;
 p.on('request',r=>{if(r.method()==='POST'&&new URL(r.url()).pathname==='/api/product/jobs')posts++});
 await check('Double activation starts one real analysis; missing architecture.yaml is optional',async()=>{
  await p.locator('[data-product="run"]').evaluate(b=>{b.click();b.click()});await p.waitForFunction(()=>AG.state.dataset.kind==='PRODUCT');
  assert.equal(posts,1);assert.equal(await p.evaluate(()=>AG.state.dataset.nodes.length),4);assert.equal(await p.evaluate(()=>AG.state.dataset.raw.classification),null);
 });
 await check('Project choices remain selected when configuring another run',async()=>{
  await p.locator('[data-product="configure"]').first().click();assert.equal(await p.locator('dialog [data-product-project]').inputValue(),project.id);assert.equal(await p.locator('dialog [data-product-architecture]').isChecked(),false);await p.keyboard.press('Escape');
 });
 await check('Cancel and restart ignore a delayed response from the previous analysis',async()=>{
  let release,seen;const captured=new Promise(resolve=>{seen=resolve});let held=false;
  await p.route('**/api/product/jobs/*',async route=>{if(route.request().method()==='GET'&&!held){held=true;const response=await route.fetch();release=()=>route.fulfill({response});seen();}else await route.continue();});
  await p.locator('[data-product="configure"]').first().click();await p.locator('dialog [data-product="run"]').click();await captured;
  const first=await p.evaluate(()=>AG.product.job.id);await p.locator('[data-product="cancel"]').click();await p.waitForFunction(()=>['CANCELLED','READY'].includes(AG.product.job.status));
  await p.locator('[data-product="configure"]').first().click();await p.locator('dialog [data-product="run"]').click();await p.waitForFunction(first=>AG.product.job.id!==first,first);
  const second=await p.evaluate(()=>AG.product.job.id);await release();await p.waitForFunction(()=>AG.state.dataset.kind==='PRODUCT');assert.equal(await p.evaluate(()=>AG.product.job.id),second);assert.equal(await p.evaluate(()=>AG.product.job.status),'READY');await p.unroute('**/api/product/jobs/*');
 });
 await check('Saved-result deletion requires a confirmation; cancel preserves the result',async()=>{
  await p.locator('nav [data-view="runs"]').click();const before=await p.locator('.product-saved article').count();
  await p.locator('[data-product="delete"]').first().click();await p.locator('dialog [data-action="close-dialog"]').click();assert.equal(await p.locator('.product-saved article').count(),before);
  // Delete only this test's newly generated result, never an unrelated saved run.
  const id=await p.evaluate(()=>AG.product.job.id);
  await p.locator('[data-product="delete"][data-id="'+id+'"]').click();await p.locator('[data-product="delete-confirm"]').click();await p.waitForFunction(id=>!AG.product.saved.some(x=>x.id===id),id);assert.equal(await p.locator('.product-saved article').count(),before-1);
 });
 await check('Storage limit explains recovery and leaves Run usable after rejection',async()=>{
  await p.locator('[data-product="configure"]').first().click();await p.route('**/api/product/jobs',route=>route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({detail:'RESULT_STORAGE_LIMIT'})}));
  await p.locator('dialog [data-product="run"]').click();await p.waitForFunction(()=>AG.product.error==='RESULT_STORAGE_LIMIT');assert.match(await p.locator('#toast').innerText(),/20/);assert.equal(await p.locator('dialog [data-product="run"]').isDisabled(),false);await p.unroute('**/api/product/jobs');await p.keyboard.press('Escape');
 });
 await check('Offline startup reconnects successfully without reloading the page',async()=>{
  const q=await browser.newPage();await q.route('**/api/product/**',r=>r.abort());await q.goto(base);await q.waitForFunction(()=>AG.product.error==='GATEWAY_UNAVAILABLE');assert.ok(await q.locator('[data-product="reconnect"]').isVisible());await q.unroute('**/api/product/**');await q.locator('[data-product="reconnect"]').click();await q.waitForFunction(()=>AG.product.projects.length>=2);assert.equal(await q.locator('[data-product="run"]').isDisabled(),false);await q.close();
 });
 assert.deepEqual(errors,[]);await browser.close();fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'workflow-report.json'),JSON.stringify({checks,passed:checks.length,failed:0,jsErrors:errors},null,2)+'\n');
})().catch(e=>{console.error(e);process.exit(1)});
