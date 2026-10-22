import {mkdirSync,readFileSync,writeFileSync,copyFileSync} from 'node:fs';
const dest='deploy/site/dist';mkdirSync(dest,{recursive:true});
for(const name of ['index.html','style.css','app.js'])copyFileSync('deploy/site/'+name,dest+'/'+name);
const read=name=>JSON.parse(readFileSync('docs/results/'+name,'utf8'));
writeFileSync(dest+'/proof.json',JSON.stringify({analysis:read('analysis.json'),canary:read('canary.json'),supply:read('supply.json'),recording:read('demo-probe.json')}));
for(const name of ['demo.webm','console-desktop.png'])copyFileSync('docs/results/'+name,dest+'/'+name);
console.log('Built public evidence from measured local runs. Interactive API is not hosted.');
