"""Kenya OND 2026 PSP: deduplicate identical (full name, phone), hold exact prior-exposure matches,
rerun provisional county/ward stratified cube-balanced random selection, export auditable workbook.

All original records are preserved in traceable registers. Shared phones among DIFFERENT names
and imperfect phone formats DO NOT cause an exclusion. No enrollment is authorized.
"""
from __future__ import annotations
import os, re, time, math, hashlib, unicodedata
from collections import Counter, defaultdict
import numpy as np
import scipy.linalg
from artifact_tool import Blob, SpreadsheetFile, Workbook

BASE=os.environ.get('PSP_WORKDIR','/mnt/data')
SOURCE=f'{BASE}/Kenya_PSP_Step1_Finger_Millet_Confirmed.xlsx'
OLDALLOC=f'{BASE}/Kenya_PSP_Step2_Ward_Allocation_Finger_Millet_Confirmed.xlsx'
OUT=f'{BASE}/Kenya_PSP_Step3_CORRECTED_Deduplicated_Draw.xlsx'
SEED=20261110
rng=np.random.default_rng(SEED)
TARGET={'Meru':133,'Tharaka Nithi':134}
RESERVE={'Meru':23,'Tharaka Nithi':23}

def norm(v):
    if v is None:return ''
    return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',str(v)).strip()).casefold()

def phone_key(r):
    if norm(r['Phone_Quality'])=='valid' and r['Farmer_Phone_E164']:
        return str(r['Farmer_Phone_E164']).strip()
    return re.sub(r'\D','',str(r['Farmer_Contact_Raw'] or ''))

def hashfile(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
    return h.hexdigest()

print('Load source records and previous provisional ward mapping',flush=True)
source=SpreadsheetFile.import_xlsx(Blob.load(SOURCE))
rr=source.worksheets.get_item('Provisional_Frame').get_range('A1:AR1901').values
headers=rr[0]
all_records=[dict(zip(headers,row)) for row in rr[1:]]
assert len(all_records)==1900
allocsrc=SpreadsheetFile.import_xlsx(Blob.load(OLDALLOC))
maprows=allocsrc.worksheets.get_item('02 Ward Dictionary').get_range('A5:H52').values
wardmap={(r[0],r[1]):r[4] for r in maprows if r[0] in TARGET and r[1] is not None}

# One person defined operationally by normalized full name + normalized phone; names and raw values preserved.
identity=defaultdict(list)
for ix,r in enumerate(all_records):
    n=norm(r['Farmer_Name_Raw']);p=phone_key(r)
    if n and p: identity[(n,p)].append(ix)
    else: identity[('unmatchable',str(ix))].append(ix)

duplicate_groups=[x for x in identity.values() if len(x)>1]
assert len(duplicate_groups)==65
assert sum(len(x)-1 for x in duplicate_groups)==67
# First-listed original record is canonical: no arbitrary choice among conflicting FSC/age/crop entries.
canonical_indices=set(min(v) for v in identity.values())
dropped_index_to_keeper={ix:min(v) for v in identity.values() for ix in v if ix!=min(v)}
canonical=[all_records[i] for i in sorted(canonical_indices)]
assert len(canonical)==1833
field_names=['County_Std','Ward_Normalized_Unapproved','FSC_Name_Normalized','Gender_Std','Age_Std','Main_Crop_Normalized','Village_Raw']
issues_for_kept={}
for members in duplicate_groups:
    k=min(members)
    conflicts=[f for f in field_names if len({norm(all_records[i].get(f)) for i in members})>1]
    issues_for_kept[all_records[k]['Study_ID']]=conflicts

# Five exact (name, phone) matches to known removed-list prior advisory exposure: do not draw until cleared.
# One phone-only overlap is NOT excluded because two different farmers can share a phone.
held=[r for r in canonical if int(r['Removed_List_NamePhone_Matches'] or 0)>0]
assert len(held)==5
candidates=[r for r in canonical if int(r['Removed_List_NamePhone_Matches'] or 0)==0]
assert len(candidates)==1828
for r in candidates:
    k=(r['County_Std'],r['Ward_Normalized_Unapproved'])
    if k not in wardmap:raise RuntimeError(f'No provisional ward mapping for {k}')
    r['Allocation_Group']=wardmap[k]
    r['Group_Key']=(r['County_Std'],r['Allocation_Group'])
for r in held:
    r['Allocation_Group']=wardmap[(r['County_Std'],r['Ward_Normalized_Unapproved'])]
    r['Group_Key']=(r['County_Std'],r['Allocation_Group'])

bygroup=defaultdict(list)
for i,r in enumerate(candidates): bygroup[r['Group_Key']].append(i)
groups=sorted(bygroup)
assert len(groups)==24
alloc={}
for county,target in TARGET.items():
    cc=sorted(k for k in groups if k[0]==county)
    total=sum(len(bygroup[k]) for k in cc)
    fractional={k:len(bygroup[k])*target/total for k in cc}
    alloc.update({k:int(math.floor(fractional[k])) for k in cc})
    rest=target-sum(alloc[k] for k in cc)
    for k in sorted(cc,key=lambda k:(-(fractional[k]-math.floor(fractional[k])),k))[:rest]: alloc[k]+=1
    assert sum(alloc[k] for k in cc)==target
    assert all(0<alloc[k]<=len(bygroup[k]) for k in cc),[(k,len(bygroup[k]),alloc[k]) for k in cc]
pi=np.array([alloc[r['Group_Key']]/len(bygroup[r['Group_Key']]) for r in candidates],float)
assert abs(sum(pi)-267)<1e-8

# Balanced randomized cube flight followed by equal-pi within-stratum pivotal landing.
major_crops=sorted(x for x,n in Counter(r['Main_Crop_Normalized'] for r in candidates).items() if n>=10)
fsclist=sorted(set(r['FSC_Name_Normalized'] for r in candidates))
feature_names=[]; features=[]
for k in groups:
    feature_names.append(f'Ward allocation | {k[0]} / {k[1]}')
    features.append(np.array([float(r['Group_Key']==k) for r in candidates]))
for val,name in [('Female','Gender Female')]:
    feature_names.append(name);features.append(np.array([float(r['Gender_Std']==val) for r in candidates]))
for val in ('Youth 18-35','Unknown'):
    feature_names.append('Age '+val);features.append(np.array([float(r['Age_Std']==val) for r in candidates]))
for val in major_crops:
    feature_names.append('Crop '+val);features.append(np.array([float(r['Main_Crop_Normalized']==val) for r in candidates]))
for val in fsclist[:-1]:
    feature_names.append('FSC '+str(val));features.append(np.array([float(r['FSC_Name_Normalized']==val) for r in candidates]))
X=np.asarray(features,dtype=float); A=X/pi[np.newaxis,:]

def move_unbiased(p,indices,v):
    pos=v>1e-12; neg=v<-1e-12
    plus_candidates=[]
    minus_candidates=[]
    if pos.any():
        plus_candidates.extend(((1-p[indices[pos]])/v[pos]).tolist())
        minus_candidates.extend((p[indices[pos]]/v[pos]).tolist())
    if neg.any():
        plus_candidates.extend((p[indices[neg]]/(-v[neg])).tolist())
        minus_candidates.extend(((1-p[indices[neg]])/(-v[neg])).tolist())
    plus=min(plus_candidates)
    minus=min(minus_candidates)
    if plus<=0 or minus<=0:raise RuntimeError('Invalid randomized balancing move')
    if rng.random()<minus/(plus+minus):p[indices]+=plus*v
    else:p[indices]-=minus*v
    p[indices]=np.clip(p[indices],0,1)
    return p

def balanced_draw(p):
    q=A.shape[0]
    steps=0
    while True:
        active=np.flatnonzero((p>1e-10)&(p<1-1e-10))
        if len(active)<=q:break
        cand=rng.choice(active,size=q+1,replace=False)
        # Null direction for q+1 columns; scipy SVD is deterministic for this fixed matrix.
        _u,_s,vh=scipy.linalg.svd(A[:,cand],full_matrices=True,check_finite=False,lapack_driver='gesvd')
        v=vh[-1,:].copy();mx=np.max(abs(v))
        if mx<=1e-14 or np.linalg.norm(A[:,cand]@v)>1e-6:raise RuntimeError('Unstable null direction')
        v/=mx
        p=move_unbiased(p,cand,v)
        steps+=1
        if steps%300==0:print('Cube flight steps',steps,'fractional',len(active),flush=True)
        if steps>2500:raise RuntimeError('Unexpectedly long cube flight')
    for k,inds in bygroup.items():
        ii=np.asarray(inds,dtype=int)
        while True:
            active=ii[(p[ii]>1e-10)&(p[ii]<1-1e-10)]
            if len(active)<2:break
            pair=rng.choice(active,size=2,replace=False)
            p=move_unbiased(p,pair,np.array([1.,-1.]))
        active=ii[(p[ii]>1e-10)&(p[ii]<1-1e-10)]
        if len(active)==1:
            if abs(p[active[0]]-round(p[active[0]]))>1e-6:raise RuntimeError('Unexpected residual fractional sample')
            p[active[0]]=round(p[active[0]])
        if abs(p[ii].sum()-alloc[k])>1e-6:raise RuntimeError('Ward quota failure')
    return np.rint(p).astype(int),steps

print('Execute corrected balanced draw',len(candidates),'candidates',len(feature_names),'features',flush=True)
selected,flight_steps=balanced_draw(pi.copy())
chosen=set(np.flatnonzero(selected))
assert len(chosen)==267
assert all(int(selected[bygroup[k]].sum())==alloc[k] for k in groups)
assert len({(norm(candidates[i]['Farmer_Name_Raw']),phone_key(candidates[i])) for i in chosen})==267

# Pre-rank residual identities separately in each geographic group.
remaining={k:[i for i in ix if i not in chosen] for k,ix in bygroup.items()}
for k,inds in remaining.items():rng.shuffle(inds)
reserve_n={}
for county,target in RESERVE.items():
    ks=[k for k in groups if k[0]==county]
    total=sum(len(remaining[k]) for k in ks)
    fraction={k:target*len(remaining[k])/total for k in ks}
    reserve_n.update({k:int(math.floor(fraction[k])) for k in ks})
    rest=target-sum(reserve_n[k] for k in ks)
    for k in sorted(ks,key=lambda k:(-(fraction[k]-math.floor(fraction[k])),k))[:rest]:reserve_n[k]+=1
    assert sum(reserve_n[k] for k in ks)==target
status={}; rank={}
for k,inds in remaining.items():
    for j,i in enumerate(inds,1):
        rank[i]=j
        status[i]='RESERVE 1' if j<=reserve_n[k] else 'RESERVE 2 - standby'
for k,inds in bygroup.items():
    prim=sorted(i for i in inds if i in chosen);rng.shuffle(prim)
    for j,i in enumerate(prim,1):status[i]='PRIMARY';rank[i]=j
assert Counter(status.values())==Counter({'PRIMARY':267,'RESERVE 1':46,'RESERVE 2 - standby':1515})

fields=['Study_ID','County_Std','Ward_Normalized_Unapproved','Allocation_Group','FSC_Name_Normalized',
        'Gender_Std','Age_Std','Main_Crop_Normalized','Farmer_Name_Raw','Farmer_Contact_Raw',
        'Phone_Quality','Shared_Phone_Group_Size','Removed_List_Phone_Matches','Removed_List_NamePhone_Matches',
        'Review_Flags','Priority','Clean_Sheet_Row']
mainhead=['Study_ID','County','Ward (unapproved)','Provisional allocation group','FSC',
          'Gender','Age / youth','Main crop','Farmer full name','Farmer phone (as supplied)',
          'Contact check','Shared phone: source count','Removed-list phone overlap','Removed-list exact identity',
          'Original QA flags','Original priority','Source row','Sampling status','Rank in geographic group','Inclusion probability',
          'Duplicate metadata conflicts (review)','Contact permission','Reviewer decision']

def candidate_row(r,i):
    vals=[r.get(f) for f in fields]
    for j in (9,):
        if vals[j] is not None:vals[j]=str(vals[j])
    return vals+[status[i],rank[i],round(float(pi[i]),9),
                 '; '.join(issues_for_kept.get(r['Study_ID'],[])),
                 'HOLD - NOT AUTHORIZED for SMS',None]
master=[candidate_row(r,i) for i,r in enumerate(candidates)]
primary=sorted([candidate_row(r,i) for i,r in enumerate(candidates) if i in chosen],key=lambda x:(x[1],x[3],x[18]))
tier1=sorted([candidate_row(r,i) for i,r in enumerate(candidates) if status[i]=='RESERVE 1'],key=lambda x:(x[1],x[3],x[18]))
tier2=sorted([candidate_row(r,i) for i,r in enumerate(candidates) if status[i]=='RESERVE 2 - standby'],key=lambda x:(x[1],x[3],x[18]))

# Exact-identity duplicate registration register, no automatic reconciliation of conflicting metadata.
drophead=['Duplicate Study ID','Canonical Study ID','Canonical source row','Duplicate source row','County','Ward duplicate','FSC canonical','FSC duplicate',
          'Age canonical','Age duplicate','Crop canonical','Crop duplicate','Full name duplicate','Phone duplicate','Conflicting fields','Resolution','CGA signoff']
dropped=[]
for ix,keeper in sorted(dropped_index_to_keeper.items()):
    r=all_records[ix]; k=all_records[keeper]
    cf=[f for f in field_names if norm(k.get(f))!=norm(r.get(f))]
    dropped.append([r['Study_ID'],k['Study_ID'],k['Clean_Sheet_Row'],r['Clean_Sheet_Row'],r['County_Std'],r['Ward_Normalized_Unapproved'],
                    k['FSC_Name_Normalized'],r['FSC_Name_Normalized'],k['Age_Std'],r['Age_Std'],k['Main_Crop_Normalized'],r['Main_Crop_Normalized'],
                    r['Farmer_Name_Raw'],str(r['Farmer_Contact_Raw'] or ''),'; '.join(cf),'Duplicate registration — excluded from draw',None])
assert len(dropped)==67
holdhead=['Study_ID','County','Ward','Full name','Phone','Source row','Removed-list identity matches','Removed-list phone matches','Disposition','iShamba verdict']
holdrows=[[r['Study_ID'],r['County_Std'],r['Ward_Normalized_Unapproved'],r['Farmer_Name_Raw'],str(r['Farmer_Contact_Raw'] or ''),r['Clean_Sheet_Row'],
           r['Removed_List_NamePhone_Matches'],r['Removed_List_Phone_Matches'],'HELD: prior exposed identity likely; do not draw until verified',None] for r in held]

allochead=['County','Provisional ward allocation group','Frame N after dedup and hold','County eligible-to-draw N','County target','Expected n','Primary allocated','Actual primary','Primary probability',
           'Initial reserve allocated','Initial reserve actual','CGA geography approval']
allocrows=[]
for k in groups:
    county=k[0];countyN=sum(len(v) for group,v in bygroup.items() if group[0]==county)
    allocrows.append([k[0],k[1],len(bygroup[k]),countyN,TARGET[county],round(len(bygroup[k])*TARGET[county]/countyN,4),
                      alloc[k],int(sum(selected[bygroup[k]])),round(alloc[k]/len(bygroup[k]),9),reserve_n[k],
                      sum(status[i]=='RESERVE 1' for i in remaining[k]),'PENDING'])

balancehead=['Dimension','Category','Frame count','Expected selected count by design','Actual primary','Difference from expectation','Frame share %','Primary share %','Difference percentage points','Balanced input?']
balancerows=[]
cols=[('County','County_Std'),('Ward-group','Allocation_Group'),('Ward original','Ward_Normalized_Unapproved'),('FSC','FSC_Name_Normalized'),('Gender','Gender_Std'),('Age','Age_Std'),('Crop','Main_Crop_Normalized')]
for d,field in cols:
    cats=sorted(set(r[field] for r in candidates))
    for cat in cats:
        ix=[i for i,r in enumerate(candidates) if r[field]==cat]
        ex=pi[ix].sum();actual=int(selected[ix].sum());N=len(ix)
        balancerows.append([d,cat,N,round(float(ex),3),actual,round(actual-ex,3),round(100*N/1828,2),
                            round(100*actual/267,2),round((actual/267-N/1828)*100,2),
                            'YES' if (d in ('County','Ward-group','FSC','Gender','Age') or (d=='Crop' and cat in major_crops)) else 'AUDIT ONLY'])

warninghead=['Study_ID','Role','Priority','Name + phone duplicate conflict','County','Ward','Farmer','Phone','Phone quality','Shared phone records',
             'Potential removed-list shared phone','CGA review status']
warnrows=[]
for i,r in enumerate(candidates):
    if (r['Priority'] in ('HIGH','MEDIUM') or r['Phone_Quality']!='VALID' or issues_for_kept.get(r['Study_ID'])
       or int(r['Removed_List_Phone_Matches'] or 0)>0):
        warnrows.append([r['Study_ID'],status[i],r['Priority'],'; '.join(issues_for_kept.get(r['Study_ID'],[])),r['County_Std'],r['Ward_Normalized_Unapproved'],
                         r['Farmer_Name_Raw'],str(r['Farmer_Contact_Raw'] or ''),r['Phone_Quality'],r['Shared_Phone_Group_Size'],
                         r['Removed_List_Phone_Matches'],'PENDING'])

wb=Workbook.create()
navy='#17324D';teal='#0F766E';gold='#B7791F';white='#FFFFFF'
def add(name,header,rows,widths=None):
    s=wb.worksheets.add(name)
    data=[header]+rows
    s.get_range_by_indexes(0,0,len(data),len(header)).values=data
    s.get_range_by_indexes(0,0,1,len(header)).format={'fill':navy,'font':{'bold':True,'color':white},'row_height':32,'wrap_text':True}
    if len(rows):s.get_range_by_indexes(1,0,len(rows),len(header)).format.row_height=18
    for j,x in enumerate(widths or []):s.get_range_by_indexes(0,j,len(data),1).format.column_width=x
    try:s.freeze_panes.freeze_rows(1)
    except Exception:pass
    return s

summary=wb.worksheets.add('00 Decision Summary')
dash=[
['KENYA 2026 OND | CORRECTED DE-DUPLICATED PROVISIONAL DRAW',None,None],
['IMPORTANT: this draw supersedes the earlier 1,900-record draw; partner review required before activation.',None,None],
[None,None,None],
['METRIC','COUNT','INTERPRETATION'],
['Original cleaned registration records',1900,'Input after the separate list of 76 was removed'],
['Duplicate identity groups',65,'Normalized exact full name + phone'],
['Surplus repeated registrations excluded',67,'Only one canonical record retained per identity group'],
['Unique provisional farmer identities',1833,'1,900 - 67'],
['Exact-match prior-exposure identities HELD',5,'Matched full name and phone to 76-removed list; no draw pending verification'],
['Unique candidate identities in corrected draw',1828,'1,833 - 5'],
['Primary selected',267,'Meru 133 / Tharaka Nithi 134'],
['First reserve',46,'Pre-ranked, 23/county; NOT enrolled'],
['Deeper standby',1515,'All remaining provisional candidate identities pre-ranked'],
['Gender, age, FSC and crop balance','Balanced probability draw','County/ward group allocation retained'],
['Finger Millet classification','Confirmed','No pending finger vs pearl question'],
['Shared phone across different people','KEEP','Not an exclusion rule, even if number is same'],
['Questionable phone format','KEEP + LABEL','Contact verification before SMS only'],
['Same full name + same phone','ONE canonical row','Other records in duplicate audit for CGA reconciliation'],
['Recorded conflicting FSC / age / crop','NEEDS REVIEW','Canonical is earliest source row, not an assertion of correct metadata'],
['Re-randomization seed',SEED,'NumPy PCG64, see script'],
['Geographic labels','UNAPPROVED','Pending CGA validation; provisional pooling retained'],
['Exposure identity cross-check','HOLD','Five exact overlaps withheld, one phone-only overlap retained'],
['RELEASE STATUS','NOT APPROVED','Do not transmit contacts or start advisory delivery'],
]
summary.get_range('A1:C23').values=dash
summary.get_range('A1:C1').format={'fill':navy,'font':{'bold':True,'color':white,'size':16},'row_height':36}
summary.get_range('A2:C2').format={'fill':'#FFF1D6','font':{'bold':True,'color':'#943E18'},'wrap_text':True,'row_height':31}
summary.get_range('A4:C4').format={'fill':teal,'font':{'bold':True,'color':white},'row_height':27}
summary.get_range('A23:C23').format={'fill':'#FFF1D6','font':{'bold':True,'color':'#943E18'}}
for col,wi in zip('ABC',[49,33,95]):summary.get_range(f'{col}:{col}').format.column_width=wi
try:summary.freeze_panes.freeze_rows(4)
except Exception:pass

common_width=[20,18,24,29,29,14,19,20,27,24,20,18,18,18,52,15,15,24,21,19,48,31,20]
add('01 Unique Candidate 1828',mainhead,master,common_width)
add('02 Primary 267',mainhead,primary,common_width)
add('03 Reserve 46',mainhead,tier1,common_width)
add('04 Standby 1515',mainhead,tier2,common_width)
add('05 Surplus Duplicates 67',drophead,dropped,[20,20,20,20,18,25,27,27,18,18,22,22,28,23,56,43,20])
add('06 Exposure Holds 5',holdhead,holdrows,[20,18,25,28,24,16,25,24,60,24])
add('07 Revised Ward Allocation',allochead,allocrows,[18,38,18,22,16,19,20,20,20,21,20,23])
add('08 Balance Assessment',balancehead,balancerows,[21,39,17,25,19,27,17,19,27,21])
add('09 Open QA Queue',warninghead,warnrows,[19,22,16,48,18,25,28,21,25,20,22,25])
protocol=[
['01 Source workbook',SOURCE],['02 Source SHA256',hashfile(SOURCE)],['03 Previous ward grouping',OLDALLOC],
['04 Ward mapping SHA256',hashfile(OLDALLOC)],['05 Dedup rule','Exact normalized full farmer name and phone match; one registration per combination.'],
['06 Canonical record','Retain earliest clean-sheet row in matching identity group; do not overwrite conflicting values.'],
['07 Repeated registrations','65 identity groups, 132 records, 67 surplus entries moved to audit.'],
['08 Metadata disagreement','FSC 46 groups; crop 29 groups; age 6 groups; ward 1 group (not mutually exclusive).'],
['09 Shared phones','Different farmer names linked to same number remain separate farmer identities and are retained.'],
['10 Phone format','35 questionable and 6 missing in original frame; retained unless same-name/phone duplicate or held exact exposure.'],
['11 Prior exposure hold','Five exact name+phone matches with previously removed exposure list are quarantined, not randomized.'],
['12 Phone-only removed-list overlap','Retained and flagged; can be a distinct individual sharing a phone.'],
['13 Candidate N','1828 provisional distinct farmers eligible for corrected draw; 1833 total unique identities including 5 holds.'],
['14 Geographic allocations','Recalculated by Hamilton largest-remainder rounding within county after deduplication/hold.'],
['15 County sizes','Meru target 133, Tharaka Nithi target 134.'],
['16 Probability sampling','Stratified cube-style flight calibrated to X / pi, randomized pivotal landing within group.'],
['17 Covariates','24 geographic group indicators; female; youth and unknown; major crops N>=10; all FSC indicators except reference.'],
['18 Inclusion probabilities','pi_i = ward-group allocated n / provisional ward-group candidate N; unequal across groups.'],
['19 Reserve','46 first-tier reserves, 23 per county, geographically pre-ranked; further 1515 in standby.'],
['20 Replacement','If candidate declines BEFORE exposure, first next reserve in same provisional group; do not substitute after exposure.'],
['21 Random seed',str(SEED)],['22 Random generator','NumPy default_rng (PCG64)'],
['23 No PS-only assignment','The PSP-only arm has not been jointly randomized here.'],
['24 Manual validation','CGA must adjudicate canonical metadata disputes; iShamba confirm 5 exact exposure holds.'],
['25 Privacy / consent','Contains names and phone numbers, restricted to approved partners; NO SMS until authorized.'],
['26 Prior draw invalidated','Supersedes earlier provisional draw performed on 1,900 registration rows.'],
['27 Data corrections','After partner decisions, rerun from approved frame; do not manually swap farmers.'],
['28 Flight iterations',str(flight_steps)]
]
add('10 Methods and Decisions',['Rule','Specification'],protocol,[37,128])
assert len(master)==1828 and len(primary)==267 and len(tier1)==46 and len(tier2)==1515
assert len({r[0] for r in primary})==267
assert len(set(r[0] for r in primary)&set(r[0] for r in tier1))==0
print('Export corrected workbook',flush=True)
SpreadsheetFile.export_xlsx(wb).save(OUT)
print('DONE',OUT,'bytes',os.stat(OUT).st_size,flush=True)
print('COUNTY FRAME',Counter(r['County_Std'] for r in candidates),'COUNTY PRIMARY',Counter(candidates[i]['County_Std'] for i in chosen),flush=True)
print('PRIMARY DUPLICATE CONFLICT',sum(bool(issues_for_kept.get(candidates[i]['Study_ID'])) for i in chosen),flush=True)
print('PRIMARY OTHER HIGH',sum(candidates[i]['Priority']=='HIGH' for i in chosen),'FINGER MILLET',sum(candidates[i]['Main_Crop_Normalized']=='Finger Millet' for i in chosen),flush=True)
print('QA',len(warnrows),'DUP',len(dropped),'EXPOSURE_HOLDS',len(holdrows),'SEED',SEED,flush=True)
