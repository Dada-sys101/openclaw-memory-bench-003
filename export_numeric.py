import csv,json,sys,hashlib
from pathlib import Path
src=Path(sys.argv[1]); dest=Path(sys.argv[2]);dest.mkdir(parents=True,exist_ok=True)
rows=[json.loads(x) for x in (src/'timeseries.ndjson').read_text().splitlines()]
with (dest/'samples.csv').open('w',newline='') as f:
    writer=csv.writer(f);writer.writerow(['unix_time','phase','tree_rss_kib','tree_pss_kib','process_count','mem_available_kib','host_swap_used_kib','cgroup_memory_current_bytes','cgroup_memory_peak_bytes','cgroup_events'])
    for r in rows:
        cg=r.get('runner_cgroup',{})
        writer.writerow([r['time'],r['phase'],r['rss_kib'],r['pss_kib'],len(r['processes']),r['mem_available_kib'],r['swap_used_kib'],cg.get('memory.current'),cg.get('memory.peak'),cg.get('memory.events','').replace('\n',';')])
for filename in ['analysis.json','container-state.json','tool-evidence.json','test-config.json']:
    if (src/filename).exists():(dest/filename).write_bytes((src/filename).read_bytes())
for p in dest.iterdir():
    if p.is_file():p.write_bytes(p.read_bytes().replace(b'\r\n',b'\n'))
manifest={'original_timeseries_sha256':hashlib.sha256((src/'timeseries.ndjson').read_bytes()).hexdigest(),'sample_count':len(rows),'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.iterdir() if p.is_file() and p.name!='checksums.json'}}
(dest/'checksums.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps({'exported':str(dest),'sample_count':len(rows)},indent=2))
