import { build } from 'esbuild';
import { mkdir, readFile, writeFile, copyFile, realpath, rm } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
const root=await realpath(join(dirname(fileURLToPath(import.meta.url)),'..'));
process.chdir(root);
const artifacts=join(root,'artifacts');
await mkdir(artifacts,{recursive:true});
if(await realpath(artifacts)!==artifacts)throw new Error('artifacts başka bir klasöre yönleniyor; temizlik yapılmadı.');
await rm(join(artifacts,'extension'),{recursive:true,force:true});
const product=JSON.parse(await readFile('product.json','utf8'));
const {version}=JSON.parse(await readFile('package.json','utf8'));
await mkdir('artifacts/extension',{recursive:true});
for(const name of ['worker','content','bind','popup','manager','refine']) {
  await build({entryPoints:[`extension/src/${name}.ts`],outfile:`artifacts/extension/${name}.js`,bundle:true,
    format:name==='worker'?'esm':'iife',target:'chrome120',define:{HOST_NAME:JSON.stringify(product.host_name)}});
}
for(const file of ['bind.html','popup.html','manager.html','refine.html','style.css'])await copyFile('extension/public/'+file,'artifacts/extension/'+file);
await writeFile('artifacts/extension/manifest.json',JSON.stringify({manifest_version:3,name:'Literatür Kayıt Asistanı',version,
  description:'Windows ekran görüntüsünü aktif arama sekmesi ve yerel arama kaydıyla eşleştirir.',minimum_chrome_version:'120',
  key:product.public_key,permissions:['activeTab','scripting','storage','nativeMessaging','alarms','contextMenus','webNavigation'],
  optional_host_permissions:['https://*/*','http://localhost/*','http://127.0.0.1/*'],
  background:{service_worker:'worker.js',type:'module'},action:{default_popup:'popup.html',default_title:'Literatür kayıt'},
  options_page:'manager.html',incognito:'not_allowed',content_security_policy:{extension_pages:"script-src 'self'; object-src 'none'"}},null,2));
console.log('Eklenti hazır: artifacts/extension. Kimlik: '+product.extension_id);
