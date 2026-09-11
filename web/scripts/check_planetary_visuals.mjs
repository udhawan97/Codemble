import assert from 'node:assert/strict';
import {mkdir, writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';
import {startDisposableCaptureServer} from './capture_support.mjs';
const root=fileURLToPath(new URL('../..',import.meta.url));
const projectRoot=process.env.CODEMBLE_VISUAL_ROOT || root;
const output=resolve(process.env.CODEMBLE_VISUAL_OUTPUT || '/tmp/codemble-planetary-visuals');
await mkdir(output,{recursive:true});
const server=await startDisposableCaptureServer({projectRoot,sourceRoot:process.env.CODEMBLE_VISUAL_SOURCE_ROOT || root,python:process.env.CODEMBLE_PYTHON});
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1440,height:900},deviceScaleFactor:1,reducedMotion:'reduce'});
const errors=[],captures=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
try{
 const graph=await (await page.request.get(server.url+'/api/graph')).json();
 await page.goto(server.url);
 const gate=page.getByRole('dialog',{name:'Choose your launch'});await gate.waitFor();
 await gate.getByRole('radio',{name:/Explore freely/}).check();await gate.getByRole('radio',{name:'I build software'}).check();await gate.getByRole('button',{name:'Open the galaxy'}).click();
 const settle=async()=>{await page.waitForTimeout(800);const skip=page.getByRole('button',{name:'Skip',exact:true});if(await skip.isVisible())await skip.click();await page.waitForTimeout(300)};
 const shot=async(name)=>{await settle();await page.screenshot({path:join(output,name+'.png')});captures.push(name)};
 const module=async(file)=>{await page.keyboard.press('Meta+k');const finder=page.locator('.module-finder[open]');await finder.getByRole('searchbox').fill(file);await page.keyboard.press('Enter');await page.locator('.orientation-copy--system').waitFor();await settle()};
 const study=async()=>{await page.getByRole('application').focus();await page.keyboard.press('ArrowRight');await page.keyboard.press('Enter');await page.locator('.study-preview').waitFor();await settle()};
 await shot('galaxy');
 if(process.env.CODEMBLE_VISUAL_ROUTES_ONLY){
  const file='tests/fixtures/csharp_sample/src/Program.cs';
  const nodes=new Map(graph.nodes.map(n=>[n.id,n]));
  const routes=graph.edges.filter(e=>e.kind==='call'&&!e.external&&nodes.get(e.src)?.file===file&&nodes.get(e.dst)?.file===file);
  assert.ok(routes.some(e=>e.certain)&&routes.some(e=>!e.certain),'scene contains certain and possible real-parser routes');
  await module(file);await shot('possible-and-certain-routes');
  await page.evaluate(()=>document.querySelector('.galaxy-frame').style.filter='grayscale(1)');await shot('possible-and-certain-greyscale');
 }else if(!process.env.CODEMBLE_VISUAL_BASELINE_ONLY){
  for(const language of ['python','javascript','typescript','go','java','rust','csharp','ruby','php']){
   const modules=graph.nodes.filter(n=>n.kind==='module'&&n.language===language&&!n.partial);
   const selected=modules.find(n=>n.file.includes('fixtures')&&graph.nodes.some(c=>c.region===n.region&&c.kind==='class')) || modules.find(n=>n.file.includes('fixtures')&&graph.nodes.filter(c=>c.region===n.region).length>2) || modules.find(n=>graph.nodes.filter(c=>c.region===n.region).length>2);
   assert.ok(selected,language+' has a rendered real-parser system');await module(selected.file);await shot('language-'+language);
  }
  await module(graph.nodes.find(n=>n.partial&&n.kind==='module').file);await shot('partial');
  await module('codemble/__init__.py');await shot('module-only');
  await module('codemble/cli.py');await shot('system-ununderstood');
  await study();await shot('study-real-source');
  await page.evaluate(()=>document.querySelector('.galaxy-frame').style.filter='grayscale(1)');await shot('study-greyscale');await page.evaluate(()=>document.querySelector('.galaxy-frame').style.filter='');
  await page.setViewportSize({width:320,height:640});await shot('study-320');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'320px page does not bleed');
  await page.setViewportSize({width:1440,height:900});await page.evaluate(()=>document.documentElement.style.zoom='2');await shot('study-200-percent');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'200% page does not bleed');await page.evaluate(()=>document.documentElement.style.zoom='');
  await page.getByRole('button',{name:'Close',exact:true}).click();
  for(let i=0;i<3;i++){await page.getByRole('application').focus();await page.keyboard.press('ArrowRight');await page.keyboard.press('Enter');await page.locator('.study-preview').waitFor();await page.getByRole('button',{name:'Close',exact:true}).click()}
  await study();const last=await page.locator('.study-preview h1').innerText();await page.waitForTimeout(650);assert.equal(await page.locator('.study-preview h1').innerText(),last,'rapid arrivals preserve the final subject');await shot('study-last-selection');
  await page.getByRole('button',{name:'Close',exact:true}).click();
  const id='codemble.cli';const suite=await(await page.request.get(`${server.url}/api/regions/${id}/checks`)).json();
  for(const check of suite.checks){if(check.passed)continue;let passed=false;for(let mask=1;mask<2**check.options.length;mask++){const r=await page.request.post(`${server.url}/api/regions/${id}/checks/${encodeURIComponent(check.id)}`,{data:{selected_ids:check.options.filter((_,i)=>mask&(1<<i)).map(x=>x.id)}});if(r.ok()&&(await r.json()).correct){passed=true;break}}assert.ok(passed,'fixture check passes with parser-derived answers')}
  await page.reload();await settle();await module('codemble/cli.py');await shot('system-understood');
  const proven=await(await page.request.get(server.url+'/api/graph')).json();assert.ok(proven.regions.find(r=>r.id===id)?.understood,'amber screenshot follows actual check-owned understanding');
 }
 assert.deepEqual(errors,[]);
 await writeFile(join(output,'receipt.json'),JSON.stringify({status:'pass',browser:browser.version(),captures,errors},null,2)+'\n');
 console.log('planetary visual matrix passed',captures.length);
}finally{await browser.close();await server.stop()}
