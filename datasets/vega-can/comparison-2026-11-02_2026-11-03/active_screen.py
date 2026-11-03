from screen import *
findings=json.loads((ROOT/'findings.json').read_text());stats={}
for day in [2,3]:
 a=load(day);first=int(a['t'].min());stats[day]={}
 for bus,cid in sorted(set(zip(a['bus'],a['id']))):
  r=a[(a['bus']==bus)&(a['id']==cid)];t=(r['t'].astype(float)-first)/1000
  per=[]
  for c in findings[str(day)]['cycles']:
   lo=c['can_key_on']['first_s']+1.5;hi=lo+4
   per.append(means(r,t,lo,hi))
  stats[day][int(bus),int(cid)]=np.array(per)
rows=[]
for key,lo in stats[2].items():
 hi=stats[3][key]
 for bit in range(64):
  l=lo[:,bit];h=hi[:,bit]
  if np.isnan(l).any() or np.isnan(h).any():continue
  if (np.all(l>.9) and np.all(h<.1)) or (np.all(l<.1) and np.all(h>.9)):
   rows.append({'bus':key[0],'id':f'0x{key[1]:03X}','byte':bit//8,'bit':bit%8,'low':np.round(l,3).tolist(),'high':np.round(h,3).tolist()})
(ROOT/'active-window-differences.json').write_text(json.dumps(rows,indent=2)+'\n')
print('Active-only contrasts:',len(rows))
for r in rows:print(r)
