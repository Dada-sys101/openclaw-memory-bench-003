import json,sys,re
from pathlib import Path
root=Path(sys.argv[1]); summary=json.loads((root/'summary.json').read_text()); out=[]
for call in summary.get('mock_provider_calls',[]):
    if not call.get('tool_results'):continue
    for content in call['tool_results']:
        if isinstance(content,list):content='\n'.join(x.get('text','') for x in content if isinstance(x,dict))
        if not isinstance(content,str):content=json.dumps(content)
        try:value=json.loads(content)
        except Exception:
            value={'provider_visible_payload_truncated_or_non_json':True,'received_chars':len(content)}
            for key in ['url','status','length','rawLength','truncated','cached','extractor']:
                match=re.search(r'"'+key+r'"\s*:\s*("[^"\n]*"|[0-9]+|true|false)',content)
                if match:value[key]=json.loads(match.group(1))
        if isinstance(value,dict):
            selected={k:v for k,v in value.items() if k in ['url','finalUrl','status','kind','provider','count','length','rawLength','truncated','cached','tookMs','extractor','received_chars','provider_visible_payload_truncated_or_non_json']}
            if 'results' in value:selected['source_urls']=[x.get('url') for x in value['results']]
            if 'error' in value:selected['error_class']='ENOTFOUND' if 'ENOTFOUND' in str(value['error']) else 'provider_error'
        else:selected={'result':value}
        out.append({'phase':call['phase'],'result':selected})
(root/'tool-evidence.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
