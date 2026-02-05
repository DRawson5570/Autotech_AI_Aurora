#!/usr/bin/env python3
import requests
url='http://127.0.0.1:8080/api/v1/google/verify'
headers={'Content-Type':'application/json','Authorization':'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6ImM1MzZlMmRlLTJmMTctNGE2MS04M2MxLTBiYjFlZmFhZDRhMCIsImp0aSI6IjkzZGFkYTdmLWQ0NjUtNDM3Ny1iNTcyLTMwOTdhZmJiODc3ZCJ9.bSAPjQVXq656v6LvzJX9FMPkRlwBpMXtITeT8fHjy-4'}
resp = requests.post(url,json={'url':'https://generativelanguage.googleapis.com/v1','key':''}, headers=headers, timeout=10)
print(resp.status_code)
print(resp.headers)
print(resp.text)
