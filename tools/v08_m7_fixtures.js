"use strict";
// Ephemeral synthetic lab signer in memory only; never export a private key.
const crypto=require('node:crypto');
const wire=require('./v08_m6b_security');
const vectors=require('./v08_crypto_vectors.json');
function point(key){const j=key.export({format:'jwk'});return Buffer.concat([Buffer.from([4]),Buffer.from(j.x,'base64url'),Buffer.from(j.y,'base64url')]).toString('hex');}
const {publicKey,privateKey}=crypto.generateKeyPairSync('ec',{namedCurve:'prime256v1'});
let serial=0;
function record(op,seq,payload=Buffer.alloc(0),index=0){const tx=Buffer.alloc(16);tx.writeBigUInt64BE(BigInt('0x'+vectors.epoch_hex));tx.writeBigUInt64BE(BigInt(seq),8);
const b=Buffer.alloc(40);b.write('STV7');b[4]=2;b[5]=op;b.writeBigUInt64BE(BigInt('0x'+vectors.epoch_hex),8);tx.copy(b,16);b.writeUInt16BE(index,32);b.writeUInt16BE(payload.length,34);b.writeUInt32BE(wire.crc32(payload),36);return Buffer.concat([b,payload]);}
function signed(op,seq,body){const operation=['','begin','tile','commit','abort'][op];const nonce='A'.repeat(21)+'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-'[++serial];const tx=body.subarray(16,32).toString('hex');const target='/api/v2/bridge/media/'+operation+'/'+tx;
const fields={host:'tv.test','content-type':wire.CONTENT_TYPE,'content-length':String(body.length),'content-digest':wire.canonicalDigest(body)};const si=wire.signatureInput('media-test',nonce);const request={method:'POST',target,fields,signatureInput:si};
const sig=crypto.sign('sha256',wire.signatureBase(request),{key:privateKey,dsaEncoding:'ieee-p1363'}).toString('base64');
const header='POST '+target+' HTTP/1.1\r\nHost: tv.test\r\nContent-Type: '+fields['content-type']+'\r\nContent-Length: '+body.length+'\r\nContent-Digest: '+fields['content-digest']+'\r\nConnection: close\r\nSignature-Input: '+si+'\r\nSignature: sig1=:'+sig+':\r\n\r\n';return {header,body_hex:body.toString('hex'),nonce,operation};}
const groups={};
for(const w of [0,32,48]){const seq=w+2,image=Buffer.alloc(w*w*2,0xa5);const tx=record(3,seq).subarray(16,32).toString('hex');
const d={album:'Album',artist:'Artist',cover_len:image.length,cover_sha256:w?crypto.createHash('sha256').update(image).digest('hex'):null,duration:60,height:w,pixel_format:w?'RGB565LE':'NONE',position:0,source:'fixture',state:'PLAYING',tile_count:image.length/512,title:'Test',track_key:'0'.repeat(64),tx,v:2,width:w};
const payload=Buffer.from(JSON.stringify(d));const list=[signed(1,seq,record(1,seq,payload))];for(let i=0;i<image.length/512;++i)list.push(signed(2,seq,record(2,seq,image.subarray(i*512,(i+1)*512),i)));list.push(signed(3,seq,record(3,seq)));list.push(signed(4,seq,record(4,seq)));groups[w]=list;}
const retainedKey=crypto.createPublicKey(vectors.public_key_pem);
process.stdout.write(JSON.stringify({retained_key:point(retainedKey),synthetic_key:point(publicKey),retained:vectors.entries,groups}));
