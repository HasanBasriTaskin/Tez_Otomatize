import { generateKeyPairSync, createHash } from 'node:crypto';
import { writeFileSync, existsSync } from 'node:fs';
if (!existsSync('product.json')) {
  const { publicKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
  const der = publicKey.export({ type: 'spki', format: 'der' });
  const id = [...createHash('sha256').update(der).digest('hex').slice(0,32)].map(c=>String.fromCharCode(97+parseInt(c,16))).join('');
  writeFileSync('product.json', JSON.stringify({ extension_id:id, public_key:der.toString('base64'), host_name:'com.literaturkayit.host' },null,2));
}
