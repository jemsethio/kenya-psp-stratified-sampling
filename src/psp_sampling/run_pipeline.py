"""Reproducible historical Kenya PSP sampling pipeline (provisional assignment).

Usage:
  python -m psp_sampling.run_pipeline --input /secure/METHA.xlsx --workdir /secure/psp_run

For a given original input and the frozen geographic crosswalk, the pipeline
reproduces the historical 315+315 farmer selection. No enrollment is authorized.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime,timezone

DATA_FILENAME='METHA PSP farmers_with 76 removed.xlsx'
STAGES=[
 '01_frame_qc.py',
 '02_build_geographic_crosswalk.py',
 '03_deduplicate_frame.py',
 '04_joint_randomization.py',
 '05_independent_tests.py',
 '06_summary_figures.py',
]


def sha(path):
    hash_=hashlib.sha256()
    with open(path,'rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            hash_.update(chunk)
    return hash_.hexdigest()


def main(argv=None):
    parser=argparse.ArgumentParser(description='Historical PSP: QC -> provisional geography -> deduplicate -> joint draw -> validation')
    parser.add_argument('--input',required=True,help='PRIVATE original Excel workbook (both sheets, 1,900 and 1,976 registrations)')
    parser.add_argument('--workdir',required=True,help='PRIVATE output directory (never inside the public Git repository)')
    parser.add_argument('--reference',help='Optional earlier joint randomized workbook to verify identical 630 assignments')
    parser.add_argument('--start-stage',type=int,choices=range(1,7),default=1,help='Resume after previously completed and audited stages (1-6)')
    args=parser.parse_args(argv)
    source=Path(args.input).expanduser().resolve()
    dest=Path(args.workdir).expanduser().resolve()
    repo=Path(__file__).resolve().parents[2]
    if not source.is_file() or source.suffix.lower()!='.xlsx': parser.error('input workbook not found / not XLSX')
    if dest==repo or repo in dest.parents: parser.error('private workdir must be OUTSIDE the Git repository to prevent PII leakage')
    dest.mkdir(parents=True,exist_ok=True)
    private_source=dest/DATA_FILENAME
    if source!=private_source:
        if private_source.exists() and sha(private_source)!=sha(source):
            parser.error('Existing private input differs: use a new workdir; frozen runs must be immutable')
        if not private_source.exists():shutil.copy2(source,private_source)
    logs=dest/'execution_logs';logs.mkdir(exist_ok=True)
    env=os.environ.copy();env['PSP_WORKDIR']=str(dest)
    completed=[]
    for j,stage in enumerate(STAGES,1):
        if j<args.start_stage:continue
        script=repo/'src'/'psp_sampling'/'stages'/stage
        print(f'[{j}/{len(STAGES)}] {stage}',flush=True)
        proc=subprocess.run([sys.executable,str(script)],cwd=str(repo),env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding='utf-8',errors='replace')
        (logs/f'{j:02d}_{stage}.log').write_text(proc.stdout)
        print(proc.stdout[-1100:],flush=True)
        if proc.returncode!=0:raise RuntimeError(f'Stage {j} failed. See {logs/f"{j:02d}_{stage}.log"}')
        completed.append(stage)
    reference_compare='NOT REQUESTED'
    if args.reference:
        from psp_sampling.verify import compare_assignments
        result=compare_assignments(str(dest/'Kenya_PSP_JOINT_315x2_PROVISIONAL.xlsx'),args.reference)
        reference_compare=result
        if not result['identical']:raise RuntimeError('Draw differs from frozen reference; retain both outputs and investigate')
    expected=[
       private_source,
       dest/'Kenya_PSP_Step1_Finger_Millet_Confirmed.xlsx',
       dest/'Kenya_PSP_Step2_Ward_Allocation_Finger_Millet_Confirmed.xlsx',
       dest/'Kenya_PSP_Step3_CORRECTED_Deduplicated_Draw.xlsx',
       dest/'Kenya_PSP_JOINT_315x2_PROVISIONAL.xlsx',
       dest/'PSP_Independent_Algorithm_Tests.json',
    ]
    manifest={
       'status':'PROVISIONAL - not an iShamba delivery authorization',
       'run_utc':datetime.now(timezone.utc).isoformat(),
       'completed_stages':completed,
       'reference_check':reference_compare,
       'configuration_sha256':sha(repo/'config/ward_groups_provisional.csv'),
       'files':{p.name:sha(p) for p in expected if p.exists()},
    }
    (dest/'run_manifest.json').write_text(json.dumps(manifest,indent=2,default=str)+'\n')
    print('DONE. PRIVATE files in:',dest,flush=True)
    print('Status: HOLD until authorized partner verification/consent. Never commit private workdir to Git.')

if __name__=='__main__':main()
