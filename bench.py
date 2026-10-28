"""Real Linux Gateway sampling. Mock upstream is labelled, never a Gateway substitute."""
import os,json,time,secrets,subprocess,threading,http.server,urllib.request,signal,statistics,sys
from pathlib import Path
if sys.platform != 'linux':raise SystemExit('Linux only; Windows execution is not a benchmark substitute.')
ROOT=Path.cwd(); OUT=ROOT/'evidence'; OUT.mkdir(exist_ok=True)
STATE=ROOT/'isolated'; STATE.mkdir(exist_ok=True)
TOKEN=secrets.token_hex(32); phase='setup'; stopping=False; gateway=None; mock_calls=[]; samples=[]; results=[]
SEARCH_ENABLED=os.environ.get('BENCH_SEARCH')=='1'
(OUT/'environment.json').write_text(json.dumps({'platform':os.uname()._asdict() if hasattr(os.uname(),'_asdict') else list(os.uname()),'cpu_count':os.cpu_count(),'clock_ticks_per_second':os.sysconf('SC_CLK_TCK'),'meminfo':Path('/proc/meminfo').read_text(),'cgroup':Path('/proc/self/cgroup').read_text()},indent=2))
def metrics():
    rows={}
    for p in Path('/proc').iterdir():
        if not p.name.isdigit(): continue
        try:
            text=(p/'stat').read_text(); v=text[text.rindex(')')+2:].split()
            rows[int(p.name)]={'pid':int(p.name),'ppid':int(v[1]),'ticks':int(v[11])+int(v[12])}
        except (OSError,ValueError): pass
    selected={gateway.pid} if gateway and gateway.poll() is None else set()
    while True:
        extra={pid for pid,r in rows.items() if r['ppid'] in selected}-selected
        if not extra: break
        selected |= extra
    procs=[]
    for pid in selected:
        try:
            m={}
            for line in Path(f'/proc/{pid}/smaps_rollup').read_text().splitlines():
                k,sep,v=line.partition(':')
                if sep and v.strip().split()[0].isdigit():m[k]=int(v.split()[0])
            status=Path(f'/proc/{pid}/status').read_text()
            hwm=next((int(x.split()[1]) for x in status.splitlines() if x.startswith('VmHWM:')),0)
            procs.append({**rows[pid],**{k:m.get(k,0) for k in ['Rss','Pss','SwapPss']},'VmHWM':hwm})
        except (OSError,ValueError):pass
    mem={x.split(':')[0]:int(x.split()[1]) for x in Path('/proc/meminfo').read_text().splitlines()}
    row={'time':time.time(),'phase':phase,'processes':procs,'rss_kib':sum(p['Rss'] for p in procs),'pss_kib':sum(p['Pss'] for p in procs),'mem_available_kib':mem['MemAvailable'],'swap_used_kib':mem['SwapTotal']-mem['SwapFree'],'memory_psi':Path('/proc/pressure/memory').read_text()}
    # Runner-wide cgroup is context, not Gateway-exclusive accounting.
    try:
        cg=Path('/sys/fs/cgroup')/Path('/proc/self/cgroup').read_text().strip().split('::',1)[1].lstrip('/')
        row['runner_cgroup']={n:(cg/n).read_text().strip() for n in ['memory.current','memory.peak','memory.events'] if (cg/n).exists()}
    except (OSError,IndexError):pass
    return row
def sampler():
    with (OUT/'timeseries.ndjson').open('w') as f:
        while not stopping:
            row=metrics(); samples.append(row); f.write(json.dumps(row)+'\n'); f.flush(); time.sleep(.5)
class Model(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        messages=data.get('messages',[]); last_user=max((i for i,m in enumerate(messages) if m.get('role')=='user'),default=-1)
        body=json.dumps(messages[last_user].get('content','')) if last_user>=0 else ''
        have_result=any(m.get('role')=='tool' for m in messages[last_user+1:])
        targets={'FETCH_SMALL':'https://example.com','FETCH_LARGE':'https://www.rfc-editor.org/rfc/rfc9110.html','FETCH_FAIL':'https://invalid.invalid/'}
        target=next((v for k,v in targets.items() if k in body),None)
        tools=[x.get('function',{}).get('name') for x in data.get('tools',[])]
        call=None
        if target and not have_result and 'web_fetch' in tools:
            call={'index':0,'id':'bench_'+secrets.token_hex(4),'type':'function','function':{'name':'web_fetch','arguments':json.dumps({'url':target,'extractMode':'text','maxChars':50000})}}
        if 'SEARCH_PUBLIC' in body and not have_result and 'web_search' in tools:
            call={'index':0,'id':'bench_'+secrets.token_hex(4),'type':'function','function':{'name':'web_search','arguments':json.dumps({'query':'Python 3.14 release official python.org','count':3})}}
        tool_results=[m.get('content') for m in messages[last_user+1:] if m.get('role')=='tool']
        mock_calls.append({'phase':phase,'message_count':len(messages),'tools':tools,'requested_fetch':bool(target),'emitted_tool_call':bool(call),'tool_result_received':have_result,'tool_results':tool_results})
        message={'role':'assistant','content':'Synthetic model reply; real Gateway path.'}
        if call:message={'role':'assistant','content':None,'tool_calls':[call]}
        self.send_response(200)
        if data.get('stream'):
            self.send_header('Content-Type','text/event-stream');self.end_headers()
            for delta,finish in [(message,None),({},'tool_calls' if call else 'stop')]:
                chunk={'id':'bench','object':'chat.completion.chunk','created':int(time.time()),'model':'bench','choices':[{'index':0,'delta':delta,'finish_reason':finish}]}
                self.wfile.write(('data: '+json.dumps(chunk)+'\n\n').encode())
            self.wfile.write(b'data: [DONE]\n\n');self.wfile.flush()
        else:
            self.send_header('Content-Type','application/json');self.end_headers()
            self.wfile.write(json.dumps({'id':'bench','object':'chat.completion','created':int(time.time()),'model':'bench','choices':[{'index':0,'message':message,'finish_reason':'tool_calls' if call else 'stop'}],'usage':{'prompt_tokens':50,'completion_tokens':10,'total_tokens':60}}).encode())
server=http.server.ThreadingHTTPServer(('127.0.0.1',18991),Model)
config={'gateway':{'mode':'local','bind':'loopback','port':18990,'auth':{'mode':'token','token':TOKEN},'http':{'endpoints':{'chatCompletions':{'enabled':True}}}},'agents':{'defaults':{'workspace':str(STATE/'workspace'),'skipBootstrap':True,'model':{'primary':'bench/bench'},'maxConcurrent':1}},'models':{'mode':'replace','providers':{'bench':{'baseUrl':'http://127.0.0.1:18991/v1','apiKey':'synthetic-not-a-real-key','api':'openai-completions','models':[{'id':'bench','name':'Synthetic upstream','contextWindow':32768,'contextTokens':16384,'maxTokens':1024,'reasoning':False,'input':['text'],'cost':{'input':0,'output':0,'cacheRead':0,'cacheWrite':0}}]}}},'tools':{'allow':['web_fetch'],'web':{'search':{'enabled':False},'fetch':{'enabled':True}}},'browser':{'enabled':False}}
if SEARCH_ENABLED:
    config['plugins']={'load':{'paths':[str(ROOT/'node_modules/@openclaw/duckduckgo-plugin')]},'entries':{'duckduckgo':{'enabled':True}}}
    config['tools']['allow'].append('web_search')
    config['tools']['web']['search']={'enabled':True,'provider':'duckduckgo'}
(STATE/'config.json').write_text(json.dumps(config));os.chmod(STATE/'config.json',0o600)
env={'PATH':os.environ['PATH'],'HOME':str(STATE),'OPENCLAW_STATE_DIR':str(STATE/'state'),'OPENCLAW_CONFIG_PATH':str(STATE/'config.json'),'OPENCLAW_NO_RESPAWN':'1','LANG':'C.UTF-8'}
def start(label):
    global gateway,phase
    phase=label
    print('PHASE '+phase,flush=True)
    log=(OUT/(label+'.log')).open('w')
    gateway=subprocess.Popen(['node',str(ROOT/'node_modules/openclaw/openclaw.mjs'),'gateway','run'],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    log.close()
    for _ in range(180):
        if gateway.poll() is not None:raise RuntimeError(f'Gateway exit {gateway.returncode}')
        try:
            with urllib.request.urlopen('http://127.0.0.1:18990/healthz',timeout=1) as r:
                if r.status==200:return
        except Exception:pass
        time.sleep(1)
    raise RuntimeError('Gateway startup timeout')
def stop():
    if gateway:
        try:os.killpg(gateway.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:gateway.wait(timeout=20)
        except subprocess.TimeoutExpired:
            os.killpg(gateway.pid,signal.SIGKILL);gateway.wait(timeout=10)
def turn(text,user):
    req=urllib.request.Request('http://127.0.0.1:18990/v1/chat/completions',data=json.dumps({'model':'openclaw:main','user':user,'messages':[{'role':'user','content':text}]}).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+TOKEN})
    before=len(mock_calls)
    try:
        with urllib.request.urlopen(req,timeout=90) as r:data=json.load(r)
        calls=mock_calls[before:]
        results.append({'phase':phase,'http':r.status,'provider_calls':len(calls),'choice_present':bool(data.get('choices')),'gateway_model_path_verified':bool(calls) and bool(data.get('choices')),'tool_roundtrip_observed':any(c['emitted_tool_call'] for c in calls) and any(c['tool_result_received'] for c in calls)})
    except Exception as e:results.append({'phase':phase,'error_type':type(e).__name__,'provider_calls':len(mock_calls)-before})
threading.Thread(target=server.serve_forever,daemon=True).start()
t=threading.Thread(target=sampler,daemon=True);t.start()
try:
    start('startup_1');phase='idle';print('PHASE '+phase,flush=True);time.sleep(int(os.environ.get('BENCH_IDLE_SECONDS','600')))
    phase='single_conversation';turn('Hello from the memory benchmark.','single');time.sleep(15)
    phase='continuous_20turns'
    for n in range(20):turn(f'Continue synthetic memory test turn {n}.','continuous')
    for key in ['FETCH_SMALL','FETCH_LARGE','FETCH_FAIL']:
        phase=key
        print('PHASE '+phase,flush=True)
        for n in range(3):turn(key,f'{key}-{n}')
        time.sleep(int(os.environ.get('BENCH_SETTLE_SECONDS','30')))
    if SEARCH_ENABLED:
        phase='SEARCH_PUBLIC';print('PHASE '+phase,flush=True)
        for n in range(3):turn('SEARCH_PUBLIC',f'search-{n}')
    phase='post_tasks_idle';time.sleep(int(os.environ.get('BENCH_POST_SECONDS','120')))
    stop();start('startup_2');phase='restart_idle';time.sleep(int(os.environ.get('BENCH_POST_SECONDS','120')))
except Exception as e:results.append({'phase':phase,'fatal':type(e).__name__,'detail':str(e)[:200]})
finally:
    phase='cleanup';stop();server.shutdown();stopping=True;t.join(timeout=5)
    for p in OUT.glob('*.log'):
        p.write_text(p.read_text(errors='replace').replace(TOKEN,'[REDACTED_LOCAL_GATEWAY_TOKEN]'))
    group_alive=False
    if gateway:
        try:os.killpg(gateway.pid,0);group_alive=True
        except ProcessLookupError:pass
    summary={}
    for label in sorted({x['phase'] for x in samples}):
        rows=[x for x in samples if x['phase']==label and x['processes']]
        if rows:summary[label]={'count':len(rows),'median_pss_mib':statistics.median(x['pss_kib'] for x in rows)/1024,'peak_pss_mib':max(x['pss_kib'] for x in rows)/1024,'peak_tree_rss_mib':max(x['rss_kib'] for x in rows)/1024}
    (OUT/'summary.json').write_text(json.dumps({'phases':summary,'requests':results,'mock_provider_calls':mock_calls,'model_quality':'NOT_VERIFIED_SYNTHETIC_UPSTREAM','real_search':'INSPECT_TOOL_RESULTS' if SEARCH_ENABLED else 'NOT_VERIFIED_DISABLED','deepseek_search':'NOT_VERIFIED_NO_KEY','gateway_exit':gateway.returncode if gateway else None,'gateway_group_remaining':group_alive,'sample_interval_seconds':.5},indent=2))
    if not summary or any('fatal' in x for x in results):raise SystemExit(1)
