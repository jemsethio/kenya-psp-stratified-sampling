"""Joint PSP-only and PSP+iShamba allocation from deduplicated provisional CGA list.
Audio on Nov 10: 315 planned enrolled per arm; NOT 267 plus inactive reserves.
DO NOT ACTIVATE until CGA + iShamba release. Only artifact_tool for Excel I/O.
"""
import os,math,hashlib
from collections import Counter,defaultdict
import numpy as np
import scipy.linalg
from artifact_tool import Blob,SpreadsheetFile,Workbook
BASE=os.environ.get('PSP_WORKDIR','/mnt/data')
SOURCE=BASE+'/Kenya_PSP_Step3_CORRECTED_Deduplicated_Draw.xlsx'
OUT=BASE+'/Kenya_PSP_JOINT_315x2_PROVISIONAL.xlsx'
SEED=20261110104
rng=np.random.default_rng(SEED)
county_target={'Meru':157,'Tharaka Nithi':158}
s=SpreadsheetFile.import_xlsx(Blob.load(SOURCE))
v=s.worksheets.get_item('01 Unique Candidate 1828').get_range('A1:W1829').values
h=v[0];rows=[dict(zip(h,r)) for r in v[1:]]
assert len(rows)==1828
for r in rows:
 r['key']=(r['County'],r['Provisional allocation group'])
 ph=r.get('Farmer phone (as supplied)')
 r['phone']=''.join(c for c in str(ph) if c.isdigit()) if ph else ''
groups=defaultdict(list)
for i,r in enumerate(rows):groups[r['key']].append(i)
keys=sorted(groups);assert len(keys)==24
allocation={}
for co,tar in county_target.items():
 ks=[g for g in keys if g[0]==co]
 total=sum(len(groups[g]) for g in ks)
 frac={g:tar*len(groups[g])/total for g in ks}
 for g in ks:allocation[g]=int(frac[g])
 for g in sorted(ks,key=lambda g:(-(frac[g]-int(frac[g])),g))[:tar-sum(allocation[g] for g in ks)]:allocation[g]+=1
 assert sum(allocation[g] for g in ks)==tar
 assert all(2*allocation[g]<=len(groups[g]) for g in ks)
pi=np.array([2*allocation[r['key']]/len(groups[r['key']]) for r in rows],dtype=float)
assert abs(pi.sum()-630)<1e-7
features=[]
for g in keys:features.append([float(r['key']==g) for r in rows])
features.append([float(r['Gender']=='Female') for r in rows])
for age in ['Youth 18-35','Unknown']:features.append([float(r['Age / youth']==age) for r in rows])
cc=Counter(r['Main crop'] for r in rows)
major=[k for k,n in sorted(cc.items()) if n>=10]
for crop in major:features.append([float(r['Main crop']==crop) for r in rows])
fsclist=sorted(set(r['FSC'] for r in rows))
for fsc in fsclist[:-1]:features.append([float(r['FSC']==fsc) for r in rows])
A=np.asarray(features,dtype=float)/pi[np.newaxis,:]

def move(p,idx,d):
 pos=d>1e-12; neg=d< -1e-12
 plus=[];minus=[]
 if pos.any():
  plus.extend(((1-p[idx[pos]])/d[pos]).tolist());minus.extend((p[idx[pos]]/d[pos]).tolist())
 if neg.any():
  plus.extend((p[idx[neg]]/(-d[neg])).tolist());minus.extend(((1-p[idx[neg]])/(-d[neg])).tolist())
 up=min(plus);dn=min(minus)
 if up<=0 or dn<=0:raise RuntimeError('Bad cube probability step')
 if rng.random()<dn/(up+dn):p[idx]+=up*d
 else:p[idx]-=dn*d
 p[idx]=np.clip(p[idx],0,1)

print('Cube flight: N',len(rows),'n',630,'auxiliary dimensions',A.shape[0],flush=True)
p=pi.copy();its=0
while True:
 active=np.flatnonzero((p>1e-10)&(p<1-1e-10))
 if len(active)<=A.shape[0]:break
 idx=rng.choice(active,size=A.shape[0]+1,replace=False)
 _,_,vh=scipy.linalg.svd(A[:,idx],full_matrices=True,lapack_driver='gesvd',check_finite=False)
 d=vh[-1].copy();d/=max(abs(d))
 assert np.linalg.norm(A[:,idx]@d)<1e-6
 move(p,idx,d);its+=1
 if its%300==0:print('Flight',its,'fractional',len(active),flush=True)
for g,idxs in groups.items():
 ii=np.array(idxs,dtype=int)
 while True:
  active=ii[(p[ii]>1e-10)&(p[ii]<1-1e-10)]
  if len(active)<2:break
  pair=rng.choice(active,size=2,replace=False)
  move(p,pair,np.array([1.,-1.]))
 assert abs(p[ii].sum()-2*allocation[g])<1e-5
chosen=np.rint(p).astype(int)
assert int(chosen.sum())==630
selected=list(np.flatnonzero(chosen))
selgroups={g:[i for i in groups[g] if chosen[i]] for g in keys}
assert all(len(selgroups[g])==2*allocation[g] for g in keys)

# Equal-per-ward assignment, rejecting phone cross-arm overlaps, with
# balanced constrained rerandomization across gender, youth, FSC and crops.
size=630
attr=[('Gender','Female',1.7),('Age / youth','Youth 18-35',1.5),('Age / youth','Unknown',1.0)]
for cat,n in Counter(rows[i]['Main crop'] for i in selected).items():
 if n>=4:attr.append(('Main crop',cat,0.9))
for cat,n in Counter(rows[i]['FSC'] for i in selected).items():
 if n>=5:attr.append(('FSC',cat,0.6))
feature_sets=[]
for field,val,weight in attr:
 members={i for i in selected if rows[i][field]==val}
 feature_sets.append((members,len(members),weight))
def measure(a):
 a=set(a);score=0.0
 for ids,n,weight in feature_sets:
  delta=2*len(a&ids)-n
  score+=weight*delta*delta/(n*(1-n/630)+1)
 for co in county_target:
  ids=[i for i in selected if rows[i]['County']==co]
  ca=a.intersection(ids)
  for field,val in [('Gender','Female'),('Age / youth','Youth 18-35')]:
   n=sum(rows[i][field]==val for i in ids)
   delta=2*sum(rows[i][field]==val for i in ca)-n
   score+=1.2*delta*delta/(n*(1-n/len(ids))+1)
 return score

print('Rerandomizing 315 per arm with shared-phone contamination safeguard',flush=True)
valid=[];attempt=0
while len(valid)<350 and attempt<30000:
 attempt+=1;a=[];b=[]
 for g in keys:
  ids=rng.permutation(selgroups[g]);m=allocation[g]
  a.extend(ids[:m].tolist());b.extend(ids[m:].tolist())
 pa={rows[i]['phone'] for i in a if rows[i]['phone']}
 pb={rows[i]['phone'] for i in b if rows[i]['phone']}
 if pa&pb:continue
 valid.append((measure(a),a,b))
if len(valid)<60:raise RuntimeError('No adequate shared-phone-safe assignments')
valid.sort(key=lambda item:item[0]);top=max(1,len(valid)//10)
score,a,b=valid[int(rng.integers(top))]
arm={i:'PSP only' for i in a};arm.update({i:'PSP + iShamba' for i in b})
assert len(a)==len(b)==315 and len(arm)==630
assert {rows[i]['phone'] for i in a if rows[i]['phone']}.isdisjoint({rows[i]['phone'] for i in b if rows[i]['phone']})
assert all(sum(i in a for i in selgroups[g])==allocation[g] for g in keys)
assert all(sum(i in b for i in selgroups[g])==allocation[g] for g in keys)
not_selected=sorted(set(range(1828))-set(arm))
assert len(not_selected)==1198
print('Joint randomization successful, valid splits',len(valid),'attempts',attempt,'balance score',round(score,3),flush=True)

contact_rank={}
for aa,bb in [('PSP only',a),('PSP + iShamba',b)]:
 for n,i in enumerate(rng.permutation(bb),1):contact_rank[int(i)]=n
head=['Study ID','Study arm','County','Source ward (unapproved)','Sampling geographic group','FSC','Gender','Age group','Main crop',
      'Farmer full name','Farmer phone (raw)','Phone quality','Shared phone group size','Excluded-list phone overlap','Duplicate metadata conflicts',
      'Original priority','Source row','Random enrollment order','Pool inclusion probability','Arm assignment chance if selected',
      'Partner identity approval','Prior exposure clearance','Consent / data-sharing','SMS activation status']
def data(i):
 r=rows[i]
 return [r['Study_ID'],arm.get(i,'Not selected'),r['County'],r['Ward (unapproved)'],r['Provisional allocation group'],r['FSC'],
 r['Gender'],r['Age / youth'],r['Main crop'],r['Farmer full name'],str(r['Farmer phone (as supplied)'] or ''),r['Contact check'],
 r['Shared phone: source count'],r['Removed-list phone overlap'],r['Duplicate metadata conflicts (review)'],r['Original priority'],
 r['Source row'],contact_rank.get(i),round(float(pi[i]),9),0.5 if i in arm else None,'PENDING','PENDING','NOT AUTHORIZED','HOLD — DO NOT SEND']

a_rows=sorted((data(i) for i in a),key=lambda r:(r[2],r[4],r[17]))
b_rows=sorted((data(i) for i in b),key=lambda r:(r[2],r[4],r[17]))
master=a_rows+b_rows+[data(i) for i in not_selected]

allocrows=[]
for g in keys:
 ids=groups[g]
 allocrows.append([g[0],g[1],len(ids),allocation[g],allocation[g],sum(i in a for i in ids),sum(i in b for i in ids),2*allocation[g],round(2*allocation[g]/len(ids),9),'PENDING CGA GEOGRAPHY CHECK'])
balrows=[]
for label,col in [('County','County'),('Ward group','Provisional allocation group'),('FSC','FSC'),('Gender','Gender'),('Age/youth','Age / youth'),('Main crop','Main crop')]:
 pop=Counter(r[col] for r in rows)
 aa=Counter(rows[i][col] for i in a);bb=Counter(rows[i][col] for i in b)
 for category,N in sorted(pop.items(),key=lambda x:(-x[1],str(x[0]))):
  balrows.append([label,category,N,round(N/1828*100,2),aa[category],bb[category],round(aa[category]/315*100,2),round(bb[category]/315*100,2),round((aa[category]-bb[category])/315*100,2),round((aa[category]+bb[category])/630*100-N/1828*100,2)])
contact_issues=[]
for study,ids in [('PSP only',a),('PSP + iShamba',b)]:
 phones=defaultdict(list)
 for i in ids:
  if rows[i]['phone']:phones[rows[i]['phone']].append(i)
 for phone,ii in phones.items():
  if len(ii)>1:
   contact_issues.append([phone,study,len(ii),', '.join(rows[i]['Study_ID'] for i in ii),', '.join(str(rows[i]['Farmer full name']) for i in ii),'RETAIN BOTH; CHECK ACTUAL EXPOSURE / SMS DELIVERY'])
flags=[]
for i in selected:
 r=rows[i];f=[]
 if r['Original priority']=='HIGH':f.append('high original review flag')
 if r['Duplicate metadata conflicts (review)']:f.append('metadata discrepancy')
 if r['Contact check'] not in ('VALID','',None):f.append('phone format / missing')
 if (r['Removed-list phone overlap'] or 0)>0:f.append('removed-list phone overlap: identify person')
 if (r['Shared phone: source count'] or 0)>1:f.append('shared phone: keep farmer')
 if f:flags.append([r['Study_ID'],arm[i],r['County'],r['Farmer full name'],str(r['Farmer phone (as supplied)'] or ''),'; '.join(f),'PENDING'])

w=Workbook.create()
navy='#183451';white='#FFFFFF';teal='#126C72'
def add(name,headers,records,widths=None):
 sh=w.worksheets.add(name)
 allvals=[headers]+records
 sh.get_range_by_indexes(0,0,len(allvals),len(headers)).values=allvals
 sh.get_range_by_indexes(0,0,1,len(headers)).format={'fill':navy,'font':{'bold':True,'color':white},'row_height':36,'wrap_text':True}
 for j,width in enumerate(widths or []):sh.get_range_by_indexes(0,j,len(allvals),1).format.column_width=width
 sh.freeze_panes.freeze_rows(1)
 return sh

summary=[['PROJECT','KENYA 2026 OND | JOINT PSP ARM RANDOMIZATION'],
 ['STATUS','PROVISIONAL — NO SMS OR CONTACT DATA TRANSFER AUTHORIZED'],
 ['Interpretation of Nov 10 audio','315 selected per arm; iShamba plans to enroll the full 315 in the digital group freshly'],
 ['Original CGA PSP registrations',1976],['Excluded previously exposed registrations (from supplied cleaned list)',76],
 ['Cleaned source registrations',1900],['Removed duplicate registrations by exact name + phone',67],
 ['Unique source identities',1833],['Exact earlier-exposed identity holds',5],['Provisional unique eligible farmer identities',1828],
 ['PSP-only allocated',315],['PSP+iShamba allocated',315],['Total uniquely allocated',630],['Unselected provisionally eligible',1198],
 ['PSP only Meru',157],['PSP only Tharaka Nithi',158],['PSP+iShamba Meru',157],['PSP+iShamba Tharaka Nithi',158],
 ['Target per arm after ~15% nonparticipation',267],['Extra allocation per arm',48],
 ['Matched phone used in opposite arms',0],['Within-arm shared phone contacts',len(contact_issues)],
 ['Finger Millet','CONFIRMED — after dedup/holds, 111 in eligible candidate frame'],
 ['Unique farmers, shared phone numbers','RETAIN; not an exclusion reason'],
 ['Questionable phone formats','RETAIN with verification flags'],
 ['Statistical design','Stratified county/ward-group balanced cube sampling, followed by constrained symmetric randomized two-arm split'],
 ['Allocation seed',SEED],['Randomization balance score',round(score,4)],['Cube flight steps',its],
 ['Valid pairwise allocations tested',len(valid)],['Assignment rerandomization attempts',attempt],
 ['Prior PSP+iShamba 267-person draw','SUPERSEDED'],
 ['Operational requirement','Both 315-person groups must be approved, with special urgency on the fresh iShamba group'],
 ['No automatic enrollment','Partner clearance required; preserve 5 exposed holds, open QA and geographic signoff'],
 ['Nyandarua iShamba-only and controls','NOT part of this draw (separate geographic and registry frames)']]
add('00 Dashboard',['Indicator','Value'],summary,[62,125])
add('01 PSP ONLY 315',head,a_rows,[22,21,21,28,32,23,17,18,22,28,21,19,22,23,38,19,18,19,23,23,22,22,22,23])
add('02 PSP+iShamba 315',head,b_rows,[22,21,21,28,32,23,17,18,22,28,21,19,22,23,38,19,18,19,23,23,22,22,22,23])
add('03 All 1828 Candidates',head,master,[22,21,21,28,32,23,17,18,22,28,21,19,22,23,38,19,18,19,23,23,22,22,22,23])
add('04 Strata Allocation',['County','Provisional ward group','Frame N','PSP-only allocated','PSP+iShamba allocated','PSP-only actual','PSP+iShamba actual','Total selected','Pool pi','Ward validation'],allocrows,[22,33,16,22,24,21,24,19,18,37])
add('05 Five-Variable Balance',['Dimension','Value','Frame N','Frame %','PSP-only N','PSP+iShamba N','PSP-only %','PSP+iShamba %','A minus B pp','Selected minus frame pp'],balrows,[21,28,19,19,21,22,20,23,20,28])
add('06 Selected QA Queue',['Study ID','Arm','County','Farmer','Phone','Flags','Clearance'],flags,[23,23,21,30,21,90,23])
add('07 Shared Phone Inside Arm',['Phone','Arm','Different farmers','Study IDs','Names','Action'],contact_issues,[24,28,22,45,50,65])
d=s.worksheets.get_item('05 Surplus Duplicates 67').get_range('A1:Q68').values
add('08 Exact Duplicate Audit',d[0],d[1:],[22]*17)
e=s.worksheets.get_item('06 Exposure Holds 5').get_range('A1:J6').values
add('09 Exposure Holds',e[0],e[1:],[24]*10)
protocol=[['01 Audio','315 in each PSP group drawn from the same 1,900-registration CGA frame. All 315 iShamba arm members intended for fresh advisory enrollment.'],
 ['02 Method','Dedup 1,900: exact name and phone -> 1,833 distinct records; 5 earlier exposed exact identities held -> 1,828 eligible provisional candidates.'],
 ['03 Two study arms','Randomize 630 unique farmers jointly; 315 PSP only, 315 PSP+iShamba, with no overlapping study IDs.'],
 ['04 Original study target','267 analyzed farmers per arm; 315 is ceil(267/0.85) and should not be confused with 267 enrolled and 48 inactive reserves.'],
 ['05 Geographic allocation','Each treatment arm has Meru 157 and Tharaka Nithi 158; exact county-ward-group equality, with ward dictionaries still provisional.'],
 ['06 Design selection','Randomized balanced cube flight with pi(pool)=2*n_h/N_h and exact ward-group pivotal landing.'],
 ['07 Arm assignment','Symmetric random rerandomization: each group split 1:1, preserve ward counts, no shared phone in opposite arms, balance FSC/gender/youth/crops.'],
 ['08 Consent','DO NOT send details or SMS until NDA, lawful contact purposes, consent/opt-out mechanism and partner approval are confirmed.'],
 ['09 Shared phone','Retained if different farmers share number. Avoid allocating a shared number to both arms, monitor within-arm shared contact exposure.'],
 ['10 Prior exposure','76 removed before sampling; 5 reappeared with exactly same name+phone and remain on hold. Phone-only overlap flagged not excluded.'],
 ['11 Duplicate metadata','Keep canonical first-listed metadata while flagging contradictions for CGA sign-off. Do not silently harmonize ages/FSC/crops.'],
 ['12 Main crop','Finger Millet confirmed in cleaned Sheet1; all types balanced at major-crop level, rare crops retained in original labels.'],
 ['13 Urgency','Operational priority: fresh PSP+iShamba enrollment. PSP-only allocation is done simultaneously to protect study comparability.'],
 ['14 Nyandarua','Other 266 iShamba-only and 400 comparison group NOT sampled here; require independent sampling frame and contamination checks.'],
 ['15 Individual exposure','Track each farmer PSP exposure, actual digital enrollment, actual SMS receipts, sharing, opt-outs and endline survey status.'],
 ['16 Sampling inference','Pool inclusion pi_h=2*n_h/N_h; arm assigned 1/2 symmetrically conditional on pool. Calibrated balancing and shared-phone restrictions affect joint probabilities.'],
 ['17 No manual substitutions','If ineligible verified before exposure, redo draw from revised approved frame or use predeclared auditable restricted redraw; not subjective swaps.'],
 ['18 Random seed',str(SEED)],['19 Input SHA256',hashlib.sha256(open(SOURCE,'rb').read()).hexdigest()],
 ['20 Important','This workbook completely supersedes the prior single-arm draw.'],
 ['21 Open decision','315 iShamba recipients vs 267 analytical target is resolved by AUDIO in favor of fresh enrollment of 315, subject to partner approval.']]
add('10 Protocol & Audio',['Rule','Explanation'],protocol,[37,125])
print('Exporting workbook',OUT,flush=True)
SpreadsheetFile.export_xlsx(w).save(OUT)
assert os.path.isfile(OUT) and os.path.getsize(OUT)>100000
print('DONE',os.path.getsize(OUT),'bytes',flush=True)
print('COUNTY A',Counter(rows[i]['County'] for i in a),'COUNTY B',Counter(rows[i]['County'] for i in b),flush=True)
print('BALANCE: gender',Counter(rows[i]['Gender'] for i in a),Counter(rows[i]['Gender'] for i in b),flush=True)
print('BALANCE: age',Counter(rows[i]['Age / youth'] for i in a),Counter(rows[i]['Age / youth'] for i in b),flush=True)
print('BALANCE: finger millet',sum(rows[i]['Main crop']=='Finger Millet' for i in a),sum(rows[i]['Main crop']=='Finger Millet' for i in b),flush=True)
print('QA selected',len(flags),'shared in-arm phones',len(contact_issues),flush=True)
