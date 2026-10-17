import { build } from 'esbuild';
import { spawnSync } from 'node:child_process';
const names=['adapter','automation','workflow-browser','workflow-ui','ieee','acm'];
await Promise.all(names.map(name=>build({entryPoints:[`extension/tests/${name}.test.ts`],outfile:`.tmp/${name}.test.mjs`,bundle:true,platform:'node',format:'esm',packages:'external'})));
const r=spawnSync(process.execPath,['--test',...names.map(name=>`.tmp/${name}.test.mjs`)],{stdio:'inherit'});process.exit(r.status??1);
