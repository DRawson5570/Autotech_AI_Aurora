#!/usr/bin/env python3
import subprocess
kf='/home/drawson/gary_gemini_api_key'
with open(kf) as f: k=f.read().strip()
print('KEY_MASKED', k[:6]+'...'+k[-6:])
candidates=['models/gemini-3.0-pro','models/gemini-3.0','models/gemini-3-pro','models/gemini-3']
for c in candidates:
    endpoint = f"https://generativelanguage.googleapis.com/v1/{c}:generateContent?key={k}"
    print('\nTRY', endpoint)
    proc = subprocess.run(['curl','-sS','-i','-H','Content-Type: application/json','-d','{"contents":[{"parts":[{"text":"Hello"}]}]}', endpoint], capture_output=True, text=True)
    out=proc.stdout+proc.stderr
    print('resp snippet:', out[:1000].replace('\n',' | '))
