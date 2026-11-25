// The single backend needs a distinct protocol namespace for each logical client.
// SQL and parameter payloads are preserved byte-for-byte.
const owned = new Map();
function frame(kind, payload) {
  const header=Buffer.alloc(5);
  header[0]=kind;
  header.writeInt32BE(payload.length+4,1);
  return Buffer.concat([header,payload]);
}
function rewriteName(message, offset, handlerId, track=false) {
  const end=message.indexOf(0,offset);
  if(end<0) throw new Error('FIXTURE_UNTERMINATED_PROTOCOL_NAME');
  if(end===offset) return {message,next:end+1};
  const original=message.subarray(offset,end);
  const name=Buffer.concat([Buffer.from(`hmt${handlerId}_`),original]);
  if(track) {
    const entries=owned.get(handlerId) ?? new Set();
    entries.add(name.toString('utf8'));
    owned.set(handlerId,entries);
  }
  const payload=Buffer.concat([message.subarray(5,offset),name,message.subarray(end)]);
  return {message:frame(message[0],payload),next:offset+name.length+1};
}
export function namespaced(message, handlerId) {
  const buffer=Buffer.from(message);
  if(buffer[0]===80) return rewriteName(buffer,5,handlerId,true).message;
  if(buffer[0]===66) {
    const statementOffset=buffer.indexOf(0,5)+1;
    if(statementOffset<6) throw new Error('FIXTURE_UNTERMINATED_PORTAL_NAME');
    return rewriteName(buffer,statementOffset,handlerId).message;
  }
  if((buffer[0]===67 || buffer[0]===68) && buffer[5]===83) {
    return rewriteName(buffer,6,handlerId).message;
  }
  return buffer;
}
export function releaseStatements(handlerId) {
  const entries=owned.get(handlerId) ?? new Set();
  owned.delete(handlerId);
  const messages=[];
  for(const name of entries) messages.push(frame(67,Buffer.from(`S${name}\0`)));
  if(messages.length) messages.push(frame(83,Buffer.alloc(0)));
  return Buffer.concat(messages);
}
