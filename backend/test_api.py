import urllib.request
import json

try:
    req = urllib.request.Request('http://localhost:8000/api/force-evaluate/C001', method='POST', data=b"{}")
    req.add_header('Content-Type', 'application/json')
    response = urllib.request.urlopen(req)
    print(response.read().decode('utf-8'))
except Exception as e:
    if hasattr(e, 'read'):
        print(e.read().decode('utf-8'))
    else:
        print(str(e))
