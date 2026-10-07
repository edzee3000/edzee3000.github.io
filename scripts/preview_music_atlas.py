"""Serve the Music include locally without Ruby. This is not a full Jekyll build."""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

class PreviewHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if self.path.split('?')[0] in ['/music', '/music/']:
            body=(ROOT/'_includes/music-atlas.html').read_text(encoding='utf-8')
            body=re.sub(r"\{\{\s*'([^']+)'\s*\|\s*relative_url\s*\}\}",r'\1',body)
            page='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Music · Between the echoes</title></head><body>'+body+'</body></html>'
            data=page.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Content-Length',str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            super().do_GET()

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=4173)
    args=parser.parse_args()
    print(f'Local design preview: http://127.0.0.1:{args.port}/music/',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),PreviewHandler).serve_forever()
