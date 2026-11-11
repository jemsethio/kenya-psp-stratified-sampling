"""Create the *historical* provisional geographic mapping as a deterministic input.

This reproduces the previous 48-label/24-group allocation mapping.  It does NOT
certify those group labels as official Kenyan wards.  Edited/approved mappings
require a new release protocol and should not overwrite the frozen historical draw.
"""
import csv
import os
from pathlib import Path
from artifact_tool import Workbook, SpreadsheetFile

workdir=Path(os.environ.get('PSP_WORKDIR','/mnt/data'))
repository=Path(__file__).resolve().parents[3]
source=repository/'config'/'ward_groups_provisional.csv'
with source.open(newline='',encoding='utf-8') as stream:
    records=list(csv.DictReader(stream))
assert len(records)==48, 'Expected the documented 48 county-ward source labels'
assert len({(r['county'],r['raw_ward_normalized']) for r in records})==48
assert len({(r['county'],r['provisional_group']) for r in records})==24
wb=Workbook.create()
s=wb.worksheets.add('02 Ward Dictionary')
s.get_range('A1:H1').values=[['Historical county–ward crosswalk: provisional, NOT approved',None,None,None,None,None,None,None]]
s.get_range('A2:H2').values=[['Not an official ward directory; source labels retain their original classification.',None,None,None,None,None,None,None]]
s.get_range('A4:H4').values=[['County','Ward label normalized','Frame N','Allocation treatment','Assigned group','Possible variant','Geographic check','Approval status']]
body=[[r['county'],r['raw_ward_normalized'],None,'Frozen historical group',r['provisional_group'],None,'CGA REVIEW REQUIRED','UNVERIFIED'] for r in records]
s.get_range('A5:H52').values=body
s.get_range('A4:H4').format={'fill':'#17324B','font':{'bold':True,'color':'#FFFFFF'},'row_height':32,'wrap_text':True}
for j,width in enumerate([23,32,14,29,39,24,27,25]):
    s.get_range_by_indexes(0,j,52,1).format.column_width=width
s.freeze_panes.freeze_rows(4)
out=workdir/'Kenya_PSP_Step2_Ward_Allocation_Finger_Millet_Confirmed.xlsx'
SpreadsheetFile.export_xlsx(wb).save(str(out))
print(f'Historical provisional crosswalk saved to {out}; 48 labels mapped to 24 groups; not certified.')
