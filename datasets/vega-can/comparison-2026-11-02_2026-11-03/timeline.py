from data import *
import csv,datetime,statistics
MSK=datetime.timezone(datetime.timedelta(hours=3))
def epoch(s):return datetime.datetime.fromisoformat(s).timestamp()
def alignment(day,a):
 s=json.loads((base(day)/'context/status.json').read_text());first=int(a['t'].min())
 if day==2:return s['started_ms']/1000-first/1000
 cal=[json.loads(l) for l in (base(day)/'context/host-hu-clock-calibration.jsonl').read_text().splitlines()]
 lower=max(r['host_minus_hu_lower_ms'] for r in cal);upper=min(r['host_minus_hu_upper_ms'] for r in cal);assert lower<=upper
 v=json.loads((base(day)/'context/verification.json').read_text())
 return ((lower+upper)/2+v['elapsed_minus_tracker_ms_min'])/1000

def commands(day):
 logs=json.loads((base(day)/'context/ha-command-log.json').read_text());tx=[x for x in logs if x['type']=='vega_setting_tx_log']
 out=[]
 for i,r in enumerate(tx):
  t=epoch(r['time_msk']);sid=r['setting_id'];value=int(r['value_hex'],16)
  if sid==1341 and value==1:action='on'
  elif sid==1341 and value==0:
   if any(n['setting_id']==1341 and n['value_hex']=='01' and 0<epoch(n['time_msk'])-t<5 for n in tx[i+1:i+3]):continue
   action='off'
  elif sid==1349:action='lock'
  elif sid==1350:action='unlock'
  else:continue
  out.append(dict(time=t,action=action,time_msk=r['time_msk']))
 return out

def rpm(a):
 d=a['d'].astype(np.uint32);raw=d[:,3]*256+d[:,4];return np.where(raw>=32,raw*.25,0.)

def trace_changes(t,v):
 ix=np.r_[True,v[1:]!=v[:-1]];return zip(t[ix],v[ix])

if __name__=='__main__':
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 fig,axes=plt.subplots(4,2,figsize=(17,10),sharex='col')
 for col,day in enumerate([2,3]):
  a=load(day);first=int(a['t'].min());align=alignment(day,a);wall0=first/1000+align
  print('DAY',day,'align',align,'wall first',datetime.datetime.fromtimestamp(wall0,MSK).isoformat())
  cc=[r for r in commands(day) if wall0<=r['time']<=wall0+(int(a['t'].max())-first)/1000]
  for r in cc:print(r['action'],round(r['time']-wall0,3))
  rs=a[(a['id']==0x10d)&(a['bus']==0)];rt=(rs['t'].astype(float)-first)/1000;rv=rpm(rs)
  st=rv>100
  print('RPM>100 transitions',[(round(float(t),3),bool(v)) for t,v in trace_changes(rt,st)])
  print('rpm max',rv.max(),'nonzero',int((rv>100).sum()),'samples',len(rv))
  for row,cid,bus in [(0,0x10d,0),(1,0x104,1),(2,0x341,0),(3,0x365,0)]:
   r=a[(a['id']==cid)&(a['bus']==bus)];d=r['d'].astype(np.uint32);t=(r['t'].astype(float)-first)/1000
   if row==0:v=rpm(r);title='RPM candidate: 0x10D bytes 3:5 BE / 4, raw < 32 -> 0'
   elif row==1:v=(((d[:,3]<<16)|(d[:,4]<<8)|d[:,5])>>6 & 0x3fff)*.1-400;title='HV current A: 0x104'
   elif row==2:v=d[:,0]&7;title='Key state: 0x341 byte0 & 7'
   else:v=(d[:,1]>>1)&1;title='Ignition: 0x365 byte1 bit1'
   axes[row,col].plot(t,v,lw=.8);axes[row,col].set_title(f'Nov {day}: '+title);axes[row,col].grid(alpha=.25)
   for c in cc:
    x=c['time']-wall0;axes[row,col].axvline(x,color={'on':'green','off':'red','unlock':'orange','lock':'gray'}[c['action']],alpha=.5,lw=.8)
    if row==0:axes[row,col].text(x,rv.max()*.9 if day==2 else 100,c['action'],rotation=90,fontsize=7)
  rows=[]
  for r in cc:
   t=r['time']-wall0;mask=(rt>=t)&(rt<t+30)
   rows.append(dict(**r,relative_s=t,rpm_max_next_30s=float(rv[mask].max()) if mask.any() else None))
  (ROOT/f'day{day}-timeline.json').write_text(json.dumps(rows,indent=2)+'\n')
 axes[3,0].set_xlabel('seconds since first recorded CAN frame');axes[3,1].set_xlabel('seconds since first recorded CAN frame')
 fig.tight_layout();fig.savefig(ROOT/'overview.png',dpi=150)
