"use strict";
// One-shot synthetic qualification vectors. Private key stays in this process
// and is discarded after generation. No sender, provisioning or private export.
const crypto=require('node:crypto');
const wire=require('./v08_m6b_security');
const {publicKey,privateKey}=crypto.generateKeyPairSync('ec',{namedCurve:'prime256v1'});
const j=publicKey.export({format:'jwk'});
const public_point=Buffer.concat([Buffer.from([4]),Buffer.from(j.x,'base64url'),Buffer.from(j.y,'base64url')]).toString('hex');
const epoch=0x1122334455667788n,alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-';
let serial=0,sequence=0;
function nonce(){let n=++serial,s='';for(let i=0;i<22;++i){s=alphabet[n%64]+s;n=Math.floor(n/64);}return s;}
function record(op,seq,payload=Buffer.alloc(0),index=0){
 const h=Buffer.alloc(40);h.write('STV7');h[4]=2;h[5]=op;h.writeBigUInt64BE(epoch,8);h.writeBigUInt64BE(epoch,16);h.writeBigUInt64BE(BigInt(seq),24);
 h.writeUInt16BE(index,32);h.writeUInt16BE(payload.length,34);h.writeUInt32BE(wire.crc32(payload),36);return Buffer.concat([h,payload]);
}
function signed(op,seq,body){
 const n=nonce(),target='/api/v2/bridge/media/'+['','begin','tile','commit','abort'][op]+'/'+body.subarray(16,32).toString('hex');
 const fields={host:'tv.test','content-type':wire.CONTENT_TYPE,'content-length':String(body.length),'content-digest':wire.canonicalDigest(body)};
 const si=wire.signatureInput('media-test',n),request={method:'POST',target,fields,signatureInput:si};
 const sig=crypto.sign('sha256',wire.signatureBase(request),{key:privateKey,dsaEncoding:'ieee-p1363'}).toString('base64');
 const header='POST '+target+' HTTP/1.1\r\nHost: tv.test\r\nContent-Type: '+fields['content-type']+'\r\nContent-Length: '+body.length+'\r\nContent-Digest: '+fields['content-digest']+'\r\nConnection: close\r\nSignature-Input: '+si+'\r\nSignature: sig1=:'+sig+':\r\n\r\n';
 return {nonce:n,seq,op,header,body_hex:body.toString('hex')};
}
const auth=[];
for(let i=0;i<12;++i)auth.push(signed(3,999,record(3,999)));
const groups=[];
for(const width of [0,32,48])for(let cycle=0;cycle<10;++cycle){
 const seq=++sequence,image=Buffer.alloc(width*width*2,0xa5),tx=record(3,seq).subarray(16,32).toString('hex');
 const meta={album:'Album',artist:'Artist',cover_len:image.length,cover_sha256:width?crypto.createHash('sha256').update(image).digest('hex'):null,duration:60,height:width,pixel_format:width?'RGB565LE':'NONE',position:0,source:'qualification',state:'PLAYING',tile_count:image.length/512,title:'Test',track_key:'0'.repeat(64),tx,v:2,width};
 const packets=[signed(1,seq,record(1,seq,Buffer.from(JSON.stringify(meta))))];
 for(let t=0;t<image.length/512;++t)packets.push(signed(2,seq,record(2,seq,image.subarray(t*512,(t+1)*512),t)));
 const abort=width===0 && cycle%3===2;
 packets.push(signed(abort?4:3,seq,record(abort?4:3,seq)));
 groups.push({width,cycle,seq,abort,packets});
}
process.stdout.write(JSON.stringify({kind:'ONE_SHOT_PUBLIC_SYNTHETIC_QUALIFICATION',public_point,epoch:epoch.toString(16),auth,groups}));
