from timeline import *
from collections import defaultdict,Counter

def get_events(day,a):
 first=int(a['t'].min());wall0=first/1000+alignment(day,a)
 events=[dict(e,rel=e['time']-wall0) for e in commands(day) if wall0<e['time']<wall0+(int(a['t'].max())-first)/1000]
 if day==2:
  return [dict(e,label=f'L{i+1}',control=False) for i,e in enumerate(e for e in events if e['action']=='on' and not 210<e['rel']<230)]
 return [dict(e,label=f'H{i+1}',control=True) for i,e in enumerate(e for e in events if e['action']=='on' and e['rel']>350)]

def means(r,t,lo,hi):
 mask=(t>=lo)&(t<hi);d=r['d'][mask]
 if len(d)<5 or len(np.unique(np.floor(t[mask])))<2:return np.full(64,np.nan)
 return np.unpackbits(d,axis=1,bitorder='little').mean(axis=0)

def main():
 allstats={};groups={};events={}
 for day in [2,3]:
  a=load(day);first=int(a['t'].min());events[day]=get_events(day,a)
  groups[day]={};allstats[day]={}
  for bus,cid in sorted(set(zip(a['bus'],a['id']))):
   r=a[(a['bus']==bus)&(a['id']==cid)];t=(r['t'].astype(float)-first)/1000;key=(int(bus),int(cid));groups[day][key]=(r,t)
   allstats[day][key]=np.array([[means(r,t,e['rel']-5,e['rel']-1),means(r,t,e['rel']+2,e['rel']+6),means(r,t,e['rel']+9,e['rel']+13)] for e in events[day]])
 rows=[]
 for key,low in allstats[2].items():
  high=allstats[3][key]
  for bit in range(64):
   l=low[:,:,bit];h=high[:,:,bit]
   if np.isnan(l).any() or np.isnan(h).any():continue
   delta=l[:,2]-l[:,0];sgn=1 if np.median(delta)>0 else -1
   low_changes=int((sgn*delta>.7).sum());high_changes=int((np.abs(h[:,2]-h[:,0])>.3).sum())
   early=int((sgn*(l[:,1]-l[:,0])>.7).sum())
   if low_changes>=3 and high_changes<=1:
    rows.append(dict(bus=key[0],can_id=f'0x{key[1]:03X}',byte=bit//8,bit=bit%8,low_changes=low_changes,high_changes=high_changes,early_changes=early,low_pre=np.round(l[:,0],3).tolist(),low_early=np.round(l[:,1],3).tolist(),low_post=np.round(l[:,2],3).tolist(),high_pre=np.round(h[:,0],3).tolist(),high_post=np.round(h[:,2],3).tolist()))
 rows.sort(key=lambda r:(-r['low_changes'],r['high_changes'],-r['early_changes'],r['can_id'],r['bus'],r['byte'],r['bit']))
 (ROOT/'bit-screen.json').write_text(json.dumps({'events':events,'candidates':rows,'method':'Within-cycle bit occupancy difference: pre[-5,-1),early[2,6),steady[9,13) seconds from actual HA TX On. At least 3/4 low-SOC changes >0.7; at most 1/5 high-SOC changes >0.3; every window >=5 frames and >=2 occupied seconds. Exploratory, no statistical independence or command semantics assumed.'},indent=2)+'\n')
 print('CANDIDATE BITS',len(rows))
 for r in rows[:90]:print(r)
 # Low-rate event records are inspected separately; bit screening excludes sparse windows.
 rare=[]
 for day in [2,3]:
  for (bus,cid),(r,t) in groups[day].items():
   if cid<0x100:
    for x,ts in zip(r,t):rare.append({'day':day,'bus':bus,'id':f'0x{cid:03X}','relative_s':round(float(ts),3),'payload':bytes(x['d']).hex()})
 (ROOT/'low-id-events.json').write_text(json.dumps(rare,indent=2)+'\n')
 with (ROOT/'bit-screen.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['bus']);w.writeheader();w.writerows(rows)
 print('rare events',len(rare))
if __name__=='__main__':main()
