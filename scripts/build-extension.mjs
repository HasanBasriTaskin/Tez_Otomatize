import { build } from 'esbuild';
import { mkdir, readFile, writeFile, copyFile } from 'node:fs/promises';
const product=JSON.parse(await readFile('product.json','utf8'));
await mkdir('extension/dist',{recursive:true});
for(const name of ['worker','content','bind','popup','manager','refine']) {
  await build({entryPoints:[`extension/src/${name}.ts`],outfile:`extension/dist/${name}.js`,bundle:true,
    format:name==='worker'?'esm':'iife',target:'chrome120',define:{HOST_NAME:JSON.stringify(product.host_name)}});
}
for(const file of ['bind.html','popup.html','manager.html','refine.html','style.css'])await copyFile('extension/public/'+file,'extension/dist/'+file);
await writeFile('extension/dist/manifest.json',JSON.stringify({manifest_version:3,name:'Literatür Kayıt Asistanı',version:'0.2.0',
  description:'Windows ekran görüntüsünü aktif arama sekmesi ve yerel arama kaydıyla eşleştirir.',minimum_chrome_version:'120',
  key:product.public_key,permissions:['activeTab','scripting','storage','nativeMessaging','alarms','contextMenus','webNavigation'],
  optional_host_permissions:['https://*/*','http://localhost/*','http://127.0.0.1/*'],
  background:{service_worker:'worker.js',type:'module'},action:{default_popup:'popup.html',default_title:'Literatür kayıt'},
  options_page:'manager.html',incognito:'not_allowed',content_security_policy:{extension_pages:"script-src 'self'; object-src 'none'"}},null,2));
console.log('Eklenti hazır: extension/dist. Kimlik: '+product.extension_id);
