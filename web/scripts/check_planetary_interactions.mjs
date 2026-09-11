/** Final interaction evidence: animated retargeting, live motion and zoom reflow. */
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';
import {startDisposableCaptureServer} from './capture_support.mjs';
const root=fileURLToPath(new URL('../..',import.meta.url));
const output=resolve(process.env.CODEMBLE_INTERACTION_OUTPUT || '/tmp/codemble-planetary-interactions');
await mkdir(output,{recursive:true});
const server=await startDisposableCaptureServer({projectRoot:root,sourceRoot:process.env.CODEMBLE_VISUAL_SOURCE_ROOT || root,python:process.env.CODEMBLE_PYTHON});
const browser=await chromium.launch({headless:false});
const page=await browser.newPage({viewport:{width:1440,height:900},deviceScaleFactor:1,reducedMotion:'no-preference'});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(server.url);
 const gate=page.getByRole('dialog',{name:'Choose your launch'});await gate.waitFor();
 await gate.getByRole('radio',{name:/Explore freely/}).check();await gate.getByRole('radio',{name:'I build software'}).check();await gate.getByRole('button',{name:'Open the galaxy'}).click();
 await page.waitForTimeout(500);const skip=page.getByRole('button',{name:'Skip',exact:true});if(await skip.isVisible())await skip.click();
 await page.keyboard.press('Meta+k');await page.locator('.module-finder[open]').getByRole('searchbox').fill('codemble/cli.py');await page.keyboard.press('Enter');await page.locator('.orientation-copy--system').waitFor();await page.waitForTimeout(1200);
 const selections=[],arrivalAtMs=[],began=Date.now();
 for(let i=0;i<3;i++){
  await page.getByRole('application').focus();await page.keyboard.press('ArrowRight');await page.keyboard.press('Enter');
  await page.locator('.study-preview h1').waitFor();selections.push(await page.locator('.study-preview h1').innerText());arrivalAtMs.push(Date.now()-began);
 }
 const retargetMs=Date.now()-began;assert.ok(new Set(selections).size>1,'multiple distinct real structures selected');
 await page.emulateMedia({reducedMotion:'reduce'});
 const preferenceAtMs=Date.now()-began;
 assert.ok(arrivalAtMs.slice(1).every((t,i)=>t-arrivalAtMs[i]<420),'selections overlap the 420ms arrival');
 assert.ok(preferenceAtMs-arrivalAtMs.at(-1)<420,'preference changes during the last arrival');
 await page.mouse.move(1200,150);
 await page.waitForTimeout(2500);
 assert.equal(await page.locator('.study-preview h1').innerText(),selections.at(-1),'last animated selection survives live motion preference change');
 const still=await page.locator('.galaxy-canvas').screenshot({path:join(output,'freeze-a.png')});await page.waitForTimeout(600);const next=await page.locator('.galaxy-canvas').screenshot({path:join(output,'freeze-b.png')});console.log({selections,arrivalAtMs,preferenceAtMs,motion:await page.evaluate(()=>matchMedia('(prefers-reduced-motion: reduce)').matches)});const freeze=await page.evaluate(async images=>{
  const pixels=await Promise.all(images.map(async data=>{const img=new Image();img.src=data;await img.decode();const canvas=document.createElement('canvas');canvas.width=img.width;canvas.height=img.height;const context=canvas.getContext('2d');context.drawImage(img,0,0);return context.getImageData(0,0,img.width,img.height).data}));
  let changedChannels=0,maxDelta=0;for(let i=0;i<pixels[0].length;i++){const delta=Math.abs(pixels[0][i]-pixels[1][i]);if(delta)changedChannels++;maxDelta=Math.max(maxDelta,delta)}
  return {changedChannels,maxDelta,totalChannels:pixels[0].length};
 },[still,next].map(buffer=>'data:image/png;base64,'+buffer.toString('base64')));
 // Permit only isolated one-level GPU rounding, never visible camera/body motion.
 assert.ok(freeze.maxDelta<=1 && freeze.changedChannels/freeze.totalChannels<=0.00001,`scene stays frozen after interruption: ${JSON.stringify(freeze)}`);
 await page.screenshot({path:join(output,'interrupted-arrival.png')});
 // 1440x900 at 200% browser zoom has a 720x450 CSS viewport. Changing the
 // effective viewport exercises media queries; CSS zoom alone does not.
 await page.setViewportSize({width:720,height:450});await page.waitForTimeout(300);
 const source=page.locator('.source-code');await source.scrollIntoViewIfNeeded();
 assert.ok(await source.isVisible(),'real source reachable at effective 200%');
 await page.screenshot({path:join(output,'zoom-source.png')});
 await page.getByRole('button',{name:'Close',exact:true}).click();
 await page.getByRole('button',{name:'Key',exact:true}).click();await page.getByLabel('Galaxy legend').waitFor();await page.getByLabel('Galaxy legend').focus();await page.keyboard.press('End');await page.screenshot({path:join(output,'zoom-key.png')});await page.getByRole('button',{name:'Key',exact:true}).click();await page.getByLabel('Galaxy legend').waitFor({state:'hidden'});
 await page.keyboard.press('Meta+k');await page.locator('.module-finder[open]').getByRole('searchbox').fill('codemble/cli.py');await page.screenshot({path:join(output,'zoom-find.png')});await page.keyboard.press('Escape');
 const menu=page.getByRole('button',{name:'Menu',exact:true});if(await menu.isVisible())await menu.click();
 await page.getByRole('button',{name:'Map',exact:true}).click();await page.locator('.map-view').waitFor();await page.screenshot({path:join(output,'zoom-map.png')});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'effective zoom has no document horizontal overflow');
 assert.deepEqual(errors,[]);
 await writeFile(join(output,'receipt.json'),JSON.stringify({status:'pass',browser:browser.version(),selections,retargetMs,arrivalAtMs,preferenceAtMs,freeze,zoomCssViewport:{width:720,height:450},reachable:['source','Key','Find','Map'],errors},null,2)+'\n');
 console.log('planetary interaction checks passed',retargetMs,preferenceAtMs);
}finally{await browser.close();await server.stop()}
