from pathlib import Path
import numpy as np, json,struct,zlib,os,hashlib
ROOT=Path(os.environ.get('VEGA_ANALYSIS_OUT',str(Path(__file__).resolve().parent))).resolve()
ROOT.mkdir(parents=True,exist_ok=True)
CAP=Path(os.environ.get('VEGA_CAPTURE_ROOT',str(ROOT.parent))).resolve()
DT=np.dtype([('t','<u4'),('id','<u4'),('bus','u1'),('dlc','u1'),('d','u1',(8,))])
def base(day):
 default=CAP/f'remote_can_202611{day:02d}'/'research-export'/f'vega-can-research-202611{day:02d}'
 return Path(os.environ.get('VEGA_LOW_SESSION' if day==2 else 'VEGA_HIGH_SESSION',str(default)))
def load(day):
 cache=ROOT/f'day{day}.npy'
 source=base(day)/'raw/stream.bin';fingerprint=hashlib.sha256(source.read_bytes()).hexdigest();meta=ROOT/f'day{day}.cache.json'
 if cache.exists() and meta.exists() and json.loads(meta.read_text()).get('source_sha256')==fingerprint:return np.load(cache)
 b=source.read_bytes();off=0;parts=[]
 while off<len(b):
  size=struct.unpack_from('<H',b,off)[0]+7;f=b[off:off+size]
  assert len(f)==size and zlib.crc32(f[:-4])==struct.unpack_from('<I',f,size-4)[0]
  if f[2]==0x1e:
   assert size==16+18*f[3];parts.append(np.frombuffer(f,DT,count=f[3],offset=12))
  off+=size
 a=np.concatenate(parts);a=a[np.argsort(a['t'],kind='stable')];np.save(cache,a);meta.write_text(json.dumps({'source_sha256':fingerprint,'frames':len(a)}));return a
if __name__=='__main__':
 from collections import Counter
 for day in [2,3]:
  a=load(day);t0=int(a['t'].min());print('DAY',day,'frames',len(a),'t0',t0)
  for cid in [0x11,0x92,0x394,0x10d]:
   r=a[a['id']==cid];print(hex(cid),'buses',dict(Counter(r['bus'])), 'unique payloads',len(set(bytes(d) for d in r['d'])))
   c=Counter(bytes(d).hex() for d in r['d']);print(c.most_common(10))
   if cid in [0x11,0x92]:
    for x in r[:100]:print(round((int(x['t'])-t0)/1000,3),int(x['bus']),bytes(x['d']).hex())
  r=a[(a['id']==0x10d)&(a['bus']==0)];d=r['d'].astype(int)
  for at in range(7):
   v=(d[:,at]*256+d[:,at+1])*.25;print('RPM candidate bytes',at,at+1,'minmax',v.min(),v.max(),'examples',v[::max(1,len(v)//10)].tolist())
