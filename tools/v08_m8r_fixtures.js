"use strict";
// Qualification-only signer. Private keys are ephemeral unless explicitly saved
// to an ignored local directory; no production credentials or device operations.
const crypto=require('node:crypto'),fs=require('node:fs'),path=require('node:path');
const wire=require('./v08_m6b_security'),vectors=require('./v08_crypto_vectors.json');
function create(privateKey){
 const publicKey=crypto.createPublicKey(privateKey),j=publicKey.export({format:'jwk'});
 const point=Buffer.concat([Buffer.from([4]),Buffer.from(j.x,'base64url'),Buffer.from(j.y,'base64url')]).toString('hex');
 const epoch=0x1122334455667788n,alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-';let serial=0;
 function nonce(){let n=++serial,s='';for(let i=0;i<22;++i){s=alphabet[n%64]+s;n=Math.floor(n/64);}return s;}
 function record(op,seq,payload=Buffer.alloc(0),index=0){const b=Buffer.alloc(40);b.write('STV7');b[4]=2;b[5]=op;b.writeBigUInt64BE(epoch,8);b.writeBigUInt64BE(epoch,16);b.writeBigUInt64BE(BigInt(seq),24);b.writeUInt16BE(index,32);b.writeUInt16BE(payload.length,34);b.writeUInt32BE(wire.crc32(payload),36);return Buffer.concat([b,payload]);}
 function signed(op,body){const n=nonce(),target='/api/v2/bridge/media/'+['','begin','tile','commit','abort'][op]+'/'+body.subarray(16,32).toString('hex');const fields={host:'tv.test','content-type':wire.CONTENT_TYPE,'content-length':String(body.length),'content-digest':wire.canonicalDigest(body)},si=wire.signatureInput('media-test',n),request={method:'POST',target,fields,signatureInput:si};const sig=crypto.sign('sha256',wire.signatureBase(request),{key:privateKey,dsaEncoding:'ieee-p1363'}).toString('base64');
  if(!crypto.verify('sha256',wire.signatureBase(request),{key:publicKey,dsaEncoding:'ieee-p1363'},Buffer.from(sig,'base64')))throw Error('independent signature check');
  const header='POST '+target+' HTTP/1.1\r\nHost: tv.test\r\nContent-Type: '+fields['content-type']+'\r\nContent-Length: '+body.length+'\r\nContent-Digest: '+fields['content-digest']+'\r\nConnection: close\r\nSignature-Input: '+si+'\r\nSignature: sig1=:'+sig+':\r\n\r\n';return {header,body_hex:body.toString('hex'),nonce:n,op};}
 function transaction(w,seq){
  const image=Buffer.alloc(w*w*2,0xa5),tx=record(3,seq).subarray(16,32).toString('hex');
  const meta={album:'Album',artist:'Artist',cover_len:image.length,cover_sha256:w?crypto.createHash('sha256').update(image).digest('hex'):null,duration:60,height:w,pixel_format:w?'RGB565LE':'NONE',position:0,source:'fixture',state:'PLAYING',tile_count:image.length/512,title:'Test',track_key:'0'.repeat(64),tx,v:2,width:w};
  const packets=[signed(1,record(1,seq,Buffer.from(JSON.stringify(meta))))];
  for(let t=0;t<image.length/512;++t)packets.push(signed(2,record(2,seq,image.subarray(t*512,(t+1)*512),t)));
  packets.push(signed(3,record(3,seq)),signed(4,record(4,seq)));
  let denial=null;
  if(w){const bad=record(2,seq,image.subarray(0,512));bad[36]^=1;
   if(bad.readUInt32BE(36)===wire.crc32(bad.subarray(40)))throw Error('CRC negative fixture is valid');
   const crcPacket=signed(2,bad);
   if(!crcPacket.header.includes('Content-Digest: '+wire.canonicalDigest(bad)+'\r\n'))throw Error('CRC negative fixture digest');
   denial={wrong_crc:crcPacket,abort_after_wrong_crc:signed(4,record(4,seq))};
  }
  return {width:w,sequence:seq,packets,denial};
 }
 const groups={},negative={};
 for(const w of [0,32,48]){
  const g=transaction(w,w+2);groups[w]=g.packets;if(w)negative[w]=g.denial;
 }
 // Fresh transactions for a future controlled run; never reuse the discarded
 // old key or an already consumed nonce. Each negative has its own Begin/Abort.
 const qualification=[];let sequence=100;
 for(const w of [0,32,48])for(const kind of ['commit','replacement','replacement','replacement','abort',...(w?['wrong_crc','interrupted']:[])]){
  const g=transaction(w,++sequence);let packets=g.packets.slice(0,-1);
  if(kind==='abort')packets=[g.packets[0],...(w?[g.packets[1]]:[]),g.packets.at(-1)];
  if(kind==='wrong_crc')packets=[g.packets[0],g.denial.wrong_crc,g.denial.abort_after_wrong_crc];
  if(kind==='interrupted')packets=[g.packets[0],g.packets[1],g.packets.at(-1)];
  qualification.push({width:w,sequence:g.sequence,kind,packets,...(kind==='interrupted'?{partial_tile_bytes:100}:{})});
 }
 const rj=crypto.createPublicKey(vectors.public_key_pem).export({format:'jwk'});
 return {kind:'QUALIFICATION_ONLY_NO_PRODUCTION_KEY',public_point:point,epoch:epoch.toString(16),retained_key:Buffer.concat([Buffer.from([4]),Buffer.from(rj.x,'base64url'),Buffer.from(rj.y,'base64url')]).toString('hex'),synthetic_key:point,retained:vectors.entries,groups,negative,qualification};
}
module.exports={create};
if(require.main===module){
 const {privateKey}=crypto.generateKeyPairSync('ec',{namedCurve:'prime256v1'});const fixtures=create(privateKey);
 if(process.argv[2]==='--qualification-out'){
  const out=path.resolve(process.argv[3]||'');const root=path.resolve(__dirname,'..');
  if(!out.startsWith(root+path.sep)||require('node:child_process').spawnSync('git',['check-ignore','--quiet',path.join(out,'signing-key.pem')],{cwd:root}).status!==0)throw Error('qualification output must be ignored and local');
  fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'signing-key.pem'),privateKey.export({format:'pem',type:'pkcs8'}),{flag:'wx',mode:0o600});fs.writeFileSync(path.join(out,'packets.json'),JSON.stringify(fixtures),{flag:'wx',mode:0o600});
  process.stdout.write(JSON.stringify({qualification_fixtures_created:true,private_material_local_and_ignored:true,widths:[0,32,48],image_Abort_and_independently_signed_wrong_CRC:true,device_contacts:0}));
 }else if(process.argv.length===2)process.stdout.write(JSON.stringify(fixtures));
 else throw Error('unexpected fixture option');
}
