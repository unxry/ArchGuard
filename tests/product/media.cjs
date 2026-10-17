'use strict';
const {chromium}=require('playwright'),path=require('node:path');
(async()=>{
 const out=path.resolve('docs/product/previews'),b=await chromium.launch(),c=await b.newContext({viewport:{width:1920,height:1080},recordVideo:{dir:out,size:{width:1920,height:1080}}}),p=await c.newPage(),v=p.video();
 await p.goto(process.env.ARCHGUARD_URL||'http://127.0.0.1:8790');await p.waitForFunction(()=>AG.product.projects.length);await p.waitForTimeout(1300);
 await p.locator('main [data-product="configure"]').first().click();await p.waitForTimeout(1200);await p.locator('dialog [data-product="run"]').click();await p.waitForFunction(()=>AG.state.dataset.kind==='PRODUCT',{},{timeout:15000});await p.waitForTimeout(5400);
 const id=await p.evaluate(()=>AG.state.dataset.findings.find(f=>f.rule==='ARCH002').nodeIds[0]);await p.locator('[data-gnode="'+id+'"]').click();await p.locator('.hero-actions [data-scene-enter]').hover();await p.waitForTimeout(800);await p.locator('.hero-actions [data-scene-enter]').click();await p.waitForTimeout(1400);
 await p.locator('[data-trace-chain]').click();await p.waitForTimeout(3400);await p.locator('#inspector [data-finding]').first().click();await p.waitForTimeout(1100);await p.locator('.source-code').scrollIntoViewIfNeeded();await p.waitForTimeout(2100);await p.locator('[data-action="finding-graph"]').click();await p.waitForTimeout(1600);
 await p.locator('nav [data-view="security"]').click();await p.locator('[data-rule="SEC002"]').click();await p.waitForTimeout(1700);await p.locator('.source-code').scrollIntoViewIfNeeded();await p.waitForTimeout(1400);await p.locator('nav [data-view="models"]').click();await p.waitForTimeout(1300);await p.locator('nav [data-view="runs"]').click();await p.waitForTimeout(1500);
 await c.close();await v.saveAs(path.join(out,'real-workflow.webm'));await v.delete();await b.close();console.log('Recorded real workflow');
})().catch(e=>{console.error(e);process.exit(1)});
