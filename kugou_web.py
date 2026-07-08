#!/usr/bin/env python3
"""酷狗音乐 Web 服务 —— 手机浏览器打开即可搜歌下载"""
import json, os, sys, re, time, threading, urllib.parse
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler

# 输出目录（kugou_spider.py 所在位置）
OUTPUT_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output"))
sys.path.insert(0, OUTPUT_DIR)
import kugou_spider

DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output", "kugou_downloads")

HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>酷狗下载</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#f5f5f5;color:#333;max-width:600px;margin:0 auto;padding:16px}
h2{text-align:center;margin:10px 0 16px;font-size:20px;color:#1a73e8}
.search-box{display:flex;gap:8px;margin-bottom:16px}
.search-box input{flex:1;padding:12px;border:1px solid #ddd;border-radius:8px;font-size:16px;outline:none}
.search-box button{padding:12px 20px;background:#1a73e8;color:#fff;border:none;border-radius:8px;font-size:16px;cursor:pointer}
.song-item{display:flex;align-items:center;padding:12px;background:#fff;border-radius:8px;margin-bottom:8px;gap:10px}
.song-info{flex:1;min-width:0}
.song-name{font-size:15px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.song-singer{font-size:13px;color:#888;margin-top:2px}
.btn{flex-shrink:0;padding:8px 14px;border:none;border-radius:6px;font-size:13px;cursor:pointer}
.btn-down{background:#1a73e8;color:#fff}
.btn-down:disabled{background:#ccc}
.loading{text-align:center;padding:20px;color:#888}
.error{text-align:center;padding:20px;color:#e53935}
.toast{position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#333;color:#fff;padding:10px 20px;border-radius:8px;font-size:14px;z-index:999;display:none}
.cnt{text-align:center;color:#888;font-size:13px;margin-top:30px}
</style>
</head>
<body>
<h2>酷狗音乐下载</h2>
<div class="search-box">
<input type="text" id="kw" placeholder="输入歌名或歌手..." autofocus>
<button onclick="search()">搜索</button>
</div>
<div id="result"></div>
<div id="toast" class="toast"></div>
<div class="cnt">搜索免费歌曲，点击即可下载到电脑</div>
<script>
function showToast(msg){var t=document.getElementById('toast');t.textContent=msg;t.style.display='block';setTimeout(function(){t.style.display='none'},2000)}
function search(){var kw=document.getElementById('kw').value.trim();if(!kw)return;var btn=document.querySelector('button');btn.disabled=true;btn.textContent='搜索中...';document.getElementById('result').innerHTML='<div class="loading">搜索中...</div>';
fetch('/api/search?kw='+encodeURIComponent(kw)).then(r=>r.json()).then(data=>{btn.disabled=false;btn.textContent='搜索';if(!data.songs||data.songs.length===0){document.getElementById('result').innerHTML='<div class="error">没有找到相关歌曲</div>';return}
var html='';data.songs.forEach(function(s,i){html+='<div class="song-item"><div class="song-info"><div class="song-name">'+s.name+'</div><div class="song-singer">'+s.singer+'</div></div><button class="btn btn-down" onclick="download(\''+s.hash+'\',\''+s.album_id+'\',this)" id="btn'+i+'">下载</button></div>'})
document.getElementById('result').innerHTML=html}).catch(function(){btn.disabled=false;btn.textContent='搜索';document.getElementById('result').innerHTML='<div class="error">搜索失败，请重试</div>'})}
function download(hash,album_id,btn){btn.disabled=true;btn.textContent='...';showToast('开始下载...');
fetch('/api/download?hash='+hash+'&album_id='+album_id+'&name='+encodeURIComponent(btn.parentElement.querySelector('.song-name').textContent)+'&singer='+encodeURIComponent(btn.parentElement.querySelector('.song-singer').textContent)).then(r=>r.json()).then(data=>{if(data.ok){btn.textContent='已下载';btn.style.background='#4caf50';showToast('下载完成: '+data.filename)}else{btn.disabled=false;btn.textContent='付费';btn.style.background='#ff9800';showToast('需要VIP')}}).catch(function(){btn.disabled=false;btn.textContent='重试';showToast('下载失败')})}
document.getElementById('kw').addEventListener('keydown',function(e){if(e.key==='Enter')search()})
</script>
</body>
</html>"""

class Handler(BaseHTTPRequestHandler):
    def _send_json(self, data, code=200):
        self.send_response(code)
        self.send_header('Content-Type','application/json;charset=utf-8')
        self.send_header('Access-Control-Allow-Origin','*')
        self.end_headers()
        self.wfile.write(json.dumps(data,ensure_ascii=False).encode())

    def _send_html(self, html, code=200):
        self.send_response(code)
        self.send_header('Content-Type','text/html;charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode())

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == '/' or path == '/index.html':
            self._send_html(HTML)
            return

        if path == '/api/search':
            kw = qs.get('kw',[''])[0]
            if not kw:
                self._send_json({'songs':[]})
                return
            try:
                songs = kugou_spider.search_songs(kw, page=1, pagesize=20)
                result = []
                for s in songs:
                    result.append({
                        'name': s['name'],
                        'singer': s['singer'],
                        'hash': s['hash'],
                        'album_id': s.get('album_id','')
                    })
                self._send_json({'songs': result})
            except Exception as e:
                self._send_json({'error': str(e)}, 500)
            return

        if path == '/api/download':
            hash_val = qs.get('hash',[''])[0]
            album_id = qs.get('album_id',[''])[0]
            name = qs.get('name',['unknown'])[0]
            singer = qs.get('singer',['unknown'])[0]
            try:
                info = kugou_spider.get_play_info(hash_val)
                play_url = info.get('play_url','')
                if not play_url:
                    self._send_json({'ok': False, 'reason': '付费歌曲'})
                    return
                filename = f"{singer} - {name}"
                filepath = kugou_spider.download_song(play_url, filename)
                self._send_json({'ok': True, 'filename': os.path.basename(filepath), 'path': filepath})
            except Exception as e:
                self._send_json({'ok': False, 'reason': str(e)})
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        pass  # 关闭日志

def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return '127.0.0.1'

if __name__ == '__main__':
    port = 8899
    ip = get_local_ip()
    print(f"\n  酷狗音乐 Web 服务已启动")
    print(f"  电脑访问: http://localhost:{port}")
    print(f"  手机访问: http://{ip}:{port}")
    print(f"  按 Ctrl+C 停止\n")
    server = HTTPServer(('0.0.0.0', port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        print("\n  服务已停止")
