"""Create de-identified scientific summaries and figures from the frozen assignment.

All generated outputs here contain only aggregate counts. Names, FSC identities,
telephone numbers, study IDs and per-person records are never exported.
"""
from __future__ import annotations
from collections import Counter,defaultdict
import csv,json,os,math
from pathlib import Path
from artifact_tool import Blob,SpreadsheetFile
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

p=Path(os.environ.get('PSP_WORKDIR','/mnt/data'))
public=p/'public_aggregate_results'; public.mkdir(exist_ok=True)
w=SpreadsheetFile.import_xlsx(Blob.load(str(p/'Kenya_PSP_JOINT_315x2_PROVISIONAL.xlsx')))
a=w.worksheets.get_item('01 PSP ONLY 315').get_range('A1:X316').values
b=w.worksheets.get_item('02 PSP+iShamba 315').get_range('A1:X316').values
frame=w.worksheets.get_item('03 All 1828 Candidates').get_range('A1:X1829').values
ra=[dict(zip(a[0],r)) for r in a[1:]]; rb=[dict(zip(b[0],r)) for r in b[1:]]
rf=[dict(zip(frame[0],r)) for r in frame[1:]]
assert len(ra)==len(rb)==315 and len(rf)==1828
assert not ({r['Study ID'] for r in ra}&{r['Study ID'] for r in rb})
assert len({r['Study ID'] for r in ra+rb})==630
assert all(r['Partner identity approval']=='PENDING' for r in ra+rb)

def phone(r):
    return ''.join(c for c in str(r.get('Farmer phone (raw)') or '') if c.isdigit())
pa={phone(r) for r in ra if phone(r)};pb={phone(r) for r in rb if phone(r)}
assert not pa&pb,'Shared contact across arms'

domains={'County':'County','Provisional geographic group':'Sampling geographic group','Gender':'Gender','Age/youth':'Age group','Main crop':'Main crop','FSC':'FSC'}
def dist(rs,field):
    if field=='Sampling geographic group':
        return Counter(str(r.get('County'))+' | '+str(r.get(field)) for r in rs)
    return Counter(str(r.get(field)) for r in rs)
def tvd(a,b):
    ca=dist(a,b);return ca

def balance(domain,field):
    ca,cb,cf=dist(ra,field),dist(rb,field),dist(rf,field)
    keys=set(ca)|set(cb)|set(cf)
    av={x:ca[x]/315 for x in keys};bv={x:cb[x]/315 for x in keys};fv={x:cf[x]/1828 for x in keys}
    t_ab=.5*sum(abs(av[x]-bv[x]) for x in keys)
    t_pop=.5*sum(abs((ca[x]+cb[x])/630-fv[x]) for x in keys)
    scores=[]
    for x in keys:
        x1,x2=av[x],bv[x]
        denominator=math.sqrt((x1*(1-x1)+x2*(1-x2))/2)
        if denominator>0:scores.append((x,abs(x1-x2)/denominator))
    return dict(domain=domain, categories=len(keys),tvd_between_arms=t_ab,tvd_selected_vs_frame=t_pop,max_abs_smd=max((v for _,v in scores),default=0))
stats=[balance(k,v) for k,v in domains.items()]
with (public/'balance_domain.csv').open('w',newline='') as f:
    d=csv.DictWriter(f,fieldnames=list(stats[0]));d.writeheader();d.writerows(stats)

summary={
 'population_original_registrations':1976,'cleaned_registrations':1900,
 'surplus_duplicate_registrations':67,'exact_previous_exposure_identity_holds':5,
 'provisional_candidate_identities':1828,'selected_unique_farmers':630,
 'psp_only':315,'psp_plus_ishamba':315,
 'psp_only_counties':dict(dist(ra,'County')),
 'psp_plus_ishamba_counties':dict(dist(rb,'County')),
 'raw_source_geography_labels':len({(r['County'],r['Source ward (unapproved)']) for r in rf}),
 'provisional_geographic_groups':len({(r['County'],r['Sampling geographic group']) for r in rf}),
 'sampled_in_small_ward_pools':sum('POOL' in str(r['Sampling geographic group']) for r in ra+rb),
 'cross_arm_shared_phone':0,
 'gender_female_counts':[sum(r['Gender']=='Female' for r in rs) for rs in [ra,rb]],
 'youth_counts':[sum(r['Age group']=='Youth 18-35' for r in rs) for rs in [ra,rb]],
 'finger_millet_counts':[sum(r['Main crop']=='Finger Millet' for r in rs) for rs in [ra,rb]],
 'individual_verification_cases':39,
 'selected_original_high_priority':sum(r['Original priority']=='HIGH' for r in ra+rb),
 'approval_status':'HOLD - all approvals pending',
 'balance':stats,
}
(public/'study_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white'})
navy='#17324B'; teal='#0A7E83'; amber='#D49B35'
# Figure 1. Registration-to-allocation flow (fully aggregated)
fig,ax=plt.subplots(figsize=(11.5,3.8))
counts=[1976,1900,1833,1828,630];labs=['Original CGA\nregistrations','After 76 prior\nexposure removals','After deduplication\n(−67)','After 5 exact\nexposure holds','Assigned to\ntwo PSP arms']
bar=ax.bar(range(len(counts)),counts,color=[navy,'#315678','#4E7993',teal,amber],width=.67)
for i,x in enumerate(bar):ax.text(x.get_x()+x.get_width()/2,x.get_height()+45,str(counts[i]),ha='center',weight='bold',fontsize=11)
ax.set_xticks(range(len(counts)),labs);ax.set_ylim(0,2200);ax.set_ylabel('Number of registrations / distinct identities')
ax.set_title('Figure 1. Reconciliation of the PSP farmer sampling frame',loc='left',fontsize=13,weight='bold',color=navy,pad=20)
ax.text(.5,-.28,'Removal and identity reconciliation precede random allocation; five exposure matches remain on hold.',transform=ax.transAxes,ha='center',fontsize=9,color='#536477')
fig.tight_layout();fig.savefig(public/'figure_01_sampling_flow.png',dpi=250,bbox_inches='tight');plt.close(fig)
# Figure 2. Distinct concepts: balance vs representativeness
fig,ax=plt.subplots(figsize=(10.8,4.3))
shown=[s for s in stats if s['domain']!='County']
y=np.arange(len(shown));a1=np.array([s['tvd_between_arms'] for s in shown]);b1=np.array([s['tvd_selected_vs_frame'] for s in shown]);width=.36
ax.barh(y-width/2,100*a1,height=width,color=navy,label='PSP-only versus PSP + iShamba')
ax.barh(y+width/2,100*b1,height=width,color=teal,label='Combined selected versus frame')
ax.set_yticks(y,[s['domain'] for s in shown]);ax.invert_yaxis();ax.set_xlabel('Total variation distance (percentage points)');ax.legend(loc='upper center',bbox_to_anchor=(.5,-.13),ncol=2,frameon=False,fontsize=9)
ax.set_title('Figure 3. Randomization balance and sampling-frame representation',loc='left',fontsize=13,weight='bold',color=navy,pad=12)
fig.tight_layout();fig.savefig(public/'figure_02_balance_two_axes.png',dpi=250,bbox_inches='tight');plt.close(fig)
# Figure 3. Mirrored county allocation
fig,ax=plt.subplots(figsize=(8.5,4))
co=['Meru','Tharaka Nithi']; aa=[sum(r['County']==c for r in ra) for c in co];bb=[sum(r['County']==c for r in rb) for c in co]
y=np.arange(2);ax.barh(y,[-n for n in aa],color=navy,label='PSP only');ax.barh(y,bb,color=teal,label='PSP + iShamba')
ax.axvline(0,color='#758294',lw=.8);ax.set_yticks(y,co);ax.invert_yaxis();ax.set_xlim(-190,190)
from matplotlib.ticker import FuncFormatter
ax.xaxis.set_major_formatter(FuncFormatter(lambda x,pos:str(abs(int(x)))))
for i in y:
 ax.text(-aa[i]-8,i,str(aa[i]),ha='right',va='center',weight='bold');ax.text(bb[i]+8,i,str(bb[i]),ha='left',va='center',weight='bold')
ax.set_xlabel('Farmers per arm');ax.legend(loc='lower center',ncol=2,frameon=False,bbox_to_anchor=(.5,-.35))
ax.set_title('Figure 2. Exact county-level allocation symmetry',loc='left',fontsize=13,weight='bold',color=navy)
fig.tight_layout();fig.savefig(public/'figure_03_county_mirror.png',dpi=250,bbox_inches='tight');plt.close(fig)
print('Aggregate figures, domain balance and de-identified summary exported:', public)
# Figure 4. Weighted auxiliary-total discrepancy (excluding identifiers)
independent=json.loads((p/'PSP_Independent_Algorithm_Tests.json').read_text())
checks=independent['ht_domain_summary']
names=[c['domain'] for c in checks]
values=[float(c['max_abs_residual_pp']) for c in checks]
fig,ax=plt.subplots(figsize=(9.4,3.8))
y=np.arange(len(names));rect=ax.barh(y,values,color=teal,height=.65)
ax.set_yticks(y,names);ax.invert_yaxis();ax.set_xlabel('Maximum absolute residual (% of frame population)')
for bar,x in zip(rect,values): ax.text(x+.014,bar.get_y()+bar.get_height()/2,f'{x:.3f}',va='center',fontsize=9)
ax.set_xlim(0,max(values)*1.28)
ax.set_title('Figure 4. Design-weighted balance of sampled auxiliary totals',loc='left',fontsize=13,weight='bold',color=navy,pad=14)
fig.tight_layout();fig.savefig(public/'figure_04_weighted_residuals.png',dpi=250,bbox_inches='tight');plt.close(fig)
# Figure 5. Verification categories overlap; do not sum them.
selected=ra+rb
flaglabels=['Original high-priority','Conflicting identity metadata','Contact number check','Shared-phone source flag']
counts=[sum(r['Original priority']=='HIGH' for r in selected),sum(bool(r['Duplicate metadata conflicts']) for r in selected),sum(r['Phone quality'] not in ('VALID',None,'') for r in selected),sum((r['Shared phone group size'] or 0)>1 for r in selected)]
fig,ax=plt.subplots(figsize=(9.4,3.65))
y=np.arange(len(flaglabels));rect=ax.barh(y,counts,color=[amber,amber,navy,teal],height=.64)
ax.set_yticks(y,flaglabels);ax.invert_yaxis();ax.set_xlabel('Selected farmer records with a flag (overlapping categories)')
for bar,x in zip(rect,counts):ax.text(x+.7,bar.get_y()+bar.get_height()/2,str(x),va='center',fontsize=10,weight='bold')
ax.set_xlim(0,max(counts)*1.22)
ax.set_title('Figure 5. Outstanding verification flags among 630 selected farmers',loc='left',fontsize=13,weight='bold',color=navy,pad=14)
fig.tight_layout();fig.savefig(public/'figure_05_verification_flags.png',dpi=250,bbox_inches='tight');plt.close(fig)
