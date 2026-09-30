"use strict";
// Differential oracle is the preserved accepted Mission 6B profile adapter.
const p=require('./v08_m6b_profile');
const v=require('./v08_crypto_vectors.json'),e=v.entries.begin;
const headers=[e.header];
for(const h of ['TV.TEST','TV.TEST:80','tv.test:80'])headers.push(e.header.replace('Host: tv.test','hOsT:\t '+h+' \t'));
headers.push(e.header.replace('sig1=("@method"','sig1=(  "@method"').replace('"content-digest")','"content-digest"  )').replace(';alg=',';  alg='));
headers.push(e.header.replace('Content-Type: ','Content-Type:\t'));
headers.push(e.header.replace(/(Signature: sig1=:[A-Za-z0-9+/]+)==:/,'$1:'));
for(const h of ['tv.test:080','tv.test.','[::1]','tv.test:65536','a..test','1.2.3.004','evil.test','tv.test:0'])headers.push(e.header.replace('Host: tv.test','Host: '+h));
for(const h of ['Host: tv.test','Content-Length: 371','Signature: sig1=:AAAA:','Transfer-Encoding: chunked','Expect: 100-continue','Content-Encoding: gzip','Trailer: sig1','Authorization: Basic x'])headers.push(e.header.replace('\r\n\r\n','\r\n'+h+'\r\n\r\n'));
for(const [from,to] of [[';tag=',';nonce="AAAAAAAAAAAAAAAAAAAAAA";tag='],[';alg=','; alg="ecdsa-p256-sha256";alg='],['Signature: sig1=','Signature: sig1=:AAAA:, sig1='],[';keyid="media-test"',';keyid=media-test'],['"@method" ','"@method";sf '],[';nonce=',';nonce ='],['Content-Digest: sha-256=','Content-Digest: sha-256 ='],['Connection: close','Connection: keep-alive'],['Host: tv.test','Host : tv.test'],['Content-Length: 371','Content-Length: 0371'],['Content-Length: 371','Content-Length: +371'],['HTTP/1.1','HTTP/1.0'],['/begin/','/Begin/'],['/begin/','/begin//']])headers.push(e.header.replace(from,to));
const cases=headers.map(header=>{let accepted=false;const a=new p.Authority(BigInt('0x'+v.epoch_hex),{'media-test':{publicKey:v.public_key_pem,enabled:true,revoked:false,roles:['media'],operations:['begin','tile','commit','abort']}});a.issue('media-test',e.nonce,101,100);
const s=new p.ByteStream(Buffer.concat([Buffer.from(header),Buffer.from(e.body_hex,'hex')]),Buffer.byteLength(header));try{p.gate1(s,a,()=>100);accepted=true;}catch(error){if(!(error instanceof p.Rejection))throw error;}return {hex:Buffer.concat([Buffer.from(header),Buffer.from(e.body_hex,'hex')]).toString('hex'),accepted};});
process.stdout.write(JSON.stringify(cases));
