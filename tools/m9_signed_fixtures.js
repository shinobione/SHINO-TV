// Ephemeral RSA private key stays only in Node memory. Public inert outputs.
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const raw = fs.readFileSync(process.argv[2]);
if (raw.length !== 100000 || crypto.createHash('sha256').update(raw).digest('hex') !==
    '5c6605d32ad0efd4b5a7f7ba9675a1111d765695afd3d41da5290ba3fc8defb6') {
  throw new Error('PUBLIC_INERT_FIXTURE_ONLY');
}
const folder = process.argv[3];
const {privateKey, publicKey} = crypto.generateKeyPairSync('rsa', {modulusLength:2048});
const der = publicKey.export({type:'spki',format:'der'});
const jwk = publicKey.export({format:'jwk'});
const signature = crypto.sign('sha256',raw,{key:privateKey,padding:crypto.constants.RSA_PKCS1_PADDING});
const trailer = Buffer.alloc(4); trailer.writeUInt32LE(256);
fs.writeFileSync(path.join(folder,'public.der'),der);
fs.writeFileSync(path.join(folder,'modulus'),Buffer.from(jwk.n,'base64url'));
fs.writeFileSync(path.join(folder,'exponent'),Buffer.from(jwk.e,'base64url'));
fs.writeFileSync(path.join(folder,'signed.inert'),Buffer.concat([raw,signature,trailer]));
console.log('EPHEMERAL_FIXTURE_PUBLIC_OUTPUTS_ONLY');
