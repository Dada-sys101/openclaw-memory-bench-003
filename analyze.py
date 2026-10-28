import json,statistics,sys
from pathlib import Path
root=Path(sys.argv[1]); rows=[json.loads(x) for x in (root/'timeseries.ndjson').read_text().splitlines()]
out={}
for phase in dict.fromkeys(x['phase'] for x in rows):
    r=[x for x in rows if x['phase']==phase and x['processes']]
    if not r:continue
    rss=[x['rss_kib']/1024 for x in r];pss=[x['pss_kib']/1024 for x in r]
    start,end=r[0]['time'],r[-1]['time']
    early=[x['pss_kib']/1024 for x in r if x['time']<start+30]
    late=[x['pss_kib']/1024 for x in r if x['time']>end-30]
    ticks=0; elapsed=0
    for a,b in zip(r,r[1:]):
        aa={p['pid']:p['ticks'] for p in a['processes']};bb={p['pid']:p['ticks'] for p in b['processes']}
        ticks+=sum(max(0,bb[k]-aa[k]) for k in aa.keys()&bb.keys());elapsed+=b['time']-a['time']
    out[phase]={'seconds':round(end-start,2),'samples':len(r),'pss_median_mib':round(statistics.median(pss),2),'pss_peak_mib':round(max(pss),2),'rss_median_mib':round(statistics.median(rss),2),'rss_peak_mib':round(max(rss),2),'early30_pss_median_mib':round(statistics.median(early),2),'late30_pss_median_mib':round(statistics.median(late),2),'cpu_pct_one_core':round(ticks/100/elapsed*100,2) if elapsed else None,'max_processes':max(len(x['processes']) for x in r)}
summary=json.loads((root/'summary.json').read_text())
out['_verification']={'requests_total':len(summary['requests']),'gateway_model_path_verified':sum(x.get('gateway_model_path_verified',False) for x in summary['requests']),'tool_roundtrips':sum(x.get('tool_roundtrip_observed',False) for x in summary['requests']),'requests_with_errors':[x for x in summary['requests'] if 'error_type' in x or 'fatal' in x],'gateway_exit':summary['gateway_exit'],'gateway_group_remaining':summary.get('gateway_group_remaining'),'continuous_message_counts':[x['message_count'] for x in summary['mock_provider_calls'] if x['phase']=='continuous_20turns']}
out['_cgroup_last']=next((x.get('runner_cgroup') for x in reversed(rows) if x.get('runner_cgroup')),None)
out['_max_process_VmHWM_mib']=max((p.get('VmHWM',0)/1024 for x in rows for p in x['processes']),default=0)
(root/'analysis.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
