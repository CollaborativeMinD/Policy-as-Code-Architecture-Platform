// Fail before opening a socket unless the reviewed local fixture bytes are active.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
const digest='13dd30ac3ddc65d1f7f25c51b6a2fd37158480acaa753bd9eef0ce244207cca3';
export function verifyFixture() {
  if(process.platform!=='linux' || process.arch!=='x64' || process.versions.node!=='24.22.1') {
    throw new Error('HMT_FIXTURE_RUNTIME_IDENTITY_MISMATCH');
  }
  for(const [name,version] of [['pglite','0.5.15'],['pglite-socket','0.2.18']]) {
    const entry=import.meta.resolve(`@electric-sql/${name}`);
    const manifest=JSON.parse(readFileSync(new URL('../package.json',entry),'utf8'));
    if(manifest.version!==version) throw new Error('HMT_FIXTURE_PACKAGE_IDENTITY_MISMATCH');
  }
  const entry=import.meta.resolve('@electric-sql/pglite');
  const bytes=readFileSync(new URL('./chunk-O74Z5DUS.js',entry));
  if(createHash('sha256').update(bytes).digest('hex')!==digest) {
    throw new Error('HMT_FIXTURE_CALLBACK_HASH_MISMATCH');
  }
}
