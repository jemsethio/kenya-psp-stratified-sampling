"""Reconstruct the 1,828-person canonical candidate register without an obsolete 267-farmer draw.

The historical 267-farmer interim sample was superseded by the joint 315+315
assignment; computing it takes substantial time and must not be mistaken for
an active sampling stage.  All identity rules match the archived 03 legacy script.
"""
from __future__ import annotations
import os, re, math, unicodedata
from pathlib import Path
from collections import defaultdict,Counter
from artifact_tool import Blob,SpreadsheetFile,Workbook
BASE=Path(os.environ.get('PSP_WORKDIR','/mnt/data'))
def norm(v):
    return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',str(v or '')).strip()).casefold()
def phone_key(r):
    if norm(r['Phone_Quality'])=='valid' and r['Farmer_Phone_E164']:
        return str(r['Farmer_Phone_E164']).strip()
    return re.sub(r'\D','',str(r['Farmer_Contact_Raw'] or ''))

old=SpreadsheetFile.import_xlsx(Blob.load(str(BASE/'Kenya_PSP_Step1_Finger_Millet_Confirmed.xlsx')))
v=old.worksheets.get_item('Provisional_Frame').get_range('A1:AR1901').values
entries=[dict(zip(v[0],row)) for row in v[1:]]
assert len(entries)==1900
w=SpreadsheetFile.import_xlsx(Blob.load(str(BASE/'Kenya_PSP_Step2_Ward_Allocation_Finger_Millet_Confirmed.xlsx')))
wardrows=w.worksheets.get_item('02 Ward Dictionary').get_range('A5:H52').values
mapping={(r[0],r[1]):r[4] for r in wardrows if r[0] and r[1]}
assert len(mapping)==48
byidentity=defaultdict(list)
for i,r in enumerate(entries):
    n,p=norm(r['Farmer_Name_Raw']),phone_key(r)
    byidentity[(n,p) if n and p else ('unmatchable',str(i))].append(i)
dups=[ids for ids in byidentity.values() if len(ids)>1]
assert len(dups)==65 and sum(len(ids)-1 for ids in dups)==67
keep={min(ids) for ids in byidentity.values()}
canonical=[entries[i] for i in sorted(keep)]
assert len(canonical)==1833
conf_fields=['County_Std','Ward_Normalized_Unapproved','FSC_Name_Normalized','Gender_Std','Age_Std','Main_Crop_Normalized','Village_Raw']
conflict={}
for ids in dups:
    first=min(ids)
    conflict[entries[first]['Study_ID']]=[field for field in conf_fields if len({norm(entries[i].get(field)) for i in ids})>1]
held=[r for r in canonical if int(r['Removed_List_NamePhone_Matches'] or 0)>0]
candidates=[r for r in canonical if int(r['Removed_List_NamePhone_Matches'] or 0)==0]
assert len(held)==5 and len(candidates)==1828
for r in canonical:
    k=(r['County_Std'],r['Ward_Normalized_Unapproved'])
    if k not in mapping:raise ValueError(f'Unmapped source ward {k}')
    r['Allocation_Group']=mapping[k]
counts=Counter((r['County_Std'],r['Allocation_Group']) for r in candidates)
assert len(counts)==24
# Historical interim-sampling probabilities appear as audit-only fields. Final
# 630-person selection and true pool probability are computed in Stage 4.
mainhead=['Study_ID','County','Ward (unapproved)','Provisional allocation group','FSC','Gender','Age / youth','Main crop','Farmer full name','Farmer phone (as supplied)','Contact check','Shared phone: source count','Removed-list phone overlap','Removed-list exact identity','Original QA flags','Original priority','Source row','Sampling status','Rank in geographic group','Inclusion probability','Duplicate metadata conflicts (review)','Contact permission','Reviewer decision']
records=[]
for r in candidates:
    rec=[r['Study_ID'],r['County_Std'],r['Ward_Normalized_Unapproved'],r['Allocation_Group'],r['FSC_Name_Normalized'],r['Gender_Std'],r['Age_Std'],r['Main_Crop_Normalized'],r['Farmer_Name_Raw'],str(r['Farmer_Contact_Raw'] or ''),r['Phone_Quality'],r['Shared_Phone_Group_Size'],r['Removed_List_Phone_Matches'],r['Removed_List_NamePhone_Matches'],r['Review_Flags'],r['Priority'],r['Clean_Sheet_Row'], 'Not selected in superseded 267 draw',None,None,'; '.join(conflict.get(r['Study_ID'],[])),'HOLD - NOT AUTHORIZED for SMS',None]
    records.append(rec)
assert len({r[0] for r in records})==1828
reverse={i:min(ids) for ids in byidentity.values() for i in ids if i!=min(ids)}
drophead=['Duplicate Study ID','Canonical Study ID','Canonical source row','Duplicate source row','County','Ward duplicate','FSC canonical','FSC duplicate','Age canonical','Age duplicate','Crop canonical','Crop duplicate','Full name duplicate','Phone duplicate','Conflicting fields','Resolution','CGA signoff']
dropped=[]
for ix,keeper in sorted(reverse.items()):
    r,k=entries[ix],entries[keeper]
    cf=[f for f in conf_fields if norm(k.get(f))!=norm(r.get(f))]
    dropped.append([r['Study_ID'],k['Study_ID'],k['Clean_Sheet_Row'],r['Clean_Sheet_Row'],r['County_Std'],r['Ward_Normalized_Unapproved'],k['FSC_Name_Normalized'],r['FSC_Name_Normalized'],k['Age_Std'],r['Age_Std'],k['Main_Crop_Normalized'],r['Main_Crop_Normalized'],r['Farmer_Name_Raw'],str(r['Farmer_Contact_Raw'] or ''),'; '.join(cf),'Duplicate registration — excluded from draw',None])
assert len(dropped)==67
holdhead=['Study_ID','County','Ward','Full name','Phone','Source row','Removed-list identity matches','Removed-list phone matches','Disposition','iShamba verdict']
holdrows=[[r['Study_ID'],r['County_Std'],r['Ward_Normalized_Unapproved'],r['Farmer_Name_Raw'],str(r['Farmer_Contact_Raw'] or ''),r['Clean_Sheet_Row'],r['Removed_List_NamePhone_Matches'],r['Removed_List_Phone_Matches'],'HELD: prior exposed identity likely; do not draw until verified',None] for r in held]
book=Workbook.create()
for name,head,body in [('01 Unique Candidate 1828',mainhead,records),('05 Surplus Duplicates 67',drophead,dropped),('06 Exposure Holds 5',holdhead,holdrows)]:
    sheet=book.worksheets.add(name)
    sheet.get_range_by_indexes(0,0,len(body)+1,len(head)).values=[head]+body
    sheet.get_range_by_indexes(0,0,1,len(head)).format={'fill':'#17324B','font':{'bold':True,'color':'#FFFFFF'},'row_height':28,'wrap_text':True}
    sheet.freeze_panes.freeze_rows(1)
    for j in range(len(head)):
        sheet.get_range_by_indexes(0,j,len(body)+1,1).format.column_width=23 if j<8 else 28
out=BASE/'Kenya_PSP_Step3_CORRECTED_Deduplicated_Draw.xlsx'
SpreadsheetFile.export_xlsx(book).save(str(out))
print(f'Frame-only stage: 1,900 rows -> 1,833 canonical identities -> five exposure holds -> 1,828 candidates; exported {out}.')
