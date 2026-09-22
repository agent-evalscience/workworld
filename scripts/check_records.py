#!/usr/bin/env python3
"""Independent consistency checks for public release records.

These checks establish consistency of released records, not actual model execution.
"""
import argparse
import csv
import hashlib
import json
import math
import re
import random
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('release', type=Path, nargs='?', default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path)
    args=parser.parse_args()
    root=args.release.resolve(); data=root/'data'
    failures=[]; checked=[]
    def check(test, message):
        (checked if bool(test) else failures).append(message)
    def close(a,b): return math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-10)
    def load(name): return json.loads((data/name).read_text())
    def digest_file(path): return hashlib.sha256(path.read_bytes()).hexdigest()
    def time(value): return datetime.fromisoformat(str(value).replace('Z','+00:00'))
    def keys(frame): return set(zip(frame.run_id,frame.criterion_id))
    def source_set(items): return {(x['surface'],x['locator']) for x in items}
    def proportions(frame):
        obs=frame[frame.access_label!='unknown']
        return {'pass':float(frame['pass'].mean()),'pass_n':int(frame['pass'].sum()),'n':len(frame),'access':float((obs.access_label=='accessed').mean())}
    c=pd.read_csv(data/'criterion_results.csv'); r=pd.read_csv(data/'run_ledger.csv')
    a=pd.read_csv(data/'attempt_ledger.csv'); matched=load('matched_results.json')
    validation=load('validation_results.json'); evidence=load('evidence_map_final.json')
    mapping=pd.read_csv(data/'task_mapping.csv')
    check(len(r)==192 and r.run_id.nunique()==192,'192 unique run records')
    check(len(c)==1728 and len(keys(c))==1728,'1728 unique criterion executions')
    check(c.criterion_id.nunique()==72,'72 criterion definitions')
    check(c.task_id.nunique()==8 and len(mapping)==8,'eight tasks with eight task labels')
    check(len(validation['seat_materializations']['fingerprints'])==6,'six employee seats')
    check(set(c.task_id)==set(mapping.task_id)==set(r.task_id),'task identifiers join across files')
    check(set(c.run_id)==set(r.run_id),'run identifiers join')
    check(set(r.agent_id)=={'opus5','grok','sol'},'three candidate-agent identifiers')
    check(set(r.condition)=={'world_first','task_first'},'two construction conditions')
    check((r.groupby(['task_id','agent_id','condition']).size()==4).all(),'four runs per task-agent-condition')
    check((c.groupby('condition').size()==864).all(),'864 criterion executions per condition')
    check((c.groupby('criterion_id').size()==24).all(),'24 executions per criterion')
    check(not c.grader_error.any() and c['pass'].notna().all(),'all completed rows have valid scores')
    check(c.access_label.isin(['accessed','not_accessed','unknown']).all(),'valid access states')
    reasons={'trace_truncated','missing_tool_output','ambiguous_source_match','unsupported_surface_log','other'}
    check(c.loc[c.access_label=='unknown','access_unknown_reason'].isin(reasons).all(),'unknown access states have reasons')
    check(c.loc[c.access_label!='unknown','access_unknown_reason'].isna().all(),'observed access states have no unknown reason')
    cg=c.groupby('run_id').agg(criterion_count=('criterion_id','size'),pass_count=('pass','sum'),accessed_count=('access_label',lambda x:(x=='accessed').sum()),not_accessed_count=('access_label',lambda x:(x=='not_accessed').sum()),unknown_count=('access_label',lambda x:(x=='unknown').sum()))
    rr=r.set_index('run_id')
    for field in cg: check((rr.loc[cg.index,field]==cg[field]).all(),f'run totals reconcile: {field}')
    joined=c.merge(r,on='run_id',suffixes=('','_run'),validate='many_to_one')
    for field in ['task_id','agent_id','condition','environment_instance']:
        check((joined[field]==joined[field+'_run']).all(),f'criterion/run metadata reconcile: {field}')
    for (task,agent,block),group in r.groupby(['task_id','agent_id','block']):
        check(len(group)==4 and group.condition.eq('world_first').sum()==2 and group.environment_instance.eq('task-first curator 1').sum()==1 and group.environment_instance.eq('task-first curator 2').sum()==1,f'balanced collection block {task}/{agent}/{block}')
    for (task,agent),group in r.groupby(['task_id','agent_id']):
        check(sorted(group.scheduled_order_within_task_agent)==list(range(1,9)),f'eight scheduled positions {task}/{agent}')

    # Canonical hashes identify public CSV rows, never withheld trajectories.
    for name,hash_field,old_fields in [('run_ledger.csv','run_record_sha256',{'trace_sha256','output_sha256'}),('criterion_results.csv','criterion_record_sha256',{'grader_output_sha256'})]:
        rows=list(csv.DictReader((data/name).open(newline='')))
        check(not old_fields.intersection(rows[0]),f'{name} excludes unsupported raw-artifact hash columns')
        check(hash_field in rows[0],f'{name} has explicit release-record digest')
        if hash_field in rows[0]:
            for i,row in enumerate(rows,2):
                payload={k:v for k,v in row.items() if not k.endswith('_sha256')}
                expected=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                check(row[hash_field]==expected,f'{name}:{i} record digest')

    # Every nested matched-study result must be the same public observation.
    nested=[]
    for run in matched['runs']:
        check(run['run_id'] in rr.index,f'matched run exists {run["run_id"]}')
        for field in ['task_id','agent_id','condition','environment_instance','model_version_string','status','scheduled_order_within_task_agent']:
            check(run[field]==rr.loc[run['run_id'],field],f'matched run field {run["run_id"]}/{field}')
        config=root/run.get('agent_config_path',f'data/configs/agent_{run["agent_id"]}.yaml')
        check(config.exists() and digest_file(config)==run['agent_config_sha256'],f'agent config digest {run["run_id"]}')
        text=config.read_text()
        config_model=re.search(r'^model_version:\s*(.+)$',text,re.M)
        if config_model: check(config_model.group(1).strip().strip('\"\'')==run['model_version_string'],f'config model alias {run["run_id"]}')
        for row in run['criterion_results']: nested.append({'run_id':run['run_id'],**row})
    nc=pd.DataFrame(nested)
    check(keys(nc)==keys(c),'matched JSON has exactly the criterion ledger keys')
    nj=nc.merge(c,on=['run_id','criterion_id'],suffixes=('_json','_csv'),validate='one_to_one')
    for field in ['pass','access_label','grading_route','grader_error','access_unknown_reason']:
        check((nj[field+'_json'].fillna('')==nj[field+'_csv'].fillna('')).all(),f'matched JSON criterion values: {field}')
    grade=matched['grading']; config=root/grade['grader_config_path']
    check(config.exists() and digest_file(config)==grade['grader_config_sha256'],'grader config digest matches actual file')
    check(not r.model_version_string.str.contains(r'-202\d{5,}',regex=True).any(),'model strings use public aliases rather than invented dated versions')

    # Schedule chronology and all retries are checked independently.
    low=datetime(2026,8,12,23,59,59,tzinfo=timezone.utc); high=datetime(2026,9,21,tzinfo=timezone.utc)
    a['_start']=a.started_at.map(time); a['_end']=a.completed_at.map(time)
    check(a.attempt_id.is_unique,'attempt identifiers unique')
    check(set(a.scheduled_run_id)==set(r.run_id),'attempt and run identifiers join')
    check(((a._start>low)&(a._end<high)&(a._end>a._start)).all(),'attempt dates after Aug12 and before Sep21 with positive duration')
    for run_id,group in a.groupby('scheduled_run_id'):
        group=group.sort_values('attempt_number'); run=rr.loc[run_id]
        timeout=1800 if run.task_id in {'T08','T07'} else 3600
        check(list(group.attempt_number)==list(range(1,len(group)+1)),f'consecutive attempt numbers {run_id}')
        check(group.iloc[-1].status=='completed' and (group.status=='completed').sum()==1,f'one final completed attempt {run_id}')
        check(all(group.iloc[i]._end<group.iloc[i+1]._start for i in range(len(group)-1)),f'retries start after prior termination {run_id}')
        for idx,row in group.iterrows():
            duration=(row._end-row._start).total_seconds(); is_last=row.attempt_number==len(group)
            check(bool(row.retried)==(not is_last),f'retried flag {row.attempt_id}')
            check(not (row.timed_out and row.crashed),f'failure flags mutually exclusive {row.attempt_id}')
            if row.status=='completed':
                check(not row.timed_out and not row.crashed and pd.isna(row.retry_reason),f'completed attempt clean flags {row.attempt_id}')
                check(duration<=timeout,f'completed attempt within configured timeout {row.attempt_id}')
            else:
                check(pd.notna(row.retry_reason),f'failed attempt has reason {row.attempt_id}')
                if row.timed_out and row.retry_reason=='wall_clock_timeout':check(duration>=timeout,f'wall-clock timeout lasted configured limit {row.attempt_id}')
        if 'duration_s' in group:check(np.allclose(group.duration_s,(group._end-group._start).dt.total_seconds()),f'explicit durations agree {run_id}')
    starts=a.groupby('scheduled_run_id')._start.min()
    for (task,agent),group in r.groupby(['task_id','agent_id']):
        order=group.sort_values('scheduled_order_within_task_agent').run_id
        times=[starts[x] for x in order]
        check(times==sorted(times),f'actual starts respect scheduled task-agent order {task}/{agent}')

    # Audit sampling probabilities refer to the published sampling population.
    for name,rating_file in [('grader','grader_audit_ratings.csv'),('access','access_label_audit_ratings.csv')]:
        manifest=pd.read_csv(data/f'{name}_audit_sample_manifest.csv'); ratings=pd.read_csv(data/rating_file)
        check(len(keys(ratings))==len(ratings)==len(manifest) and keys(ratings)==keys(manifest),f'{name} sample keys and sizes agree')
        population=c[c.grading_route=='semantic'].copy() if name=='grader' else c.copy()
        population['_stratum']=population.task_id+'|'+population.agent_id+'|'+population.condition if name=='grader' else population.condition+'|'+population.access_label
        pj=manifest.merge(population,on=['run_id','criterion_id'],suffixes=('_manifest','_ledger'),validate='one_to_one')
        check(len(pj)==len(manifest),f'{name} samples all belong to intended population')
        check((pj.stratum==pj._stratum).all(),f'{name} stratum labels match current ledger')
        for stratum,group in manifest.groupby('stratum'):
            total=population._stratum.eq(stratum).sum()
            check(total>0 and np.allclose(group.selection_probability,len(group)/total,atol=1e-12,rtol=1e-12),f'{name} inclusion probabilities {stratum}')
        check(manifest.seed.nunique()==1,f'{name} records one sampling seed')
        sample_rng=random.Random(int(manifest.seed.iloc[0]))
        grouping=['task_id','agent_id','condition'] if name=='grader' else ['condition','access_label']
        groups={tuple(key):group.sort_values(['run_id','criterion_id']) for key,group in population.groupby(grouping)}
        stratum_keys=sorted(groups)
        if name=='grader':allocations={key:5 for key in stratum_keys}
        else:
            expected={key:len(manifest)*len(groups[key])/len(population) for key in stratum_keys}
            allocations={key:math.floor(expected[key]) for key in stratum_keys}
            remainder=len(manifest)-sum(allocations.values())
            for key in sorted(stratum_keys,key=lambda key:(-(expected[key]-allocations[key]),key))[:remainder]:allocations[key]+=1
        resampled=[]
        for key in stratum_keys:
            ordered=list(zip(groups[key].run_id,groups[key].criterion_id))
            resampled.extend(sample_rng.sample(ordered,allocations[key]))
        sample_rng.shuffle(resampled)
        check(resampled==list(zip(manifest.run_id,manifest.criterion_id)),f'{name} sample exactly reproduced from seed and population')
        rj=ratings.merge(c,on=['run_id','criterion_id'],suffixes=('_audit','_ledger'),validate='one_to_one')
        check(len(rj)==len(ratings),f'{name} rating keys all join')
        if name=='grader':
            check((rj.grader_pass==rj['pass']).all(),'frozen grader labels match current outcomes')
            check((rj.grading_route=='semantic').all(),'semantic-grader audit excludes deterministic executions')
            expert=ratings.expert_verdict.eq('pass'); grade=ratings.grader_pass
            contingency={'both_pass':int((expert&grade).sum()),'both_fail':int((~expert&~grade).sum()),'expert_only_pass':int((expert&~grade).sum()),'grader_only_pass':int((~expert&grade).sum())}
            check(sum(contingency.values())==len(ratings),'grader audit contingency covers all ratings')
            check(close((expert==grade).mean(),(contingency['both_pass']+contingency['both_fail'])/len(ratings)),'grader audit agreement recomputes')
        else:
            check((rj.automated_label==rj.access_label).all(),'frozen automated access labels match current ledger')
            for coder in ['a','b']:
                separate=pd.read_csv(data/f'access_label_coder_{coder}.csv')
                sj=separate.merge(ratings,on=['audit_id','run_id','task_id','criterion_id'],validate='one_to_one')
                check(len(sj)==len(ratings) and (sj.label==sj[f'coder_{coder}']).all(),f'coder {coder} submission agrees with merged audit')
                check((separate.submitted_at.map(time)>a._end.max()).all(),f'coder {coder} labels after run completion')

    # Packets must cover at least one declared sufficient source set per criterion.
    criteria={x['criterion_id']:x for x in evidence['criteria']}
    check(set(criteria)==set(c.criterion_id),'evidence-map criterion coverage')
    freeze=time(evidence['frozen_at']);check(freeze<a._start.min(),'evidence map frozen before runs')
    check(len(matched['packet_construction'])==16,'two curator packets for each of eight tasks')
    for packet in matched['packet_construction']:
        task=packet['task_id']; curator=packet['curator_id']; final=source_set(packet['final_sources']); submitted=source_set(packet['as_submitted_sources'])
        check(len(final)==packet['final_packet_size'] and len(submitted)==packet['submitted_packet_size'],f'packet sizes count distinct sources {task}/{curator}')
        taskcriteria=[x for x in criteria.values() if x['task_id']==task]
        check(len(taskcriteria)==packet['total_criteria'],f'packet criterion count {task}/{curator}')
        sufficient=lambda sources,criterion:any(source_set(s)<=sources for s in criterion['sufficient_sets'])
        final_count=sum(sufficient(final,x) for x in taskcriteria); submitted_count=sum(sufficient(submitted,x) for x in taskcriteria)
        check(final_count==len(taskcriteria),f'final packet covers sufficient sets {task}/{curator}')
        check(submitted_count==packet['pre_repair_solvable_criteria'] and len(taskcriteria)-submitted_count==packet['missing_criteria'],f'pre-repair coverage matches declarations {task}/{curator}')
        check(freeze<=time(packet['submitted_at'])<=time(packet['completeness_reviewed_at'])<=time(packet['finalized_at'])<a._start.min(),f'packet chronology {task}/{curator}')
        history=[time(x['timestamp']) for x in packet['revision_history']]
        check(history==sorted(history),f'packet stage order {task}/{curator}')
    evcsv=pd.read_csv(data/'evidence_map_final.csv')
    check(set(evcsv.criterion_id)==set(criteria),'evidence map CSV/JSON criterion join')
    for _,row in evcsv.iterrows():
        item=criteria[row.criterion_id]
        check(row.task_id==item['task_id'] and row.final_solvable==item['final_solvable'],f'evidence-map status {row.criterion_id}')

    # Released tables must be computed from the released ledger.
    for name,identifier in [('by_task','task_id'),('by_agent','agent_id')]:
        table=pd.read_csv(data/'tables'/f'{name}.csv')
        check(set(table[identifier])==set(c[identifier]),f'{name} coverage')
        for _,row in table.iterrows():
            group=c[c[identifier]==row[identifier]]; ps={cond:proportions(group[group.condition==cond]) for cond in ['world_first','task_first']}
            for cond,values in ps.items():
                for metric,value in values.items(): check(close(row[f'{cond}_{metric}'],value),f'{name} {row[identifier]} {cond} {metric}')
            for metric in ['pass','access']:check(close(row[f'{metric}_rd'],ps['task_first'][metric]-ps['world_first'][metric]),f'{name} {row[identifier]} {metric} contrast')
    packets=pd.read_csv(data/'tables/by_packet.csv')
    for _,row in packets.iterrows():
        group=c[c.task_id==row.task_id]; values=[]
        for i in [1,2]:
            value=group.loc[group.environment_instance==f'task-first curator {i}','pass'].mean();values.append(value)
            check(close(row[f'packet{i}_pass'],value),f'packet table {row.task_id}/{i}')
        check(close(row.packet2_minus_packet1,values[1]-values[0]),f'packet table difference {row.task_id}')
    loo=pd.read_csv(data/'tables/leave_one_task_out.csv')
    for _,row in loo.iterrows():
        group=c[c.task_id!=row.held_out_task]; p={cond:proportions(group[group.condition==cond]) for cond in ['world_first','task_first']}
        for metric in ['pass','access']:check(close(row[f'{metric}_rd'],p['task_first'][metric]-p['world_first'][metric]),f'leave-one-task-out {row.held_out_task}/{metric}')
    result={'status':'PASS' if not failures else 'FAIL','checks_passed':len(checked),'checks_failed':len(failures),'failures':failures,'scope':'Public-record consistency only; does not authenticate real executions.'}
    print(json.dumps(result,indent=2))
    if args.output:args.output.write_text(json.dumps(result,indent=2)+'\n')
    return int(bool(failures))


if __name__=='__main__':raise SystemExit(main())
