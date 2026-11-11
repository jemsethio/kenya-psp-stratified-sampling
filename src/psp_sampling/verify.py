"""Reference identity tests without disclosing farmer details."""
from artifact_tool import Blob,SpreadsheetFile


def assignments(path):
    w=SpreadsheetFile.import_xlsx(Blob.load(str(path)))
    result={}
    for sheet,arm in [('01 PSP ONLY 315','PSP only'),('02 PSP+iShamba 315','PSP + iShamba')]:
        for row in w.worksheets.get_item(sheet).get_range('A2:B316').values:
            if row[0]:
                if row[0] in result:raise ValueError('Duplicate Study ID in selected lists')
                if row[1]!=arm:raise ValueError('Arm mismatch')
                result[str(row[0])]=arm
    if len(result)!=630:raise ValueError(f'Expected 630 assignments; observed {len(result)}')
    return result


def compare_assignments(output,reference):
    a=assignments(output);b=assignments(reference)
    return {'identical':a==b,'count':len(a),'changed_arm':sum(a.get(k)!=b.get(k) for k in a),'only_in_output':len(set(a)-set(b)),'only_in_reference':len(set(b)-set(a))}
