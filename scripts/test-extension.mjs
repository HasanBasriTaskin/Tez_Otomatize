import { build } from 'esbuild';
import { spawnSync } from 'node:child_process';
await build({entryPoints:['extension/tests/adapter.test.ts'],outfile:'.tmp/adapter.test.mjs',bundle:true,platform:'node',format:'esm',packages:'external'});
const r=spawnSync(process.execPath,['--test','.tmp/adapter.test.mjs'],{stdio:'inherit'});process.exit(r.status??1);
