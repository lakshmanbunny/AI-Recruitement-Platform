import urllib.request
import urllib.error

urls = [
    'http://127.0.0.1:8000/api/rag/retrieval-metrics/C001',
    'http://127.0.0.1:8000/api/rag-evaluation-status/C001'
]

for url in urls:
    try:
        req = urllib.request.urlopen(url)
        print(f"Success {url}:", req.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Error {url}:", e.read().decode())
    except Exception as e:
        print(f"Failed {url}:", str(e))
