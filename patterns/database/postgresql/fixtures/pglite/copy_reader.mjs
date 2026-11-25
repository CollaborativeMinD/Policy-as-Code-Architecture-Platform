// Bound the synchronous Linux read used only after PostgreSQL's CopyInResponse.
import { readSync } from 'node:fs';
const waitCell=new Int32Array(new SharedArrayBuffer(4));
export function copyReader(handler) {
  const deadline=Date.now()+5000;
  let remaining=64*1024*1024;
  return (limit)=> {
    const length=Math.min(limit,remaining);
    if(length<1 || Date.now()>=deadline) {
      console.error('HMT_FIXTURE_COPY_INPUT_BOUND');
      return Buffer.alloc(0);
    }
    if(handler.messageBuffer.length) {
      const part=handler.messageBuffer.subarray(0,length);
      handler.messageBuffer=handler.messageBuffer.subarray(part.length);
      remaining-=part.length;
      return part;
    }
    const fd=handler.socket?._handle?.fd;
    if(!Number.isInteger(fd) || fd<0) throw new Error('HMT_FIXTURE_SOCKET_FD_UNAVAILABLE');
    const buffer=Buffer.alloc(length);
    for(let attempt=0;attempt<5000 && Date.now()<deadline;attempt++) {
      try {
        const count=readSync(fd,buffer,0,length,null);
        remaining-=count;
        return buffer.subarray(0,count);
      } catch(error) {
        if(!['EAGAIN','EWOULDBLOCK','EINTR'].includes(error.code)) throw error;
        Atomics.wait(waitCell,0,0,1);
      }
    }
    console.error('HMT_FIXTURE_COPY_READ_DEADLINE');
    return Buffer.alloc(0);
  };
}
