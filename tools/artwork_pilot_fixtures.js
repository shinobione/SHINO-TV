"use strict";
// Deterministic covers, ephemeral host signing key. No device/network sender.
const crypto = require("node:crypto");
const wire = require("./v08_m6b_security");
const {privateKey, publicKey} = crypto.generateKeyPairSync("ec", {namedCurve:"prime256v1"});
const jwk = publicKey.export({format:"jwk"});
const point = Buffer.concat([Buffer.from([4]),Buffer.from(jwk.x,"base64url"),Buffer.from(jwk.y,"base64url")]);
const epoch = 0x1122334455667788n;
let serial = 0, sequence = 0;
function image(kind) {
  const b = Buffer.alloc(2048);
  for (let y=0;y<32;y++) for (let x=0;x<32;x++) {
    let r,g,bl;
    if (!kind) {
      r=40+x*6; g=25+y*3; bl=70+y*3;
      if ((x-21)**2+(y-17)**2<105) {r=18;g=28;bl=48;}
      if ((x-21)**2+(y-17)**2<13) {r=245;g=193;bl=85;}
    } else {
      r=12;g=36;bl=62;
      if (x%7<4 && y>8+(x*11)%13) {r=40+x*5;g=175-y*2;bl=165+x*2;}
      if (y>27) {r=213;g=91;bl=136;}
    }
    let pixel=((r>>3)<<11)|((g>>2)<<5)|(bl>>3);
    if(y===0)pixel=[0xf800,0x07e0,0x001f,0xffff][x>>3]; // byte-order witness
    b.writeUInt16LE(pixel,(y*32+x)*2);
  }
  return b;
}
function record(op, seq, payload=Buffer.alloc(0), index=0) {
  const b=Buffer.alloc(40);b.write("STV7");b[4]=2;b[5]=op;
  b.writeBigUInt64BE(epoch,8);b.writeBigUInt64BE(epoch,16);b.writeBigUInt64BE(BigInt(seq),24);
  b.writeUInt16BE(index,32);b.writeUInt16BE(payload.length,34);b.writeUInt32BE(wire.crc32(payload),36);
  return Buffer.concat([b,payload]);
}
function signed(op,body) {
  const alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-";
  let n=++serial,nonce="";for(let i=0;i<22;++i){nonce=alphabet[n%64]+nonce;n=Math.floor(n/64);}
  const target="/api/v2/bridge/media/"+["","begin","tile","commit","abort"][op]+"/"+body.subarray(16,32).toString("hex");
  const fields={host:"tv.test","content-type":wire.CONTENT_TYPE,"content-length":String(body.length),"content-digest":wire.canonicalDigest(body)};
  const si=wire.signatureInput("media-test",nonce);
  const request={method:"POST",target,fields,signatureInput:si};
  const base=wire.signatureBase(request);
  const sig=crypto.sign("sha256",base,{key:privateKey,dsaEncoding:"ieee-p1363"});
  if (!crypto.verify("sha256",base,{key:publicKey,dsaEncoding:"ieee-p1363"},sig)) throw Error("fixture proof");
  const header="POST "+target+" HTTP/1.1\r\nHost: tv.test\r\nContent-Type: "+fields["content-type"]+"\r\nContent-Length: "+body.length+"\r\nContent-Digest: "+fields["content-digest"]+"\r\nConnection: close\r\nSignature-Input: "+si+"\r\nSignature: sig1=:"+sig.toString("base64")+":\r\n\r\n";
  return {header,body_hex:body.toString("hex"),nonce};
}
function group(name,{kind=0,width=32,title="Midnight Signals",artist="SHINO LAB",state="PLAYING",position=42,duration=180,trackKey=null,invalid=false}={}) {
  const seq=++sequence, cover=width ? image(kind) : Buffer.alloc(0);
  const meta={album:"",artist,cover_len:cover.length,cover_sha256:width?crypto.createHash("sha256").update(cover).digest("hex"):null,duration,height:width,pixel_format:width?"RGB565LE":"NONE",position,source:"fixture",state,tile_count:cover.length/512,title,track_key:trackKey||crypto.createHash("sha256").update(title+"\0"+artist).digest("hex"),tx:record(3,seq).subarray(16,32).toString("hex"),v:2,width};
  if(invalid)meta.state="INVALID";
  const bytes=Buffer.from(JSON.stringify(meta));if(bytes.length>512)throw Error("fixture budget");
  const packets=[signed(1,record(1,seq,bytes))];
  for(let i=0;i<cover.length/512;i++)packets.push(signed(2,record(2,seq,cover.subarray(i*512,(i+1)*512),i)));
  packets.push(signed(3,record(3,seq)),signed(4,record(4,seq)));
  return {name,image_hex:cover.toString("hex"),packets};
}
const groups=[group("first"),group("replacement",{kind:1,title:"Neon Streets",artist:"SmallTV / Offline"}),group("repeat"),group("paused",{state:"PAUSED"}),group("stopped",{state:"STOPPED"}),group("no_session",{width:0,state:"NO_SESSION",title:"",artist:""}),group("missing",{width:0}),group("long",{title:"Midnight Signals / Extended Offline SmallTV Display Pilot Mix".padEnd(60," ").slice(0,60),artist:"SHINO LAB / Deterministic Native Receiver Qualification Set".padEnd(60," ").slice(0,60)}),group("utf8",{title:"Café / 夜",artist:"Björk"}),group("rejected",{invalid:true}),
  group("resume"),group("unknown_progress",{position:null,duration:null}),
  group("zero_duration",{position:0,duration:0}),group("position_only",{duration:null}),
  group("invalid_progress",{position:181}),group("unavailable",{width:0,state:"UNAVAILABLE"}),
  group("after_long",{kind:1,title:"A New Track",artist:"New Artist"}),
  group("same_labels_new_track",{title:"Midnight Signals / Extended Offline SmallTV Display Pilot Mix".padEnd(60," ").slice(0,60),artist:"SHINO LAB / Deterministic Native Receiver Qualification Set".padEnd(60," ").slice(0,60),trackKey:"1".repeat(64)}),
  group("hour_progress",{position:3601,duration:604800}),
  group("empty_labels",{width:0,title:"",artist:""}),
  group("accented_long",{width:0,title:"é".repeat(60),artist:"Zoë"}),
  group("paused_missing",{width:0,state:"PAUSED"})];
process.stdout.write(JSON.stringify({public_point:point.toString("hex"),groups}));
