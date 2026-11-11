"""Independent transparent tests of the frozen Kenya PSP custom randomization.
Does not modify farmer allocations, source workbook, or contact details.
- Full deterministic replay: provided as original draw plus independently executed copy.
- Numerical pilot simulation of cube flight/pivotal landing on toy finite population.
- Weighted balancing diagnostics and arm-symmetry check on actual 630 assignments.
"""
import os
import json, math
from collections import Counter,defaultdict
import numpy as np
from scipy.linalg import svd
from artifact_tool import Blob,SpreadsheetFile
BASE=os.environ.get('PSP_WORKDIR','/mnt/data').rstrip('/')+'/'
W=SpreadsheetFile.import_xlsx(Blob.load(BASE+'Kenya_PSP_JOINT_315x2_PROVISIONAL.xlsx'))
v=W.worksheets.get_item('03 All 1828 Candidates').get_range('A1:X1829').values
rows=[dict(zip(v[0],r)) for r in v[1:]]
bygroup=defaultdict(list)
for r in rows: bygroup[(r['County'],r['Sampling geographic group'])].append(r)
keys=sorted(bygroup)
selected=[r for r in rows if r['Study arm']!='Not selected']
a=[r for r in rows if r['Study arm']=='PSP only']; b=[r for r in rows if r['Study arm']=='PSP + iShamba']
assert len(a)==len(b)==315 and len(selected)==630
# Audit the same score in original script: weighted discrepancy on whole sample and within county.
attr=[('Gender','Female',1.7),('Age group','Youth 18-35',1.5),('Age group','Unknown',1.0)]
for cat,n in Counter(r['Main crop'] for r in selected).items():
 if n>=4:attr.append(('Main crop',cat,0.9))
for cat,n in Counter(r['FSC'] for r in selected).items():
 if n>=5:attr.append(('FSC',cat,0.6))
def score(aa):
 sc=0.
 for field,val,weight in attr:
  n=sum(r[field]==val for r in selected)
  v=sum(r[field]==val for r in aa)
  delta=2*v-n
  sc+=weight*delta*delta/(n*(1-n/630)+1)
 for co in ('Meru','Tharaka Nithi'):
  tot=[r for r in selected if r['County']==co]
  sub=[r for r in aa if r['County']==co]
  for field,val in [('Gender','Female'),('Age group','Youth 18-35')]:
   n=sum(r[field]==val for r in tot); k=sum(r[field]==val for r in sub)
   d=2*k-n
   sc+=1.2*d*d/(n*(1-n/len(tot))+1)
 return sc
obs=score(a);reverse=score(b)
assert abs(obs-reverse)<1e-10
# Stage 1 HT totals, primary balance diagnostics
cats=[('County–geographic group','Sampling geographic group'),('FSC','FSC'),('Gender','Gender'),('Age','Age group'),('Crop','Main crop')]
summary=[]; detail=[]
for dom,field in cats:
 count=Counter((str(r['County'])+' | '+str(r[field])) if dom=='County–geographic group' else str(r[field]) for r in rows)
 for category,n in sorted(count.items()):
  ht=sum(1/r['Pool inclusion probability'] for r in selected if ((str(r['County'])+' | '+str(r[field])) if dom=='County–geographic group' else str(r[field]))==category)
  diff=ht-n
  detail.append({'domain':dom,'category':category,'frame_n':n,'selected_n':sum(((str(r['County'])+' | '+str(r[field])) if dom=='County–geographic group' else str(r[field]))==category for r in selected),'weighted_ht':ht,'residual':diff,'residual_pp_of_N':100*diff/len(rows)})
 d=[x for x in detail if x['domain']==dom]
 summary.append({'domain':dom,'categories':len(d),'max_abs_residual_pp':max(abs(x['residual_pp_of_N']) for x in d),'mean_abs_residual_pp':float(np.mean([abs(x['residual_pp_of_N']) for x in d]))})
# Toy population empirical test using production-style SVD flight/within-block pivotal landing
rng=np.random.default_rng(10777)
N=24
block=np.array([0]*10+[1]*14)
nh={0:3,1:5}
pi=np.array([nh[int(h)]/sum(block==h) for h in block])
X=np.array([
  (block==0).astype(float),(block==1).astype(float),
  (np.arange(N)%3==0).astype(float),(np.arange(N)%5<2).astype(float),
],dtype=float)
M=X/pi

def move(p,idx,v):
 pos=v>1e-12;neg=v<-1e-12
 plus=[];minus=[]
 if np.any(pos):
  plus.extend(((1-p[idx[pos]])/v[pos]).tolist());minus.extend((p[idx[pos]]/v[pos]).tolist())
 if np.any(neg):
  plus.extend((p[idx[neg]]/-v[neg]).tolist());minus.extend(((1-p[idx[neg]])/-v[neg]).tolist())
 up=min(plus);dn=min(minus)
 if rng.random()<dn/(up+dn):p[idx]+=up*v
 else:p[idx]-=dn*v
 p[idx]=np.clip(p[idx],0,1)

def draw():
 p=pi.copy();q=M.shape[0]
 while True:
  active=np.flatnonzero((p>1e-10)&(p<1-1e-10))
  if len(active)<=q:break
  idx=rng.choice(active,q+1,replace=False)
  _,_,vh=svd(M[:,idx],full_matrices=True,lapack_driver='gesvd',check_finite=False)
  v=vh[-1,:];v=v/max(abs(v));move(p,idx,v)
 for h in [0,1]:
  indexes=np.where(block==h)[0]
  while True:
   active=indexes[(p[indexes]>1e-10)&(p[indexes]<1-1e-10)]
   if len(active)<2:break
   pair=rng.choice(active,2,replace=False);move(p,pair,np.array([1.,-1.]))
  assert round(p[indexes].sum())==nh[h]
 z=np.rint(p).astype(int)
 assert z.sum()==8 and all(z[block==h].sum()==nh[h] for h in [0,1])
 return z
R=1200
z=np.asarray([draw() for _ in range(R)])
frequencies=z.mean(axis=0)
toy={'draws':R,'expected_pi_min':float(pi.min()),'expected_pi_max':float(pi.max()),'max_abs_pi_deviation':float(max(abs(frequencies-pi))),
     'rmse_empirical_pi':float(np.sqrt(np.mean((frequencies-pi)**2))), 'mean_abs_pi_deviation':float(np.mean(abs(frequencies-pi)))}
# Exact assignment invariants
checks={
 'unique_assigned_study_ids':len({r['Study ID'] for r in selected})==630,
 'frozen_arm_sizes_315_each':len(a)==len(b)==315,
 'exact_county_ward_group_equality':all(sum(r['Study arm']=='PSP only' for r in g)==sum(r['Study arm']=='PSP + iShamba' for r in g) for g in bygroup.values()),
 'no_cross_arm_shared_phones':not ({''.join(c for c in str(r['Farmer phone (raw)']) if c.isdigit()) for r in a if r['Farmer phone (raw)']} & {''.join(c for c in str(r['Farmer phone (raw)']) if c.isdigit()) for r in b if r['Farmer phone (raw)']}),
 'score_arm_label_symmetry':abs(obs-reverse)<1e-10
}
result={'checks':checks,'observed_balance_score':obs,'reverse_label_balance_score':reverse,'ht_domain_summary':summary,'ht_detail':detail,'toy_probability_test':toy,
        'limitations':['Toy simulation validates unbiased transitions in a small analogue, not empirical full-frame inclusion probabilities.',
        'A single realized sample cannot establish inclusion probabilities by itself.',
        'Symmetry of the assignment score supports equal arm probabilities; imposed restrictions affect joint assignment probabilities.',
        'County–ward groups are provisional and not automatically official wards.']}
with open(BASE+'PSP_Independent_Algorithm_Tests.json','w') as f:json.dump(result,f,indent=2)
print(json.dumps({k:v for k,v in result.items() if k!='ht_detail'},indent=2))
