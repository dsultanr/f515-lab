from screen import *
result={};info={}
for day in [2,3]:
 a=load(day);first=int(a['t'].min());ev=get_events(day,a);r=a[(a['id']==0x10d)&(a['bus']==0)];rt=(r['t'].astype(float)-first)/1000;rv=rpm(r)
 for e in ev:
  mask=(rt>e['rel'])&(rt<e['rel']+15)&(rv>100)
  e['rpm_rel']=float(rt[mask][0]) if mask.any() else None
 info[day]=ev;result[day]={}
 for bus,cid in sorted(set(zip(a['bus'],a['id']))):
  r=a[(a['bus']==bus)&(a['id']==cid)];t=(r['t'].astype(float)-first)/1000;bits=np.unpackbits(r['d'],axis=1,bitorder='little');out=[]
  for e in ev:
   pre=(t>=e['rel']-5)&(t<e['rel']-1);stop=e['rpm_rel']-.1 if day==2 else e['rel']+7.5;post=(t>=e['rel'])&(t<stop)
   if pre.sum()<5 or post.sum()<3:out.append(None);continue
   p=bits[pre].mean(axis=0);v=bits[post];tt=t[post];changes=[]
   for bit in range(64):
    if .1<p[bit]<.9:changes.append(None);continue
    baseline=int(p[bit]>.5);idx=np.flatnonzero(v[:,bit]!=baseline)
    # Require at least two consecutive observed frames, not a single outlier.
    pair=idx[np.flatnonzero(np.diff(idx)==1)] if len(idx)>1 else []
    changes.append({'baseline':baseline,'first_rel':float(tt[pair[0]]) if len(pair) else None,'samples':int(len(idx)),'window_samples':len(v),'fraction':float(len(idx)/len(v))})
   out.append(changes)
  result[day][int(bus),int(cid)]=out
rows=[]
for key,low in result[2].items():
 high=result[3][key]
 if any(x is None for x in low+high):continue
 for bit in range(64):
  l=[x[bit] for x in low];h=[x[bit] for x in high]
  if any(x is None for x in l+h):continue
  if len({x['baseline'] for x in l})!=1:continue
  nl=sum(x['first_rel'] is not None for x in l);nh=sum(x['first_rel'] is not None for x in h)
  if nl>=3 and nh<=1:
   rows.append(dict(bus=key[0],can_id=f'0x{key[1]:03X}',byte=bit//8,bit=bit%8,low_hits=nl,high_hits=nh,low=l,high=h,leads_to_rpm=[round(e['rpm_rel']-x['first_rel'],3) if x['first_rel'] else None for x,e in zip(l,info[2])]))
rows.sort(key=lambda r:(-r['low_hits'],r['high_hits'],-sum(x or 0 for x in r['leads_to_rpm']),r['can_id']))
(ROOT/'transient-screen.json').write_text(json.dumps({'events':info,'candidates':rows,'note':'Stable baseline across all events; >=2 consecutive differing frames before observed RPM>100 in low-SOC events; high-SOC control window 7.5s. Exploratory candidate selection, no causality proved.'},indent=2)+'\n')
for r in rows:print({k:v for k,v in r.items() if k not in ['low','high']})
