#!/usr/bin/env python3
"""Five-endpoint HTTP smoke check. Writes only to the isolated demo namespace.

Uses the Python standard library. Start backend first. API_TOKEN is read from the
process environment, not from frontend files. Use synthetic data only.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8080')
    parser.add_argument('--origin', default='', help='Optional expected allowed frontend origin for CORS checks.')
    parser.add_argument('--report', default=str(Path(__file__).resolve().parents[1]/'reports/http-sandbox.json'))
    args = parser.parse_args()
    base = args.base_url.rstrip('/')
    url = urlsplit(base)
    if url.scheme not in ('http', 'https') or not url.netloc or url.path or url.query or url.fragment or url.username:
        raise ValueError('Use an HTTP(S) base URL only, without API paths or credentials.')
    token = os.environ.get('API_TOKEN', '')
    checks = []
    def check(name, condition):
        if not condition: raise AssertionError(name)
        checks.append(name); print('PASS', name)
    def request(path, data=None, method=None, extra=None):
        headers = {'Accept': 'application/json'}
        if args.origin: headers['Origin'] = args.origin
        if data is not None:
            headers['Content-Type'] = 'application/json'
            if token: headers['Authorization'] = 'Bearer ' + token
        headers.update(extra or {})
        req = Request(base + path, data=None if data is None else json.dumps(data).encode(), headers=headers, method=method)
        try:
            with urlopen(req, timeout=90) as response: status, raw, result_headers = response.status, response.read(), dict(response.headers)
        except HTTPError as e: status, raw, result_headers = e.code, e.read(), dict(e.headers)
        try: result = json.loads(raw)
        except json.JSONDecodeError: result = raw.decode('utf-8', errors='replace')
        return status, result, {key.lower(): value for key,value in result_headers.items()}
    status, before, _ = request('/v1/healthz')
    check('judge health', status==200 and before['status']=='ok')
    status, health, _ = request('/demo/v1/healthz')
    check('sandbox health', status==200 and health['status']=='ok')
    status, metadata, _ = request('/demo/v1/metadata')
    check('sandbox metadata', status==200 and bool(metadata.get('model')))
    if args.origin:
        status, _, headers = request('/demo/v1/reply', method='OPTIONS', extra={
            'Access-Control-Request-Method':'POST', 'Access-Control-Request-Headers':'content-type,authorization'})
        check('CORS preflight', status==200 and headers.get('access-control-allow-origin') in ('*',args.origin))
    identifier = 'http_' + uuid.uuid4().hex
    now = datetime.now(timezone.utc); stamp = now.isoformat()
    category = {'slug':identifier+'_restaurants','voice':{'tone':'warm_busy_practical'},'peer_stats':{'avg_ctr':0.03}}
    merchant = {'merchant_id':identifier+'_m','category_slug':category['slug'],
                'identity':{'name':'Synthetic Demo Café','owner_first_name':'Asha','languages':['en'],'verified':True},
                'performance':{'calls':20,'views':800,'window_days':30,'ctr':0.025},
                'offers':[{'id':'offer1','title':'Lunch Thali @ ₹149','status':'active'}]}
    trigger = {'id':identifier+'_t','merchant_id':merchant['merchant_id'],'scope':'merchant','kind':'perf_dip',
               'payload':{'metric':'calls','delta_pct':-0.4,'window':'7d'},'urgency':3,
               'suppression_key':identifier,'expires_at':(now+timedelta(days=1)).isoformat()}
    for scope, key, payload in [('category','slug',category),('merchant','merchant_id',merchant),('trigger','id',trigger)]:
        body={'scope':scope,'context_id':payload[key],'version':2,'payload':payload,'delivered_at':stamp}
        status, ack, _=request('/demo/v1/context',body)
        check('context '+scope,status==200 and ack.get('accepted'))
        status, replay, _=request('/demo/v1/context',body)
        check('context idempotency '+scope,status==200 and replay==ack)
        body['version']=1
        status, stale, _=request('/demo/v1/context',body)
        check('stale version '+scope,status==409 and stale.get('reason')=='stale_version')
    tick={'now':stamp,'available_triggers':[trigger['id']]}
    status, result, _=request('/demo/v1/tick',tick)
    check('tick action',status==200 and len(result.get('actions',[]))==1)
    action=result['actions'][0]
    check('grounded initial message','40%' in action['body'] and '20 calls' in action['body'])
    status, duplicate, _=request('/demo/v1/tick',tick)
    check('duplicate tick suppressed',status==200 and duplicate=={'actions':[]})
    inbound={'conversation_id':action['conversation_id'],'merchant_id':merchant['merchant_id'],'customer_id':None,
             'from_role':'merchant','message':'Yes, send the draft','turn_number':1,
             'received_at':(now+timedelta(seconds=1)).isoformat()}
    status, response, _=request('/demo/v1/reply',inbound)
    check('reply drafts',status==200 and response.get('action')=='send' and bool(response.get('body')))
    status, replay, _=request('/demo/v1/reply',inbound)
    check('reply exact retry',status==200 and replay==response)
    inbound.update(message='STOP',turn_number=2,received_at=(now+timedelta(seconds=2)).isoformat())
    status, response, _=request('/demo/v1/reply',inbound)
    check('STOP ends session',status==200 and response.get('action')=='end')
    status, after, _=request('/v1/healthz')
    check('judge context counts unchanged',status==200 and after['contexts_loaded']==before['contexts_loaded'])
    report={'executed_at':datetime.now(timezone.utc).isoformat(),'checks_passed':len(checks),'checks':checks,
            'note':'Local or manually selected HTTP target. Synthetic demo writes only. No deployment or quality-score claim.'}
    p=Path(args.report); p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(report,indent=2)+'\n')
    print(f'{len(checks)} checks passed; {p}')

if __name__=='__main__':
    try: main()
    except (ValueError, AssertionError, URLError, TimeoutError, KeyError, TypeError) as e:
        print(f'FAILED: {e}',file=sys.stderr);raise SystemExit(1)
