from timeline import *
import hashlib,struct,zlib
f=json.loads((ROOT/'findings.json').read_text());evidence=[];counts={}
for day in [2,3]:
 targets={}
 for c in f[str(day)]['cycles']:
  for kind,cid,bus in [('can_key_on',0x341,0),('can_key_off',0x341,0),('gcu3',0x10c,0),('gcu4',0x10c,0),('rpm_gt100',0x10d,0),('ems3',0x181,0),('ems4',0x181,0),('gcu_stop3',0x10c,0),('ems_stop5',0x181,0),('rpm_stop',0x10d,0)]:
   if c[kind]:targets.setdefault((bus,cid,c[kind]['tracker_ms'],c[kind]['payload']),[]).append((c['label'],kind))
 raw=(base(day)/'raw/stream.bin').read_bytes();assert hashlib.sha256(raw).hexdigest()==f[str(day)]['source_sha256']
 off=0;n=0;packet_count=0;found=set()
 while off<len(raw):
  size=int.from_bytes(raw[off:off+2],'little')+7;packet=raw[off:off+size]
  assert len(packet)==size and zlib.crc32(packet[:-4])==int.from_bytes(packet[-4:],'little')
  if packet[2]==0x1e:
   packet_count+=1;assert size==16+18*packet[3]
   for i in range(packet[3]):
    at=12+18*i;t,cid,bus,dlc=struct.unpack_from('<IIBB',packet,at);d=packet[at+10:at+18];n+=1
    key=(bus,cid,t,d.hex())
    if key in targets and key not in found:
     for label,kind in targets[key]:evidence.append({'day':day,'cycle':label,'kind':kind,'bus':bus,'can_id':f'0x{cid:03X}','tracker_ms':t,'data_hex':d.hex(),'usb_packet_offset':off,'record_index':i,'usb_packet_crc32':packet[-4:].hex()})
     found.add(key)
  off+=size
 assert found==targets.keys(),targets.keys()-found
 assert n==f[str(day)]['frames']
 counts[day]={'frames':n,'can_packets':packet_count,'keyed_records_verified':len(found),'raw_sha256':f[str(day)]['source_sha256']}
assert len(f['2']['cycles'])==4 and len(f['3']['cycles'])==5
assert all(c['gcu3'] and c['gcu4'] and c['ems3'] and c['ems4'] and c['rpm_peak']>1000 for c in f['2']['cycles'])
assert all(not c['gcu3'] and not c['gcu4'] and not c['ems3'] and not c['ems4'] and c['rpm_peak']==0 for c in f['3']['cycles'])
assert all(c['gcu3_to_rpm_transition_bracket_s'][0]>0 for c in f['2']['cycles'])
with (ROOT/'evidence-records.csv').open('w') as out:
 w=csv.DictWriter(out,fieldnames=list(evidence[0]));w.writeheader();w.writerows(evidence)
result={'verified':True,'sources':counts,'evidence_rows':len(evidence),'positive_cycles':4,'full_soc_control_cycles':5,'gcu3_precedes_observed_rpm_in_all_transition_brackets':True,'note':'Integrity and observed sequence verified. No ECU actuation or causal replay test was performed.'}
(ROOT/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
