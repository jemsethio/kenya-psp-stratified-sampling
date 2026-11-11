"""Kenya PSP 2026 OND -- Step 1 revised frame audit: shared phones and questionable formats remain eligible for review.
Requires artifact_tool. Original data is never changed. No random draw is performed.
Re-run using the original workbook: METHA PSP farmers_with 76 removed.xlsx.
"""
from __future__ import annotations
from collections import Counter, defaultdict, deque
from datetime import date
import difflib
import os
import re
import unicodedata
from artifact_tool import Blob, SpreadsheetFile, Workbook

ROOT=os.environ.get('PSP_WORKDIR','/mnt/data')
SOURCE=os.path.join(ROOT,'METHA PSP farmers_with 76 removed.xlsx')
OUTPUT=os.path.join(ROOT,'Kenya_PSP_Step1_Finger_Millet_Confirmed.xlsx')


def norm(v):
    v='' if v is None else str(v)
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC',v).strip()).casefold()

def title(v):
    return norm(v).title() if norm(v) else ''

def keyrow(row):
    return tuple(norm(c) for c in row)

def wardnorm(v):
    txt=norm(v)
    txt=re.sub(r'[.,/]+',' ',txt)
    return re.sub(r'\s+',' ',txt).strip().title()

def standard_phone(v):
    t=str(v or '').strip()
    if not t: return ('','MISSING')
    # The submitted file stores most phones as 9-digit local numbers without leading 0.
    # Reject rather than infer ambiguous 8-, 10- or 11-digit entries.
    if 'e+' in t.lower():
        return ('','INVALID:SCIENTIFIC_NOTATION')
    digits=re.sub(r'\D','',t)
    if not digits: return ('','MISSING')  # e.g. textual placeholders for no contact
    if digits.startswith('00254') and len(digits)==14:
        digits=digits[2:]
    if len(digits)==12 and digits.startswith('254') and digits[3] in '17':
        return (digits, 'VALID')
    if len(digits)==10 and digits[:2] in ('07','01'):
        return ('254'+digits[1:], 'VALID')
    if len(digits)==9 and digits[0] in ('7','1'):
        return ('254'+digits, 'VALID')
    return ('','INVALID_LENGTH_OR_PREFIX')

def shared_key(v):
    p,q=standard_phone(v)
    return p if q=='VALID' else ('INVALID:'+re.sub(r'\D','',str(v or '')) if q!='MISSING' else '')

print('Reading input workbook...',flush=True)
src=SpreadsheetFile.import_xlsx(Blob.load(SOURCE))
clean=src.worksheets.get_item_at(0).get_range('A1:P1901').values
original=src.worksheets.get_item_at(1).get_range('A1:P1977').values
if len(clean)!=1901 or len(original)!=1977:
    raise ValueError('Unexpected frame size; inspect source before running')
clean_records=[{'clean_row':i,'data':r} for i,r in enumerate(clean[1:],2)]
orig_records=[{'original_row':i,'data':r} for i,r in enumerate(original[1:],2)]
clean_counter=Counter(keyrow(obj['data']) for obj in clean_records)
orig_counter=Counter(keyrow(obj['data']) for obj in orig_records)
if clean_counter-orig_counter:
    raise ValueError('Cleaned input contains records absent from original sheet')
removed_counter=orig_counter-clean_counter
if sum(removed_counter.values())!=76:
    raise ValueError('The source difference is not exactly 76 rows')
removed=[]
for obj in orig_records:
    k=keyrow(obj['data'])
    if removed_counter[k]>0:
        removed.append(obj)
        removed_counter[k]-=1
orig_indices=defaultdict(deque)
for obj in orig_records:
    orig_indices[keyrow(obj['data'])].append(obj['original_row'])
for i,obj in enumerate(clean_records,1):
    obj['study_id']=f'PSP-CGA-{i:05d}'
    obj['original_row']=orig_indices[keyrow(obj['data'])].popleft()

phones=defaultdict(list)
pairs=defaultdict(list)
removed_phones=defaultdict(list)
removed_pairs=defaultdict(list)
fscphones=defaultdict(set)
fsc_contacts=set()
ward_groups=defaultdict(list)
fsc_groups=defaultdict(list)
crop_groups=defaultdict(list)
for obj in clean_records:
    r=obj['data']; sid=obj['study_id']; ph=shared_key(r[4]); name=norm(r[3]); fsc=norm(r[1])
    obj['phone']=ph
    obj['phone_quality']=standard_phone(r[4])[1]
    obj['name_norm']=name
    obj['ward_norm']=wardnorm(r[9])
    obj['fsc_norm']=title(r[1])
    obj['county_norm']=title(r[7])
    obj['age_norm']='Youth 18-35' if norm(r[6])=='youth 18-35 years' else ('Adult 36+' if norm(r[6])=='adult 36 and above years' else 'Unknown')
    obj['gender_norm']=title(r[5])
    obj['crop_norm']=title(r[12])
    if ph:
        phones[ph].append(obj)
        if name:pairs[(name,ph)].append(obj)
    fscphones[fsc].add(shared_key(r[2]))
    fsc_contacts.add(shared_key(r[2]))
    ward_groups[(obj['county_norm'],obj['ward_norm'])].append(obj)
    fsc_groups[fsc].append(obj)
    crop_groups[obj['crop_norm']].append(obj)
for obj in removed:
    r=obj['data']; ph=shared_key(r[4]);name=norm(r[3]);
    if ph:
        removed_phones[ph].append(obj)
        if name:removed_pairs[(name,ph)].append(obj)

# Geographic review dictionary: do not silently merge close spellings.
ward_totals={k:len(v) for k,v in ward_groups.items()}
ward_dictionary=[]
ward_suspect=set()
for (county,ward),rset in sorted(ward_groups.items()):
    n=len(rset)
    candidates=[]
    for (oc,ow),others in ward_groups.items():
        if oc!=county or ow==ward: continue
        score=difflib.SequenceMatcher(None,norm(ward),norm(ow)).ratio()
        if score>=0.84 and len(others)>=n:
            candidates.append((score,len(others),ow))
    candidates.sort(reverse=True)
    suggested=candidates[0][2] if candidates else ''
    ratio=candidates[0][0] if candidates else 0
    alternate_count=sum(n2 for (c2,w2),n2 in ward_totals.items() if w2==ward and c2!=county)
    flag=[]
    if len(ward)<5 or ward.lower() in {'east','ka','ntima','imenti north','muukuru','buur'}:
        flag.append('Potential place-name placeholder / misplaced field')
    if suggested and (ratio>=.90 or (n<=2 and ratio>=.84)):
        flag.append('Possible variant of '+suggested+'; do not merge without approval')
    if n<=3 and alternate_count>=20:
        flag.append('Unexpected county relative to other records')
    if flag:ward_suspect.add((county,ward))
    raw_counter=Counter(str(z['data'][9]) for z in rset)
    ward_dictionary.append([county,ward,n,'; '.join(f'{x} ({c})' for x,c in raw_counter.most_common(4)),suggested,round(ratio,2) if suggested else '', ' | '.join(flag) or 'Basic casing/spacing only', '', 'Pending CGA confirmation'])

statuses=Counter(); flag_counts=Counter(); queue=[]; frame=[]
source_name_pairs=Counter()
for obj in clean_records:
    r=obj['data']; ph=obj['phone']; nm=obj['name_norm'];idkey=(nm,ph)
    match_xphone=len(removed_phones.get(ph,[])) if ph else 0
    match_xperson=len(removed_pairs.get(idkey,[])) if ph else 0
    dup_pair=len(pairs.get(idkey,[])) if ph else 0
    shared=len(phones.get(ph,[])) if ph else 0
    reasons=[]; critical=[]; other=[]
    if match_xperson:
        critical.append('Same farmer name + phone as removed record')
        flag_counts['Removed name+phone match']+=1
    elif match_xphone:
        critical.append('Phone overlaps removed 76 (different/uncertain farmer)')
        flag_counts['Removed phone-only match']+=1
    if dup_pair>1:
        critical.append('Repeated farmer name + phone in retained list')
        flag_counts['Repeated name+phone']+=1
    if shared>1 and len({p['name_norm'] for p in phones[ph]})>1:
        other.append('SHARED NUMBER — RETAIN farmer; verify SMS access if selected')
        flag_counts['Shared phone / different names']+=1
    if obj['phone_quality']=='MISSING':
        other.append('MISSING CONTACT — RETAIN farmer; obtain number before advisory delivery')
        flag_counts['Missing contact']+=1
    if obj['phone_quality'] not in ('MISSING','VALID'):
        other.append('PHONE FORMAT CHECK — RETAIN farmer; verify before advisory delivery')
        flag_counts['Invalid contact']+=1
    if ph and ph in fsc_contacts:
        other.append('Farmer contact also appears as an FSC contact')
        flag_counts['Farmer phone also FSC contact']+=1
    if obj['age_norm']=='Unknown':
        other.append('Missing/unrecognized age category')
        flag_counts['Missing age']+=1
    if (obj['county_norm'],obj['ward_norm']) in ward_suspect:
        other.append('Ward label or county needs verification')
        flag_counts['Ward classification review']+=1
    if len(fscphones[norm(r[1])])>1:
        # FSC contact conflicts are dictionary-level checks, not 1,242 individual eligibility flags.
        flag_counts['FSC multiple contacts, affected rows (reference only)']+=1
    reasons=critical+other
    if critical:status='HOLD - exposure/identity verification';priority='HIGH'
    elif other:status='REVIEW - retain; verify metadata';priority='MEDIUM'
    else:status='PROVISIONAL - no detected flags';priority='LOW'
    statuses[status]+=1
    obj['status']=status;obj['priority']=priority;obj['critical']=critical;obj['other']=other;obj['flags']=reasons
    shared_flag=shared>1 if ph else False
    keep_phone_policy=('Shared contact across retained records — KEEP farmer; verify individual identity and SMS access' if shared_flag else 'No shared-number issue detected')
    if obj['phone_quality']=='MISSING': keep_phone_policy+=' | Missing phone: obtain before SMS'
    elif obj['phone_quality']!='VALID': keep_phone_policy+=' | Format needs verification before SMS'
    obj['contact_policy']=keep_phone_policy
    master=[obj['study_id'], obj['clean_row'], obj['original_row'],status,priority,' | '.join(reasons),
            'Pending review','Not yet confirmed','',
            r[3],r[4],standard_phone(r[4])[0],obj['gender_norm'],obj['age_norm'],obj['county_norm'],r[8],r[9],obj['ward_norm'],
            r[1],obj['fsc_norm'],r[2],obj['crop_norm'],r[13],r[10],r[11],r[0],r[14],r[15],
            dup_pair,shared,match_xphone,match_xperson,obj['phone_quality'],
            'Review' if (obj['county_norm'],obj['ward_norm']) in ward_suspect else 'No row-level alert',
            'Finger Millet confirmed in cleaned Sheet1' if norm(r[12])=='finger millet' else 'As recorded',
            len(fscphones[norm(r[1])]),r[5],r[6],r[7],r[12],r[13],
            'RETAIN in provisional frame — partner eligibility check pending', obj['contact_policy'],
            'Yes' if obj['phone_quality']!='VALID' else 'No']
    obj['master_row']=master
    frame.append(master)
    if reasons:
        queue.append([obj['study_id'],status,priority,' | '.join(critical),' | '.join(other),r[3],r[4],
                      obj['county_norm'],obj['ward_norm'],obj['fsc_norm'],obj['age_norm'],obj['crop_norm'],obj['clean_row'],
                      'See Provisional_Frame; enter decisions only in master sheet'])

queue.sort(key=lambda r:({'HIGH':0,'MEDIUM':1,'LOW':2}[r[2]],r[7],r[8],r[0]))

excluded=[]
for k,obj in enumerate(removed,1):
    r=obj['data'];ph=shared_key(r[4]);ids_phone=[o['study_id'] for o in phones.get(ph,[])] if ph else []
    ids_person=[o['study_id'] for o in pairs.get((norm(r[3]),ph),[])] if ph else []
    excluded.append([f'REM-{k:03d}',obj['original_row'],r[3],r[4],standard_phone(r[4])[0],r[7],r[9],r[1],r[5],r[6],r[12],
                     len(ids_phone),'; '.join(ids_phone),len(ids_person),'; '.join(ids_person),
                     'Presumed previously exposed according to workbook/meeting context; confirmation required'])

fsc_sheet=[]
for name,objs in sorted(fsc_groups.items(),key=lambda kv:(-len(kv[1]),kv[0])):
    phones_seen=sorted(fscphones[name])
    fsc_sheet.append([title(name),len(objs),len(phones_seen),'; '.join(str(o['data'][1]) for o in objs[:1]),
                      '; '.join(str(o['data'][2]) for o in objs[:3]),
                      'Review lead contact(s) with CGA' if len(phones_seen)>1 else 'Verify FSC identity/coverage',
                      '', 'Pending CGA confirmation'])

crops=[]
for crop,objs in sorted(crop_groups.items(),key=lambda kv:(-len(kv[1]),kv[0])):
    counties=Counter(o['county_norm'] for o in objs)
    crops.append([crop,len(objs),counties['Meru'],counties['Tharaka Nithi'],
                  'Confirmed Finger Millet in cleaned Sheet1' if norm(crop)=='finger millet' else 'Retained exactly as reported',
                  '', 'Resolved per cleaned Sheet1' if norm(crop)=='finger millet' else 'Provisional'])

print('Counts',dict(statuses),'Queue',len(queue),'Shared distinct number groups',sum(len(group)>1 for group in phones.values()),'Shared different-name rows',sum(len({o['name_norm'] for o in phones[x['phone']]})>1 for x in clean_records if x['phone']),'Ward dictionary',len(ward_dictionary),'FSC',len(fsc_sheet), 'crop',len(crops), flush=True)

wb=Workbook.create()
NAVY='#12324A'; BLUE='#1E5D85'; TEAL='#107D75'; LIGHT='#E9F3F8'; GRAY='#F1F5F9'; WHITE='#FFFFFF'; RED='#FFF0EE'; AMBER='#FFF3DA'; GREEN='#E8F6EF'

def write_grid(sheet_name,headers,rows,widths=None,table_name=None):
    sh=wb.worksheets.add(sheet_name)
    matrix=[headers]+rows
    # Chunks keep underlying dispatch size controlled for 1900-row frame.
    for start in range(0,len(matrix),250):
        chunk=matrix[start:start+250]
        sh.get_range_by_indexes(start,0,len(chunk),len(headers)).values=chunk
    last=len(matrix)
    hr=sh.get_range_by_indexes(0,0,1,len(headers))
    hr.format={'fill':NAVY,'font':{'bold':True,'color':WHITE},'wrap_text':True,'row_height':38,'vertical_alignment':'center'}
    if last>1:
        sh.get_range_by_indexes(1,0,last-1,min(len(headers),6)).format.row_height=23
    if widths:
        for col_idx,width in widths.items():
            sh.get_range_by_indexes(0,col_idx,last,1).format.column_width=width
    sh.freeze_panes.freeze_rows(1)
    if table_name:
        sh.tables.add(sh.get_range_by_indexes(0,0,last,len(headers)),True,table_name)
    return sh

headers=['Study_ID','Clean_Sheet_Row','Original_Sheet_Row','Screening_Status','Priority','Review_Flags',
         'CGA_Decision','iShamba_Exposure_Verified','Review_Notes',
         'Farmer_Name_Raw','Farmer_Contact_Raw','Farmer_Phone_E164','Gender_Std','Age_Std','County_Std',
         'SubCounty_Raw','Ward_Raw','Ward_Normalized_Unapproved','FSC_Name_Raw','FSC_Name_Normalized',
         'FSC_Contact_Raw','Main_Crop_Normalized','Secondary_Crop_Raw','Village_Raw','Landmark_Raw',
         'Timestamp_Raw','Additional_Crop3_Unlabeled','Additional_Crop4_Unlabeled',
         'Repeated_NamePhone_Group_Size','Shared_Phone_Group_Size','Removed_List_Phone_Matches',
         'Removed_List_NamePhone_Matches','Phone_Quality','Ward_Review_Flag','Crop_Review_Flag',
         'FSC_Contact_Count','Gender_Raw','Age_Raw','County_Raw','Main_Crop_Raw','Second_Crop_Raw',
         'Frame_Inclusion','Shared_And_Contact_Policy','Phone_Correction_Needed']
assert all(len(row)==len(headers) for row in frame)

summary=wb.worksheets.add('00_Read_Me')
summary.merge_cells('A1:H2')
summary.get_range('A1').values=[['KENYA 2026 OND | PSP SAMPLING FRAME — STEP 1']]
summary.get_range('A1:H2').format={'fill':NAVY,'font':{'bold':True,'color':WHITE,'size':15},'vertical_alignment':'center','row_height':25}
summary.merge_cells('A3:H3')
summary.get_range('A3').values=[['Conservative audit • not a final eligible list • no random sample has been drawn']]
summary.get_range('A3:H3').format={'fill':LIGHT,'font':{'color':BLUE,'italic':True},'row_height':25}
summary.get_range('A5:B15').values=[
    ['FRAME / QUALITY METRIC','RECORDS'],
    ['Original sheet farmer rows',1976],
    ['Removed original records (verified difference)',76],
    ['Retained records in cleaned sheet',1900],
    ['High-priority exposure/identity reviews (not deleted)',None],
    ['Medium-priority metadata reviews',None],
    ['No detected row-level flags (still provisional)',None],
    ['Review queue (unique flagged rows)',None],
    ['Retained rows with removed-list phone overlap',None],
    ['Retained rows with removed-list name+phone match',None],
    ['Missing phone numbers',None],
]
summary.get_range('A17:B23').values=[
    ['OTHER CRITICAL CHECKS','COUNT'],
    ['Retained with ambiguous phone formats (verify before SMS)',None],
    ['Retained rows with repeated name+phone',None],
    ['Retained farmer rows sharing phone across names',None],
    ['Missing age category',None],
    ['Ward labels requiring review (county-label pairs)',len(ward_suspect)],
    ['FSC names with multiple contacts',sum(len(fscphones[k])>1 for k in fscphones)],
]
summary.get_range('A25:H25').merge_cells('A25:H25') if False else None
# Additional distinct shared phone count is shown on the summary at row 24.
summary.get_range('A24:B24').values=[['Distinct phone numbers used by 2+ retained records', sum(len(group)>1 for group in phones.values())]]
summary.merge_cells('A25:H25')
summary.get_range('A25').values=[['WORKFLOW AND LIMITATIONS']]
summary.get_range('A25:H25').format={'fill':BLUE,'font':{'bold':True,'color':WHITE},'row_height':24}
workflow=[
    '1. All 1,900 retained farmers stay in the provisional frame. HIGH flags identify exposure/identity cases, not automatic removals.',
    '2. SHARED PHONES: keep all different farmers even with the same phone; mark shared access and review SMS delivery arrangements.',
    '3. AMBIGUOUS/MISSING PHONES: keep the record and mark it. Resolve contact formatting or obtain a reachable number before SMS delivery.',
    '4. Record eligibility decisions ONLY in the master CGA_Decision field; confirm iShamba exposure separately before the draw.',
    '5. Use Review_Queue for triage; review source identity duplicates and removed-list overlaps with CGA/iShamba.',
    '6. Confirm Ward_Map and FSC_Map manually; Finger Millet is confirmed in cleaned Sheet1 and must not be flagged as pending.',
    '7. Shared phone numbers alone are NOT grounds to hold or exclude a farmer; link farmer IDs separately to shared phones.',
    '8. A malformed phone number alone is NOT grounds to exclude a farmer from the frame; intervention enrollment requires valid contact.',
    '9. The 76 removed rows are verified as workbook differences; review their number overlaps to avoid prior-exposure contamination.',
    '10. Do not randomize or transfer contacts until outstanding identity/exposure decisions and NDA/consent rules are approved.',
]
for i,msg in enumerate(workflow,27):
    summary.merge_cells(f'A{i}:H{i}')
    summary.get_range(f'A{i}').values=[[msg]]
    summary.get_range(f'A{i}:H{i}').format={'wrap_text':True,'row_height':34 if i in (27,28,32,33) else 29}
summary.get_range('A5:B5').format={'fill':BLUE,'font':{'bold':True,'color':WHITE}}
summary.get_range('A17:B17').format={'fill':BLUE,'font':{'bold':True,'color':WHITE}}
summary.get_range('A5:A23').format.column_width=53
summary.get_range('B5:B23').format.column_width=16
summary.get_range('C1:H36').format.column_width=15
summary.freeze_panes.freeze_rows(3)

print('Writing master and review tabs...',flush=True)
main=write_grid('Provisional_Frame',headers,frame,{0:22,1:18,2:20,3:36,4:12,5:68,6:24,7:25,8:25,
      9:25,10:22,11:23,12:16,13:16,14:20,15:23,16:24,17:27,18:24,19:24,20:21,21:24,22:25,
      28:17,29:17,30:20,31:20,32:25},'FrameAuditTable')
# Partner-editable fields are clearly marked and controlled.
main.get_range('G1:I1').format={'fill':TEAL,'font':{'bold':True,'color':WHITE},'row_height':38,'wrap_text':True}
main.get_range('G2:I1901').format.fill=GREEN
main.get_range('G2:G1901').data_validation={'rule':{'type':'list','values':['Pending review','Confirm eligible','Exclude - prior exposure','Exclude - duplicate','Exclude - other','Needs follow-up']}}
main.get_range('H2:H1901').data_validation={'rule':{'type':'list','values':['Not yet confirmed','No prior relevant exposure','Previously received iShamba advice','Uncertain - investigate']}}

qheads=['Study_ID','Screening_Status','Priority','Identity_or_Contact_Issue','Other_Metadata_Issue','Farmer_Name','Farmer_Contact',
        'County','Ward_Unapproved','FSC','Age','Primary_Crop','Clean_Sheet_Row','Reviewer_Instruction']
q=write_grid('Review_Queue',qheads,queue,{0:22,1:35,2:12,3:65,4:70,5:24,6:22,7:19,8:25,9:27,10:17,11:23,12:18,13:58},'ReviewQueueTable')

rheaders=['Removed_ID','Original_Sheet_Row','Farmer_Name_Raw','Farmer_Phone_Raw','Normalized_E164','County','Ward','FSC',
          'Gender','Age','Main_Crop','Retained_Phone_Match_Count','Retained_Phone_Match_Study_IDs',
          'Retained_NamePhone_Match_Count','Retained_NamePhone_Match_Study_IDs','Exposure_Note']
ex=write_grid('Removed_76',rheaders,excluded,{0:16,1:20,2:25,3:23,4:23,5:17,6:24,7:24,11:22,12:46,13:25,14:47,15:70},'RemovedListTable')

wheaders=['County','Ward_Normalized_Not_Approved','Records','Raw_Labels_Observed','Similar_Ward_Suggestion_Only',
          'Similarity_Score','Review_Reason','CGA_Approved_Canonical_Ward','Approval_Status']
ws=write_grid('Ward_Map',wheaders,ward_dictionary,{0:20,1:30,2:12,3:65,4:35,5:18,6:72,7:40,8:26},'WardCrosswalkTable')
ws.get_range_by_indexes(1,7,len(ward_dictionary),2).format.fill=GREEN

fheaders=['FSC_Normalized_Not_Approved','Farmer_Records','Distinct_Submitted_Contacts','Source_Label_Example',
          'Submitted_Contact_Examples','CGA_Action','CGA_Approved_FSC_ID','Approval_Status']
fs=write_grid('FSC_Map',fheaders,fsc_sheet,{0:38,1:20,2:28,3:38,4:55,5:45,6:28,7:28},'FSCCrosswalkTable')
fs.get_range_by_indexes(1,6,len(fsc_sheet),2).format.fill=GREEN

cheaders=['Main_Crop_As_Reported','Records','Meru_Records','Tharaka_Nithi_Records','Classification_Note','CGA_Approved_Crop','Approval_Status']
cs=write_grid('Crop_Map',cheaders,crops,{0:28,1:13,2:22,3:28,4:55,5:28,6:30},'CropCrosswalkTable')
cs.get_range_by_indexes(1,5,len(crops),2).format.fill=GREEN

rules=[
['SOURCE / VERSION','Original workbook','METHA PSP farmers_with 76 removed.xlsx','Sheet1 = cleaned, Copy of Sheet1 = original'],
['SOURCE / VERSION','Scope','CGA PSP-reached farmers, Meru and Tharaka Nithi','Not Nyandarua digital-only or comparison groups'],
['SOURCE / VERSION','Date',date(2026,11,10),'Initial audit based only on uploaded records'],
['ELIGIBILITY','Removed 76','Exactly 76 original rows absent from cleaned frame','Do not re-add unless CGA/iShamba explicitly reverses prior-exposure decision'],
['ELIGIBILITY','Removed-list overlap','Match by normalized phone; stronger evidence when name + phone match','All linked retained records held for independent validation'],
['ELIGIBILITY','Shared phones','A single number may legitimately be used by several distinct farmers','KEEP all distinct farmers; label SHARED and verify reachable advisory contact on enrollment; do not auto-exclude'],
['ELIGIBILITY','Name+phone duplicates','Identical normalized name plus identical normalized phone','Review every matching record; do not randomly select duplicates'],
['ELIGIBILITY','Phone normalization','Kenyan 9-digit 7/1 prefix, 10-digit 07/01, or 12-digit 2547/2541','Store valid form as 254xxxxxxxxx, never guess incomplete digits'],
['ELIGIBILITY','Phone format/missing','Missing, malformed, or ambiguous contact strings','KEEP records in frame with verification flag; correct/obtain deliverable number before digital enrollment'],
['GEOGRAPHY','County','Case- and spacing-normalized only','2 counties expected'],
['GEOGRAPHY','Ward','Case/whitespace/punctuation normalized for provisional diagnostics','Similar or cross-county variants require CGA approval before quotas'],
['GEOGRAPHY','Sub-county','Retained as originally submitted','Many inconsistent labels; do not infer ward from sub-county automatically'],
['STRATA','Gender','Female and Male reported (no missing in source)','Do not impose prior withdrawn quotas'],
['STRATA','Age','Youth 18–35, Adult 36+, Unknown','Age unknown is retained; obtain correction where feasible'],
['STRATA','Crop','Main crop taken only from explicitly titled Crop 1 column','Finger Millet is already resolved in cleaned Sheet1 (125 records); retain as Finger Millet'],
['STRATA','FSC','Name case/whitespace normalized; contact names not presumed unique official FSC IDs','23 names have multiple associated contact numbers'],
['DECISION','Exposure/identity HOLD','Removed-list phone/name overlap or repeated identical name+phone in retained file','Retain records provisionally; requires identity/prior-exposure review before sampling'],
['DECISION','Metadata/contact REVIEW','Shared different-farmer phone, questionable/missing phone format, or age/ward data','RETAIN all farmers; correct fields and ensure delivery capability, but do not auto-exclude'],
['DECISION','PROVISIONAL','No recorded row-level flag','Still subject to exposure, consent, and frame-wide CGA approval'],
['PARTNER ACTION','CGA_Decision','Only edit master sheet; use dropdown; fill review notes','Shared phone/phone format alone is not sufficient basis for exclusion'],
['PARTNER ACTION','iShamba exposure','Confirm delivery of relevant OND/subseasonal advisories, not merely platform registration','Resolve all 76 exclusions and overlapping numbers'],
['DATA GOVERNANCE','Restricted contact data','Contains personally identifying farmer data','Distribute only under appropriate NDA/data agreements'],
['NEXT STEP','Not authorized for sampling yet','Finalize approved canonical wards/FSCs and enrollment eligibility; Finger Millet confirmed','Then execute Step 2 allocation and Step 3 stratified random draw'],
]
rule_headers=['Section','Rule','Operational_Definition','Required_Action_or_Caution']
rs=write_grid('QA_Protocol',rule_headers,rules,{0:25,1:30,2:85,3:100},'QualityProtocolTable')

# Summary formulas respond to decisions and source-quality changes in the workbook.
summary.get_range('B9').formulas=[["=COUNTIF(Provisional_Frame!D2:D1901,\"HOLD - exposure/identity verification\")"]]
summary.get_range('B10').formulas=[["=COUNTIF(Provisional_Frame!D2:D1901,\"REVIEW - retain; verify metadata\")"]]
summary.get_range('B11').formulas=[["=COUNTIF(Provisional_Frame!D2:D1901,\"PROVISIONAL - no detected flags\")"]]
summary.get_range('B12').formulas=[["=COUNTA(Review_Queue!A2:A1901)"]]
summary.get_range('B13').formulas=[["=COUNTIF(Provisional_Frame!AE2:AE1901,\">0\")"]]
summary.get_range('B14').formulas=[["=COUNTIF(Provisional_Frame!AF2:AF1901,\">0\")"]]
summary.get_range('B15').formulas=[["=COUNTIF(Provisional_Frame!AG2:AG1901,\"MISSING\")"]]
summary.get_range('B18').formulas=[["=COUNTIF(Provisional_Frame!AG2:AG1901,\"INVALID_LENGTH_OR_PREFIX\")+COUNTIF(Provisional_Frame!AG2:AG1901,\"INVALID:SCIENTIFIC_NOTATION\")"]]
summary.get_range('B19').formulas=[["=COUNTIF(Provisional_Frame!AC2:AC1901,\">1\")"]]
# Shared phones across farmer names, from computed source audit, using QA flags on full frame.
summary.get_range('B20').values=[[sum(len({o['name_norm'] for o in phones[x['phone']]})>1 for x in clean_records if x['phone'])]]
summary.get_range('B21').formulas=[["=COUNTIF(Provisional_Frame!N2:N1901,\"Unknown\")"]]

# Color tier cells with precise red/amber/green, while keeping large sheet efficient.
main.get_range('D2:D1901').conditional_formats.add_custom('=LEFT($D2,4)="HOLD"',{'fill':RED})
main.get_range('D2:D1901').conditional_formats.add_custom('=LEFT($D2,6)="REVIEW"',{'fill':AMBER})
main.get_range('D2:D1901').conditional_formats.add_custom('=LEFT($D2,11)="PROVISIONAL"',{'fill':GREEN})
summary.get_range('B6:B24').format.number_format='#,##0'

print('Verifying summary...',flush=True)
print(wb.inspect({'kind':'table','range':'00_Read_Me!A5:B23','include':'values,formulas','table_max_rows':20,'table_max_cols':2}).ndjson[:4200],flush=True)
print('Exporting...',flush=True)
SpreadsheetFile.export_xlsx(wb).save(OUTPUT)
print('SAVED',OUTPUT,os.path.getsize(OUTPUT),'bytes',flush=True)
print('COUNTS',{'orig':len(orig_records),'removed':len(removed),'clean':len(clean_records),'statuses':dict(statuses),'review_queue':len(queue),'removed_phone_rows':sum(bool(removed_phones.get(x['phone'])) for x in clean_records if x['phone']),
' removed_namephone_rows':sum(bool(removed_pairs.get((x['name_norm'],x['phone']))) for x in clean_records if x['phone']),
'duplicate_namephone_rows':sum(len(pairs.get((x['name_norm'],x['phone']),[]))>1 for x in clean_records if x['phone']),
'phone_missing':sum(x['phone_quality']=='MISSING' for x in clean_records),
'phone_invalid':sum(x['phone_quality'] not in ('MISSING','VALID') for x in clean_records),
'age_missing':sum(x['age_norm']=='Unknown' for x in clean_records), 'count_ward_dictionary':len(ward_dictionary), 'fsc_multiple_contacts':sum(len(v)>1 for v in fscphones.values())},flush=True)
