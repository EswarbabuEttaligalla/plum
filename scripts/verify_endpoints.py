import time
import httpx

base='http://127.0.0.1:8000'

for i in range(20):
    try:
        r=httpx.get(f'{base}/api/health', timeout=1.0)
        print('health', r.status_code, r.text)
        break
    except Exception as e:
        time.sleep(0.5)

try:
    r=httpx.get(f'{base}/openapi.json', timeout=5.0)
    print('openapi', r.status_code, 'paths_count=', len(r.json().get('paths', {})))
except Exception as e:
    print('openapi error', e)

# create claim
ts = int(time.time())
payload={'member_code':f'DEMO{ts}','treatment_date':'2026-05-01','total_amount':1200,
         'items':[{'description':'consultation','amount':1200,'category':'consultation_fees'}]}
try:
    r=httpx.post(f'{base}/api/claims/', json=payload, timeout=5.0)
    print('create', r.status_code, r.text)
    data=r.json()
    claim_id=data.get('id') or data.get('claim_code') or data.get('claim_id')
    print('claim_id', claim_id)
    if claim_id:
        # upload a sample bill and prescription
        try:
            files = {'file': ('bill.txt', 'diagnosis: fever\nconsultation_fee:1200', 'text/plain')}
            up = httpx.post(f'{base}/api/claims/{claim_id}/upload', data={'doc_type':'original_bills'}, files=files, timeout=10.0)
            print('upload', up.status_code, up.text)
        except Exception as e:
            print('upload error', e)

        p=httpx.post(f'{base}/api/claims/{claim_id}/process', json={}, timeout=10.0)
        print('process', p.status_code, p.text)
except Exception as e:
    print('create/process error', e)
