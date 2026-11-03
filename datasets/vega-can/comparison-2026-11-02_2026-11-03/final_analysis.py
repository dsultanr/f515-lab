from screen import *
import hashlib
from collections import Counter

def values(a,cid,bus,fn):
 r=a[(a['id']==cid)&(a['bus']==bus)];first=int(a['t'].min());return r,(r['t'].astype(float)-first)/1000,fn(r['d'].astype(np.int64))
def edge(r,t,v,lo,hi,predicate):
 idx=np.flatnonzero((t>=lo)&(t<hi)&predicate(v))
 if not len(idx):return None
 i=idx[0]
 return {'first_s':round(float(t[i]),6),'previous_s':round(float(t[i-1]),6) if i else None,'previous_value':float(v[i-1]) if i else None,'value':float(v[i]),'payload':bytes(r['d'][i]).hex(),'previous_payload':bytes(r['d'][i-1]).hex() if i else None,'gap_ms':round(float((t[i]-t[i-1])*1000),3) if i else None,'tracker_ms':int(r['t'][i])}
results={};csvrows=[];controls=[]
for day in [2,3]:
 a=load(day);first=int(a['t'].min());ev=get_events(day,a);wall0=first/1000+alignment(day,a)
 rr,rt,rv=values(a,0x10d,0,lambda d:np.where(d[:,3]*256+d[:,4]>=32,(d[:,3]*256+d[:,4])*.25,0))
 gr,gt,gv=values(a,0x10c,0,lambda d:d[:,0]>>4)
 er,et,ee=values(a,0x181,0,lambda d:d[:,0]&7)
 kr,kt,kv=values(a,0x341,0,lambda d:d[:,0]&7)
 br,bt,bi=values(a,0x104,1,lambda d:(((d[:,3]<<16)|(d[:,4]<<8)|d[:,5])>>6 & 0x3fff)*.1-400)
 _,_,bv=values(a,0x104,1,lambda d:((d[:,0]<<8)|d[:,1])//4*.1)
 _,_,soc=values(a,0x104,1,lambda d:((d[:,5]<<8)|d[:,6])>>4 & 0x3ff)
 cycles=[]
 allcmd=commands(day)
 for e in ev:
  t=e['rel'];on=edge(kr,kt,kv,t-2,t+7,lambda v:v==3)
  stopcmd=next(c for c in allcmd if c['time']>e['time'] and c['action'] in ('off','unlock'))
  stoprel=stopcmd['time']-wall0
  off=edge(kr,kt,kv,stoprel-2,stoprel+6,lambda v:v!=3)
  start=on['first_s'];end=off['first_s'];lo=start-1;hi=end
  rpmstart=edge(rr,rt,rv,start,end,lambda v:v>100)
  gcustart=edge(gr,gt,gv,start,end,lambda v:v==3)
  gcurun=edge(gr,gt,gv,start,end,lambda v:v==4)
  emsstart=edge(er,et,ee,start,end,lambda v:v==3)
  emsrun=edge(er,et,ee,start,end,lambda v:v==4)
  rpmstop=edge(rr,rt,rv,end-3,end+8,lambda v:v<=100) if rpmstart else None
  gcustop=edge(gr,gt,gv,end-3,end+8,lambda v:v==3) if gcustart else None
  emsstop=edge(er,et,ee,end-3,end+8,lambda v:v==5) if rpmstart else None
  rm=(rt>=start)&(rt<end+1);bm=(bt>=start)&(bt<end+1)
  lead=round(rpmstart['first_s']-gcustart['first_s'],6) if rpmstart and gcustart else None
  lead_lo=round(rpmstart['previous_s']-gcustart['first_s'],6) if lead is not None else None
  lead_hi=round(rpmstart['first_s']-gcustart['previous_s'],6) if lead is not None else None
  c={'label':e['label'],'command_msk':e['time_msk'],'ha_tx_relative_s':t,'can_key_on':on,'can_key_off':off,'stop_action':stopcmd['action'],'gcu3':gcustart,'gcu4':gcurun,'rpm_gt100':rpmstart,'ems3':emsstart,'ems4':emsrun,'gcu_stop3':gcustop,'ems_stop5':emsstop,'rpm_stop':rpmstop,'gcu3_first_to_rpm_first_s':lead,'gcu3_to_rpm_transition_bracket_s':[lead_lo,lead_hi] if lead is not None else None,'rpm_peak':float(rv[rm].max()),'battery_current_min_a':round(float(bi[bm].min()),2),'battery_current_max_a':round(float(bi[bm].max()),2),'battery_power_min_kw':round(float((bi[bm]*bv[bm]/1000).min()),3),'battery_power_max_kw':round(float((bi[bm]*bv[bm]/1000).max()),3)}
  cycles.append(c)
  csvrows.append({k:c[k] for k in ['label','command_msk','stop_action','gcu3_first_to_rpm_first_s','rpm_peak','battery_current_min_a','battery_current_max_a','battery_power_min_kw','battery_power_max_kw']})
  csvrows[-1].update(gcu3_tracker_ms=gcustart['tracker_ms'] if gcustart else '',rpm_start_tracker_ms=rpmstart['tracker_ms'] if rpmstart else '',key_on_tracker_ms=on['tracker_ms'],key_off_tracker_ms=off['tracker_ms'])
 # Whole-window false-positive controls: a delayed occurrence in high SOC rejects specificity.
 check=[]
 for cid,bus,byte,shift,mask,states in [(0x371,0,7,6,3,[1,2]),(0x185,0,5,7,1,[1]),(0x35a,0,4,5,1,[1]),(0x379,0,3,2,1,[0]),(0x10c,0,0,4,15,[3,4]),(0x181,0,0,0,7,[3,4])]:
  r,t,v=values(a,cid,bus,lambda d:(d[:,byte]>>shift)&mask)
  for state in states:
   per=[]
   for c in cycles:
    x=edge(r,t,v,c['can_key_on']['first_s'],c['can_key_off']['first_s'],lambda v:v==state)
    per.append({'cycle':c['label'],'observed':x is not None,'offset_from_key_on_s':round(x['first_s']-c['can_key_on']['first_s'],3) if x else None})
   check.append({'id':f'0x{cid:03X}','bus':bus,'byte':byte,'shift':shift,'mask':mask,'value':state,'cycles':per})
 present=set(int(x) for x in a['id']);targets=[0x11,0x31,0x92,0x101,0x102,0x103,0x105,0x114,0x121,0x141,0x151,0x161,0x162,0x186,0x187,0x342,0x393,0x394]
 results[day]={'frames':len(a),'cycles':cycles,'controls':check,'target_id_counts':{f'0x{cid:03X}':int((a['id']==cid).sum()) for cid in targets},'source_sha256':hashlib.sha256((base(day)/'raw/stream.bin').read_bytes()).hexdigest(),'soc_raw_range':[int(soc.min()),int(soc.max())]}
 if day==2:
  failed=next(e for e in allcmd if e['action']=='on' and 210<e['time']-wall0<230);t=failed['time']-wall0
  results[day]['failed_remote_on']={'command_msk':failed['time_msk'],'relative_s':t,'rpm_samples_next_8s':int(((rt>=t)&(rt<t+8)).sum()),'rpm_max_next_8s':float(rv[(rt>=t)&(rt<t+8)].max()) if ((rt>=t)&(rt<t+8)).any() else None,'key_states_next_8s':sorted(set(kv[(kt>=t)&(kt<t+8)].tolist()))}
(ROOT/'findings.json').write_text(json.dumps(results,indent=2)+'\n')
with (ROOT/'cycles.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(csvrows[0]));w.writeheader();w.writerows(csvrows)
for d,r in results.items():
 print('DAY',d)
 for c in r['cycles']:
  print(c['label'],c['command_msk'],'RPM',c['rpm_peak'],'lead',c['gcu3_first_to_rpm_first_s'],'bracket',c['gcu3_to_rpm_transition_bracket_s'],'I minmax',c['battery_current_min_a'],c['battery_current_max_a'])
 print('target ids',r['target_id_counts'])
