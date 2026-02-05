#!/usr/bin/env python3
import requests, json
URL='http://127.0.0.1:8080/api/chat/completions'
headers={'Content-Type':'application/json','Authorization':'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6ImM1MzZlMmRlLTJmMTctNGE2MS04M2MxLTBiYjFlZmFhZDRhMCIsImp0aSI6IjkzZGFkYTdmLWQ0NjUtNDM3Ny1iNTcyLTMwOTdhZmJiODc3ZCJ9.bSAPjQVXq656v6LvzJX9FMPkRlwBpMXtITeT8fHjy-4'}
data={'model':'gemini-2.5-flash','messages':[{'role':'user','content':'Say hi and return OK.'}],'stream':False}
resp = requests.post(URL,json=data,headers=headers,timeout=30)
print('status', resp.status_code)
try:
    print(json.dumps(resp.json(), indent=2)[:2000])
except Exception:
    print('raw text:', resp.text[:2000])
