/** Visible-GPU comparison on the same parser-built, disposable code fixture. */
import assert from 'node:assert/strict';
import {mkdtemp, mkdir, rm, writeFile, readFile, readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {tmpdir, platform, release, arch} from 'node:os';
import {join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';
import {startDisposableCaptureServer} from './capture_support.mjs';
const root=fileURLToPath(new URL('../..',import.meta.url));
const baseline=process.env.CODEMBLE_GRAPHICS_BASELINE;
assert.ok(baseline,'CODEMBLE_GRAPHICS_BASELINE must identify the unmodified comparison checkout');
const output=resolve(process.env.CODEMBLE_GRAPHICS_OUTPUT || '/tmp/codemble-planetary-graphics');
const fixture=await mkdtemp(join(tmpdir(),'codemble-worlds-fixture-'));
await mkdir(output,{recursive:true});
await writeFile(join(fixture,'ordinary.py'),Array.from({length:12},(_,i)=>`def world_${i}(value):\n    """A deterministic graphics fixture."""\n    return ${i ? `world_${i-1}(value)` : "value"} + ${i}\n`).join('\n'));
await writeFile(join(fixture,'dense.py'),Array.from({length:250},(_,i)=>`def world_${i}(value):\n    return value + ${i}\n`).join('\n'));
const receipt={host:{platform:platform(),os:release(),arch:arch()},viewport:{width:1440,height:900,dpr:1},warmupMs:5000,sampleMs:15000,runs:[]};
try {
for(const workload of ['fixture','self-parse']){
for(const [name,projectRoot] of [['baseline',baseline],['candidate',root]]){
 const server=await startDisposableCaptureServer({projectRoot,sourceRoot:workload==='fixture'?fixture:baseline,python:process.env.CODEMBLE_PYTHON});
 const browser=await chromium.launch({headless:false});
 const page=await browser.newPage({viewport:{width:1440,height:900},deviceScaleFactor:1,reducedMotion:'no-preference'});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
 const digest=createHash('sha256');
 for(const dir of ['web/src','codemble/web_dist/assets'])for(const file of (await readdir(join(projectRoot,dir))).sort()){if(/\.(js|jsx|css)$/.test(file))digest.update(dir+'/'+file).update(await readFile(join(projectRoot,dir,file)))}
 const run={name,workload,revision:execFileSync('git',['-C',projectRoot,'rev-parse','HEAD'],{encoding:'utf8'}).trim(),graphicsDigest:digest.digest('hex'),browser:browser.version(),views:[],resources:[],errors};receipt.runs.push(run);
 await page.addInitScript(()=>{
   const sets={};
   for(const [create,destroy] of [['createBuffer','deleteBuffer'],['createTexture','deleteTexture'],['createProgram','deleteProgram'],['createFramebuffer','deleteFramebuffer'],['createRenderbuffer','deleteRenderbuffer']]){
     sets[create]=new Map();
     for(const Type of [WebGLRenderingContext,WebGL2RenderingContext]){
       const originalCreate=Type.prototype[create],originalDestroy=Type.prototype[destroy];
       Type.prototype[create]=function(...args){const item=originalCreate.apply(this,args);if(item)sets[create].set(item,this);if(!this.canvas.graphicsTracked){this.canvas.graphicsTracked=true;this.canvas.addEventListener('webglcontextlost',()=>{for(const resources of Object.values(sets))for(const [resource,context] of resources)if(context.canvas===this.canvas)resources.delete(resource)})}return item};
       Type.prototype[destroy]=function(item){sets[create].delete(item);return originalDestroy.call(this,item)};
     }
   }
   window.graphicsResources=()=>Object.fromEntries(Object.entries(sets).map(([key,value])=>[key,value.size]));
 });
 try{
 await page.goto(server.url);
 const gate=page.getByRole('dialog',{name:'Choose your launch'});await gate.waitFor();
 await gate.getByRole('radio',{name:/Explore freely/}).check();
 await gate.getByRole('radio',{name:'I build software'}).check();
 await gate.getByRole('button',{name:'Open the galaxy'}).click();
 const settle=async()=>{await page.waitForTimeout(500);const skip=page.getByRole('button',{name:'Skip',exact:true});if(await skip.isVisible())await skip.click()};
 const module=async(path)=>{await page.keyboard.press('Meta+k');const finder=page.locator('.module-finder[open]');await finder.getByRole('searchbox').fill(path);await page.keyboard.press('Enter');await page.locator('.orientation-copy--system').waitFor();await settle()};
 const study=async()=>{await page.getByRole('application').focus();await page.keyboard.press('ArrowRight');await page.keyboard.press('Enter');await page.locator('.study-preview').waitFor();await settle()};
 const sample=async(view)=>{
   await page.waitForTimeout(5000);
   const timings=await page.evaluate(()=>new Promise(resolve=>{const intervals=[];let first,last;function frame(t){first??=t;if(last!==undefined)intervals.push(t-last);last=t;if(t-first<15000)requestAnimationFrame(frame);else{intervals.sort((a,b)=>a-b);resolve({median:intervals[Math.floor(intervals.length*.5)],p95:intervals[Math.floor(intervals.length*.95)],frames:intervals.length})}}requestAnimationFrame(frame)}));
   run.views.push({view,...timings});await page.screenshot({path:join(output,`${workload}-${name}-${view}.png`)});console.log(workload,name,view,timings);
 };
 await module(workload==='fixture'?'ordinary.py':'codemble/cli.py');
 run.gpu=await page.evaluate(()=>{const gl=document.querySelector('.galaxy-canvas canvas')?.getContext('webgl2');const ext=gl?.getExtension('WEBGL_debug_renderer_info');return ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):'unavailable'});
 await sample('system');await study();await sample('study');
 await page.getByRole('button',{name:'Close',exact:true}).click();
 if(workload==='fixture'){await module('dense.py');await sample('dense')}
 if(name==='candidate' && workload==='fixture'){
   for(let i=0;i<10;i++){
     await page.getByRole('button',{name:'Back to galaxy',exact:true}).click();
     await module('ordinary.py');await study();
     await page.getByRole('button',{name:'Close',exact:true}).click();
     await page.getByRole('button',{name:'Map',exact:true}).click();await page.waitForTimeout(150);
     await page.getByRole('button',{name:'Galaxy',exact:true}).click();await page.waitForTimeout(550);
     run.resources.push(await page.evaluate(()=>window.graphicsResources()));
   }
   for(const key of Object.keys(run.resources.at(-1)))assert.equal(run.resources.at(-1)[key],run.resources[4][key],`${key} did not plateau`);
   await study();const selected=await page.locator('.study-preview h1').innerText();
   await page.emulateMedia({reducedMotion:'reduce'});await page.waitForTimeout(1500);await page.locator('.study-preview').waitFor();
   assert.equal(await page.locator('.study-preview h1').innerText(),selected,'live reduced motion preserves selection');
   const still=await page.locator('.galaxy-canvas').screenshot();await page.waitForTimeout(600);
   assert.ok(still.equals(await page.locator('.galaxy-canvas').screenshot()),'reduced motion freezes the rendered scene');
   await page.screenshot({path:join(output,'candidate-reduced-motion.png')});
 }
 assert.deepEqual(errors,[],'Browser/shader errors');
 }finally{await browser.close();await server.stop()}
}
}
for(const workload of ['fixture','self-parse'])for(const view of workload==='fixture'?['system','study','dense']:['system','study']){
 const before=receipt.runs.find(r=>r.name==='baseline'&&r.workload===workload).views.find(x=>x.view===view);
 const after=receipt.runs.find(r=>r.name==='candidate'&&r.workload===workload).views.find(x=>x.view===view);
 for(const metric of ['median','p95'])assert.ok(after[metric] <= before[metric]*1.25+2,`${workload} ${view}: ${metric} regression ${before[metric]} -> ${after[metric]}`);
 assert.ok(after.p95 < (view==='dense'?100:50),`${view}: p95 too slow`);
}
receipt.status='pass';
} catch(error){receipt.status='fail';receipt.failure=error.stack;process.exitCode=1;
} finally{await writeFile(join(output,'receipt.json'),JSON.stringify(receipt,null,2)+'\n');await rm(fixture,{recursive:true,force:true})}
console.log(receipt.status,receipt.failure??'');
