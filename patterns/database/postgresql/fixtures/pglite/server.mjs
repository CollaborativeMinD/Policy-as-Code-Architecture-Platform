// Explicit Linux-local fixture repair. Production code never imports this file.
import { PGlite } from '@electric-sql/pglite';
import { PGLiteSocketServer } from '@electric-sql/pglite-socket';
import { parseArgs } from 'node:util';
import { copyReader } from './copy_reader.mjs';
import { verifyFixture } from './identity.mjs';
import { namespaced, releaseStatements } from './statement_namespace.mjs';
const {values} = parseArgs({options: {
  db: {type:'string',default:'memory://'},
  host: {type:'string',default:'127.0.0.1'},
  port: {type:'string',default:'5432'},
  'max-connections': {type:'string',default:'8'},
}});
if(values.host !== '127.0.0.1') throw new Error('FIXTURE_LOOPBACK_REQUIRED');
verifyFixture();
const db = new PGlite(values.db);
await db.waitReady;
const server = new PGLiteSocketServer({db,host:values.host,port:Number(values.port),maxConnections:Number(values['max-connections'])});
const originalExec=db.execProtocolRawStream.bind(db);
db.execProtocolRawStream=async(...args)=> {
  try { return await originalExec(...args); }
  finally { db._hmtFixtureReadMore=undefined; }
};
const originalEnqueue=server.queryQueue.enqueue.bind(server.queryQueue);
server.queryQueue.enqueue=(handlerId,message,onData)=> {
  let output=Buffer.alloc(0);
  return originalEnqueue(handlerId,namespaced(message,handlerId),(data)=> {
    output=Buffer.concat([output,Buffer.from(data)]);
    while(output.length>=5 && output.length>=output.readInt32BE(1)+1) {
      const size=output.readInt32BE(1)+1;
      const kind=output[0];
      if(kind===71) {
        const handler=[...server.handlers].find(item=>item.handlerId===handlerId);
        db._hmtFixtureReadMore=copyReader(handler);
      }
      if(kind===67 || kind===69 || kind===90) db._hmtFixtureReadMore=undefined;
      output=output.subarray(size);
    }
    onData(data);
  });
};
const originalClear=server.queryQueue.clearTransactionIfNeeded.bind(server.queryQueue);
server.queryQueue.clearTransactionIfNeeded=async(handlerId)=> {
  await originalClear(handlerId);
  const message=releaseStatements(handlerId);
  if(message.length) await originalEnqueue(handlerId,message,()=>{});
};
server.addEventListener('error',event=>console.error('HMT_FIXTURE_SERVER_ERROR',event.detail));
for(const signal of ['SIGTERM','SIGINT']) process.on(signal,async()=> {
  await server.stop();
  await db.close();
  process.exit(0);
});
await server.start();
console.log('HMT_PGLITE_FIXTURE_REPAIRED_COPY',server.getServerConn());
