from data import *
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
findings=json.loads((ROOT/'findings.json').read_text())
fig,axes=plt.subplots(4,2,figsize=(13,10),sharex=True,layout='constrained')
colors=['#1468a0','#d67b13','#258945','#9254b0','#bb3b57']
labels=['Engine speed, rpm (0x10D)','0x10C: byte 0 >> 4 (state code)','HV battery current, A (0x104)','0x181: byte 0 & 7 (state code)']
limits=[(-100,3000),(-.2,5.3),(-20,50),(-.2,5.3)]
for col,day in enumerate([2,3]):
 a=load(day);first=int(a['t'].min())
 for row,(cid,bus) in enumerate([(0x10d,0),(0x10c,0),(0x104,1),(0x181,0)]):
  r=a[(a['id']==cid)&(a['bus']==bus)];d=r['d'].astype(np.int64);t=(r['t'].astype(float)-first)/1000
  if row==0:
   raw=d[:,3]*256+d[:,4];v=np.where(raw>=32,raw*.25,0)
  elif row==1:v=d[:,0]>>4
  elif row==2:v=(((d[:,3]<<16)|(d[:,4]<<8)|d[:,5])>>6 & 0x3fff)*.1-400
  else:v=d[:,0]&7
  for i,c in enumerate(findings[str(day)]['cycles']):
   origin=c['can_key_on']['first_s'];end=c['can_key_off']['first_s'];sel=(t>=origin-1)&(t<=min(origin+22,end+2))
   x=t[sel]-origin;y=v[sel].astype(float)
   # Break the displayed line across missing observations. Never interpolate capture gaps.
   idx=np.flatnonzero(np.diff(x)>.5)+1
   for j,(xx,yy) in enumerate(zip(np.split(x,idx),np.split(y,idx))):
    axes[row,col].plot(xx,yy,lw=1.0,color=colors[i],alpha=.85,drawstyle='steps-post' if row in (1,3) else 'default',label=c['label'] if j==0 and row==0 else None)
   if row==0 and end-origin<22:axes[row,col].axvline(end-origin,color=colors[i],lw=.7,ls=':',alpha=.7)
  ax=axes[row,col];ax.set_ylim(*limits[row]);ax.set_xlim(-1,22);ax.grid(alpha=.22);ax.set_ylabel(labels[row],fontsize=9)
  ax.axvline(0,color='#333',ls='--',lw=.7)
  if row==0:ax.legend(loc='upper right',ncol=2,fontsize=8);ax.set_title('2 Nov: low SOC, 4 observed starts' if day==2 else '3 Nov: full SOC, 5 controls')
  if row==3:ax.set_xlabel('Seconds from CAN key-state transition to 3')
fig.suptitle('Remote On: engine/generator sequence versus ignition-only controls',fontsize=13)
fig.savefig(ROOT/'comparison.png',dpi=160)
fig.savefig(ROOT/'comparison.svg')
