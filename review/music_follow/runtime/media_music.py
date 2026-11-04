"""Music V1 production codec. PC-only conversion; no network on import."""
import hashlib,hmac,struct,unicodedata
from io import BytesIO
from media_sessions import bounded_text
from media_wire_v1 import track_identity

PATH='/api/v1/media';STATUS=PATH+'/status'
def ascii_text(value):
 text=unicodedata.normalize('NFKD',bounded_text(value,120))
 return ''.join(c for c in text if not unicodedata.combining(c)).encode('ascii','replace')[:60].ljust(61,b'\0')
def prepare(jpeg):
 if not jpeg:return None
 from PIL import Image,ImageOps
 if type(jpeg) is not bytes or len(jpeg)>40960:raise ValueError('cover extent')
 with Image.open(BytesIO(jpeg)) as src:
  if src.width*src.height>4000000:raise ValueError('image extent')
  rgb=ImageOps.fit(ImageOps.exif_transpose(src).convert('RGB'),(64,64),method=Image.Resampling.LANCZOS)
  indexed=rgb.quantize(colors=256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
  palette=indexed.getpalette();palette += [0]*(768-len(palette));out=bytearray(indexed.tobytes())
  for i in range(256):
   r,g,b=palette[3*i:3*i+3];out+=struct.pack('<H',((r>>3)<<11)|((g>>2)<<5)|(b>>3))
  assert len(out)==4608
  return bytes(out)
def timeline(s):
 p,d=s.position_seconds,s.duration_seconds
 valid=lambda n:type(n) is int and 0<=n<=604800
 flags=int(valid(p))+2*int(valid(d))
 if flags==3 and p>d:flags=0
 return struct.pack('>BBII',{'PLAYING':1,'PAUSED':2}.get(s.state,0),flags,p if flags&1 else 0,d if flags&2 else 0)
def metadata(s,cover):
 if cover is not None and (type(cover) is not bytes or len(cover)!=4608):raise ValueError('cover extent')
 return timeline(s)+ascii_text(s.title)+ascii_text(s.artist)+bytes.fromhex(track_identity(s))+(hashlib.sha256(cover).digest() if cover else bytes(32))+bytes([int(cover is not None)])
def update(s):return timeline(s)+bytes.fromhex(track_identity(s))
def envelope(op,sequence,tx,offset,body):
 if type(sequence) is not int or not 0<=sequence<0xffffffff or op not in range(1,6) or len(tx)!=16 or not any(tx) or len(body)>512 or not 0<=offset<=4608:raise ValueError('frame bound')
 return (struct.pack('>BBI16sHH',1,op,sequence,tx,offset,len(body))+hashlib.sha256(body).digest()).hex()
def tag(password,s,command,result=None,*,status=False):
 domain='SHINO-MEDIA-STATUS-1\n' if status else 'SHINO-MEDIA-ACK-1\n' if result is not None else 'SHINO-MEDIA-REQ-1\nPOST\n'+PATH+'\n'
 message=domain+s['device']+'\n'+s['build']+'\n'+s['boot']+'\n'+command+'\n'
 if result is not None:message+=result+'\n'
 return hmac.new(password.encode('utf-8'),message.encode('ascii'),hashlib.sha256).hexdigest()
def verified_ack(password,s,command,ack):
 if type(ack) is not dict or set(ack)!={'protocol','sequence','accepted','command','proof'} or type(ack['protocol']) is not int or ack['protocol']!=1 or type(ack['sequence']) is not int or ack['sequence']!=int(command[4:12],16)+1 or type(ack['accepted']) is not bool or ack['command']!=command or type(ack['proof']) is not str:raise ValueError('ACK schema')
 result=f'{ack["sequence"]:08x}{int(ack["accepted"]):02x}'
 if not hmac.compare_digest(ack['proof'],tag(password,s,command,result)):raise ValueError('ACK proof')
 return ack
