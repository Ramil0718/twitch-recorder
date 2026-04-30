#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from collections import deque
from datetime import datetime
from urllib.parse import urlparse

try:
    from flask import Flask, jsonify, request, render_template_string
except ImportError:
    print("Flask is not installed. Installing it now...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "flask"])
    from flask import Flask, jsonify, request, render_template_string


APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(APP_DIR, "channels.json")
RECORD_DIR = os.path.join(APP_DIR, "recordings")
PORT = 8888

os.makedirs(RECORD_DIR, exist_ok=True)

app = Flask(__name__)
procs = {}
enabled_channels = set()
current_files = {}
logs = {}


def streamlink_base_cmd():
    exe = shutil.which("streamlink")
    if exe:
        return [exe]
    if importlib.util.find_spec("streamlink"):
        return [sys.executable, "-m", "streamlink"]
    return None


def extract_name_from_url(url):
    try:
        parsed = urlparse(url)
        parts = [p for p in parsed.path.split("/") if p]
        return parts[-1].lower() if parts else None
    except Exception:
        return None


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        normalized = []
        for ch in d.get("channels", []):
            if isinstance(ch, str):
                normalized.append({"url": f"https://www.twitch.tv/{ch}", "name": ch})
            else:
                normalized.append(ch)
        d["channels"] = normalized
        return d
    return {"channels": [], "proxy": "", "quality": "best"}


def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


data = load_data()


def import_config_once():
    if os.path.exists(DATA_FILE):
        return
    yml = os.path.join(APP_DIR, "config.yml")
    if not os.path.exists(yml):
        return
    try:
        import re
        with open(yml, "r", encoding="utf-8") as f:
            content = f.read()
        urls = re.findall(r"url:\s*(https://www\.twitch\.tv/\S+)", content)
        for url in urls:
            name = extract_name_from_url(url)
            if name and not any(c["name"] == name for c in data["channels"]):
                data["channels"].append({"url": url, "name": name})
        if urls:
            save_data()
            print("Imported channels from config.yml:", ", ".join(extract_name_from_url(u) for u in urls))
    except Exception as e:
        print("Could not import config.yml:", e)


def log_append(name, msg):
    if name not in logs:
        logs[name] = deque(maxlen=300)
    logs[name].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def get_channel_info(name):
    return next((c for c in data["channels"] if c["name"] == name), None)


def build_cmd(url, proxy, quality, out_file):
    base_cmd = streamlink_base_cmd()
    if not base_cmd:
        raise FileNotFoundError("streamlink is not installed")
    cmd = list(base_cmd)
    if proxy:
        cmd += ["--https-proxy", proxy]
    cmd += [
        "--retry-streams", "30",
        "--retry-max", "0",
        url,
        quality,
        "-o", out_file,
    ]
    return cmd


def record_worker(name):
    log_append(name, f"录制任务已启动，等待 {name} 开播...")
    while name in enabled_channels:
        ch_info = get_channel_info(name)
        if not ch_info:
            log_append(name, "错误：找不到频道信息，任务已停止")
            enabled_channels.discard(name)
            procs.pop(name, None)
            current_files.pop(name, None)
            return

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_file = os.path.join(RECORD_DIR, f"{name}_{ts}.ts")
        current_files[name] = out_file
        proxy = data.get("proxy", "").strip()
        quality = data.get("quality", "best").strip() or "best"

        try:
            cmd = build_cmd(ch_info["url"], proxy, quality, out_file)
            log_append(name, "检测直播状态...")
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            if name not in enabled_channels:
                kill_process_tree(proc)
                break
            procs[name] = proc
            for line in proc.stdout:
                if name not in enabled_channels:
                    kill_process_tree(proc)
                    break
                line = line.strip()
                if line:
                    log_append(name, line)
            proc.wait()
        except FileNotFoundError:
            log_append(name, "错误：找不到 Streamlink。请运行 install_deps.cmd 或执行 python -m pip install streamlink")
            enabled_channels.discard(name)
            procs.pop(name, None)
            current_files.pop(name, None)
            return
        except Exception as e:
            log_append(name, f"异常：{e}")

        procs.pop(name, None)
        if name not in enabled_channels:
            break

        log_append(name, "本次检测/录制结束，60 秒后重新检测...")
        for _ in range(60):
            if name not in enabled_channels:
                break
            time.sleep(1)

    procs.pop(name, None)
    current_files.pop(name, None)
    log_append(name, "录制任务已停止")


def start_recording(name):
    if name in enabled_channels:
        return
    enabled_channels.add(name)
    procs[name] = None
    threading.Thread(target=record_worker, args=(name,), daemon=True).start()


def kill_process_tree(proc):
    if not proc or proc.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=8,
            )
        except Exception:
            proc.kill()
    else:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


def stop_recording(name):
    enabled_channels.discard(name)
    proc = procs.pop(name, None)
    kill_process_tree(proc)
    current_files.pop(name, None)
    log_append(name, "已手动停止录制")


def start_all_recordings():
    for ch in data.get("channels", []):
        name = ch.get("name")
        if name:
            start_recording(name)


def channel_runtime_state(name):
    proc = procs.get(name)
    enabled = name in enabled_channels
    process_running = bool(proc and proc.poll() is None)
    out_file = current_files.get(name)
    recording_now = bool(process_running and out_file and os.path.exists(out_file) and os.path.getsize(out_file) > 0)
    if recording_now:
        state = "recording"
    elif enabled:
        state = "listening"
    else:
        state = "stopped"
    return {
        "enabled": enabled,
        "processRunning": process_running,
        "recordingNow": recording_now,
        "state": state,
        "currentFile": out_file or "",
    }


def check_live(name):
    ch_info = get_channel_info(name)
    base_cmd = streamlink_base_cmd()
    if not ch_info or not base_cmd:
        return "unknown"
    cmd = list(base_cmd) + ["--json"]
    proxy = data.get("proxy", "").strip()
    if proxy:
        cmd += ["--https-proxy", proxy]
    cmd += [ch_info["url"], "best"]
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode == 0 and r.stdout.strip().startswith("{"):
            return "live"
        if "No playable streams" in out or "offline" in out.lower() or "No streams" in out:
            return "offline"
        return "unknown"
    except Exception:
        return "unknown"


@app.errorhandler(Exception)
def handle_error(e):
    import traceback
    traceback.print_exc()
    code = getattr(e, "code", 500)
    return jsonify(error=str(e)), code


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/data")
def api_data():
    result = []
    for ch in data["channels"]:
        name = ch["name"]
        runtime = channel_runtime_state(name)
        result.append({
            "name": name,
            "url": ch["url"],
            "recording": runtime["enabled"],
            "enabled": runtime["enabled"],
            "processRunning": runtime["processRunning"],
            "recordingNow": runtime["recordingNow"],
            "state": runtime["state"],
            "currentFile": runtime["currentFile"],
            "logs": list(logs.get(name, []))[-30:],
        })
    return jsonify(
        channels=result,
        proxy=data.get("proxy", ""),
        quality=data.get("quality", "best"),
        streamlinkReady=streamlink_base_cmd() is not None,
    )


@app.route("/api/channels", methods=["POST"])
def api_add():
    body = request.get_json(force=True, silent=True) or {}
    url = body.get("url", "").strip()
    if not url:
        return jsonify(error="请输入直播间网址"), 400
    if not url.startswith("http"):
        url = "https://" + url
    name = extract_name_from_url(url)
    if not name:
        return jsonify(error="无法从网址中解析频道名，请检查格式"), 400
    if any(c["name"] == name for c in data["channels"]):
        return jsonify(error=f"频道 {name} 已存在"), 400
    data["channels"].append({"url": url, "name": name})
    save_data()
    start_recording(name)
    return jsonify(ok=True, name=name)


@app.route("/api/channels/<ch>", methods=["DELETE"])
def api_del(ch):
    if ch in enabled_channels or ch in procs:
        stop_recording(ch)
    data["channels"] = [c for c in data["channels"] if c["name"] != ch]
    save_data()
    return jsonify(ok=True)


@app.route("/api/channels/<ch>/start", methods=["POST"])
def api_start(ch):
    if not get_channel_info(ch):
        return jsonify(error="频道不存在"), 404
    start_recording(ch)
    return jsonify(ok=True)


@app.route("/api/channels/<ch>/stop", methods=["POST"])
def api_stop(ch):
    stop_recording(ch)
    return jsonify(ok=True)


@app.route("/api/channels/<ch>/status")
def api_status(ch):
    return jsonify(status=check_live(ch))


@app.route("/api/channels/<ch>/logs")
def api_logs(ch):
    return jsonify(logs=list(logs.get(ch, [])))


@app.route("/api/settings", methods=["POST"])
def api_settings():
    body = request.get_json(force=True, silent=True) or {}
    if "proxy" in body:
        data["proxy"] = body["proxy"].strip()
    if "quality" in body:
        data["quality"] = body["quality"].strip() or "best"
    save_data()
    return jsonify(ok=True)


HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Twitch 直播录制管理</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0e0e10;color:#efeff1;min-height:100vh}
header{background:#18181b;border-bottom:1px solid #2d2d35;padding:14px 24px;display:flex;align-items:center;gap:10px}
header h1{font-size:17px;font-weight:700;color:#a970ff}
header span{font-size:12px;color:#adadb8}
.wrap{max-width:900px;margin:0 auto;padding:20px}
.card{background:#18181b;border:1px solid #2d2d35;border-radius:8px;padding:18px;margin-bottom:14px}
.card-title{font-size:12px;font-weight:700;color:#adadb8;text-transform:uppercase;letter-spacing:.6px;margin-bottom:14px}
.row{display:flex;gap:8px}
input[type=text],select{background:#0e0e10;border:1px solid #2d2d35;border-radius:6px;padding:9px 13px;color:#efeff1;font-size:13px;outline:none}
input[type=text]:focus,select:focus{border-color:#a970ff}
input.grow{flex:1}
select option{background:#18181b}
.btn{padding:9px 16px;border-radius:6px;border:none;cursor:pointer;font-size:12px;font-weight:700;white-space:nowrap}
.btn:hover{filter:brightness(1.15)}
.btn-purple{background:#a970ff;color:#fff}
.btn-green{background:#00b56a;color:#fff}
.btn-red{background:#eb0400;color:#fff}
.btn-ghost{background:transparent;border:1px solid #2d2d35;color:#adadb8}
.btn-outline{background:transparent;border:1px solid #a970ff;color:#a970ff}
.btn-sm{padding:5px 11px;font-size:11px}
.ch-item{background:#0e0e10;border:1px solid #2d2d35;border-radius:8px;margin-bottom:8px;overflow:hidden}
.ch-head{display:flex;align-items:center;gap:10px;padding:12px 14px}
.ch-info{flex:1;min-width:0}
.ch-name{font-size:14px;font-weight:700}
.ch-url{font-size:11px;color:#adadb8;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ch-actions{display:flex;gap:6px;align-items:center;flex-shrink:0}
.badge{display:inline-flex;align-items:center;gap:5px;padding:3px 9px;border-radius:4px;font-size:10px;font-weight:700;letter-spacing:.4px;flex-shrink:0}
.dot{width:6px;height:6px;border-radius:50%;background:currentColor}
.b-live{background:#eb0400;color:#fff}
.b-rec{background:#00b56a;color:#fff}
.b-off,.b-unk{background:#2d2d35;color:#adadb8}
.log-wrap{border-top:1px solid #2d2d35;background:#07070a;max-height:160px;overflow-y:auto;display:none}
.log-wrap.open{display:block}
.log-line{font-family:Consolas,monospace;font-size:11px;color:#adadb8;padding:2px 14px;line-height:1.7}
.settings-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.settings-grid label{font-size:11px;color:#adadb8;display:block;margin-bottom:5px}
.hint{font-size:11px;color:#5c5c7a;margin-top:8px}
.empty{text-align:center;color:#5c5c7a;padding:28px;font-size:13px}
.toast{position:fixed;bottom:22px;right:22px;background:#18181b;border:1px solid #2d2d35;border-radius:8px;padding:11px 18px;font-size:13px;opacity:0;transition:opacity .25s;pointer-events:none}
.toast.show{opacity:1}
.toast.ok{border-color:#00b56a;color:#00d47a}
.toast.err{border-color:#eb0400;color:#ff6b6b}
.refresh-ts{font-size:11px;color:#5c5c7a;text-align:right;margin-bottom:10px}
.warning{border-color:#eb0400;color:#ffb4b4;display:none}
@media(max-width:760px){.row,.settings-grid,.ch-head{display:block}.ch-actions{margin-top:10px;flex-wrap:wrap}.badge{margin-top:8px}}
</style>
</head>
<body>
<header>
  <h1>Twitch 直播录制管理</h1>
  <span>自动检测开播 · 一键录制</span>
</header>
<div class="wrap">
  <div class="card warning" id="depWarn">未检测到 Streamlink。请在服务器运行 install_deps.cmd，或执行 python -m pip install streamlink。</div>
  <div class="card">
    <div class="card-title">添加直播间</div>
    <div class="row">
      <input class="grow" type="text" id="newUrl" placeholder="https://www.twitch.tv/spicyuuu">
      <button class="btn btn-purple" onclick="addChannel()">添加</button>
    </div>
  </div>
  <div class="card">
    <div class="card-title">频道列表</div>
    <div class="refresh-ts" id="ts">加载中...</div>
    <div id="list"><div class="empty">暂无频道，请先添加</div></div>
  </div>
  <div class="card">
    <div class="card-title">设置</div>
    <div class="settings-grid">
      <div>
        <label>代理地址（可选）</label>
        <input type="text" id="proxy" placeholder="http://127.0.0.1:7890" style="width:100%">
      </div>
      <div>
        <label>录制画质</label>
        <select id="quality" style="width:100%">
          <option value="best">最高 best</option>
          <option value="1080p60">1080p60</option>
          <option value="720p60">720p60</option>
          <option value="720p">720p</option>
          <option value="480p">480p</option>
          <option value="worst">最低 worst</option>
        </select>
      </div>
    </div>
    <p class="hint">修改设置后点击保存；正在录制的频道下次重启任务后生效。</p>
    <div style="margin-top:12px"><button class="btn btn-purple btn-sm" onclick="saveSettings()">保存设置</button></div>
  </div>
</div>
<div class="toast" id="toast"></div>
<script>
function $(id) {
  return document.getElementById(id);
}

function api(method, url, body, done) {
  var xhr = new XMLHttpRequest();
  if (method === 'GET') {
    url += (url.indexOf('?') >= 0 ? '&' : '?') + '_=' + new Date().getTime();
  }
  xhr.open(method, url, true);
  xhr.setRequestHeader('Content-Type', 'application/json');
  xhr.setRequestHeader('Cache-Control', 'no-cache');
  xhr.setRequestHeader('Pragma', 'no-cache');
  xhr.onreadystatechange = function () {
    if (xhr.readyState !== 4) return;
    var data = {};
    try {
      data = JSON.parse(xhr.responseText || '{}');
    } catch (e) {
      data = {error: 'Server returned invalid response: ' + (xhr.responseText || '').slice(0, 120)};
    }
    if (xhr.status >= 400 && !data.error) data.error = 'HTTP ' + xhr.status;
    done(data);
  };
  xhr.onerror = function () {
    done({error: 'Network request failed'});
  };
  xhr.send(body ? JSON.stringify(body) : null);
}

function toast(msg, type) {
  var el = $('toast');
  el.textContent = msg;
  el.className = 'toast show ' + (type || 'ok');
  setTimeout(function () { el.className = 'toast'; }, 2600);
}

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function toggleLog(ch) {
  var el = $('log_' + ch);
  if (!el) return;
  if ((' ' + el.className + ' ').indexOf(' open ') >= 0) {
    el.className = el.className.replace(/\bopen\b/g, '');
  } else {
    el.className += ' open';
    el.scrollTop = el.scrollHeight;
  }
}

function loadAll() {
  api('GET', '/api/data', null, function (d) {
    if (d.error) {
      toast('Load failed: ' + d.error, 'err');
      return;
    }
    $('depWarn').style.display = d.streamlinkReady ? 'none' : 'block';
    $('proxy').value = d.proxy || '';
    if (d.quality) $('quality').value = d.quality;

    var list = $('list');
    if (!d.channels || !d.channels.length) {
      list.innerHTML = '<div class="empty">No channels yet. Add one first.</div>';
    } else {
      var html = [];
      for (var i = 0; i < d.channels.length; i++) {
        var ch = d.channels[i];
        var name = esc(ch.name);
        var logHtml = '';
        for (var j = 0; j < ch.logs.length; j++) {
          logHtml += '<div class="log-line">' + esc(ch.logs[j]) + '</div>';
        }
        if (!logHtml) logHtml = '<div class="log-line">No logs yet</div>';
        var stateBadge = '';
        if (ch.recordingNow) {
          stateBadge = '<span class="badge b-rec"><span class="dot"></span>Recording</span>';
        } else if (ch.enabled) {
          stateBadge = '<span class="badge b-live"><span class="dot"></span>Listening</span>';
        } else {
          stateBadge = '<span class="badge b-off">Stopped</span>';
        }
        var detail = ch.recordingNow && ch.currentFile
          ? 'Writing: ' + ch.currentFile
          : (ch.enabled ? 'Waiting for stream' : 'Recorder stopped');
        var actionBtn = ch.enabled
          ? '<button class="btn btn-sm btn-red" onclick="stopRec(\'' + name + '\')">Stop</button>'
          : '<button class="btn btn-sm btn-green" onclick="startRec(\'' + name + '\')">Start</button>';
        html.push(
          '<div class="ch-item"><div class="ch-head"><div class="ch-info">' +
          '<div class="ch-name">' + name + '</div>' +
          '<div class="ch-url" title="' + esc(ch.url) + '">' + esc(ch.url) + '</div>' +
          '<div class="ch-url" title="' + esc(detail) + '">' + esc(detail) + '</div>' +
          '</div><span class="badge b-unk" id="st_' + name + '">Checking</span>' +
          stateBadge +
          '<div class="ch-actions">' +
          '<button class="btn btn-sm btn-outline" onclick="checkStatus(\'' + name + '\')">Check</button>' +
          actionBtn +
          '<button class="btn btn-sm btn-ghost" onclick="toggleLog(\'' + name + '\')">Logs</button>' +
          '<button class="btn btn-sm btn-ghost" onclick="delChannel(\'' + name + '\')">Delete</button>' +
          '</div></div><div class="log-wrap" id="log_' + name + '">' + logHtml + '</div></div>'
        );
      }
      list.innerHTML = html.join('');
      for (var k = 0; k < d.channels.length; k++) checkStatus(d.channels[k].name);
    }
    $('ts').textContent = 'Last refresh: ' + new Date().toLocaleTimeString();
  });
}

function checkStatus(ch) {
  var el = $('st_' + ch);
  if (!el) return;
  el.className = 'badge b-unk';
  el.textContent = 'Checking';
  api('GET', '/api/channels/' + encodeURIComponent(ch) + '/status', null, function (d) {
    if (d.status === 'live') {
      el.className = 'badge b-live';
      el.innerHTML = '<span class="dot"></span>Live';
    } else if (d.status === 'offline') {
      el.className = 'badge b-off';
      el.textContent = 'Offline';
    } else {
      el.className = 'badge b-unk';
      el.textContent = 'Unknown';
    }
  });
}

function addChannel() {
  var url = $('newUrl').value.replace(/^\s+|\s+$/g, '');
  if (!url) return;
  api('POST', '/api/channels', {url: url}, function (res) {
    if (res.error) {
      toast(res.error, 'err');
      return;
    }
    $('newUrl').value = '';
    toast('Added ' + res.name);
    loadAll();
  });
}

function delChannel(ch) {
  if (!confirm('Delete ' + ch + '?')) return;
  api('DELETE', '/api/channels/' + encodeURIComponent(ch), null, function () {
    toast('Deleted ' + ch);
    loadAll();
  });
}

function startRec(ch) {
  api('POST', '/api/channels/' + encodeURIComponent(ch) + '/start', null, function (res) {
    if (res.error) {
      toast(res.error, 'err');
      return;
    }
    toast('Started ' + ch);
    refreshPage();
  });
}

function stopRec(ch) {
  toast('Stopping ' + ch + '...');
  api('POST', '/api/channels/' + encodeURIComponent(ch) + '/stop', null, function () {
    toast('Stopped ' + ch);
    refreshPage();
  });
}

function refreshPage() {
  var base = window.location.href.split('#')[0].split('?')[0];
  window.location.replace(base + '?_=' + new Date().getTime());
}

function saveSettings() {
  api('POST', '/api/settings', {proxy: $('proxy').value.replace(/^\s+|\s+$/g, ''), quality: $('quality').value}, function (res) {
    if (res.error) toast(res.error, 'err');
    else toast('Settings saved');
  });
}

$('newUrl').onkeydown = function (e) {
  e = e || window.event;
  if (e.keyCode === 13 || e.key === 'Enter') addChannel();
};
loadAll();
setInterval(loadAll, 30000);
</script>
</body>
</html>"""


if __name__ == "__main__":
    import_config_once()
    sl_cmd = streamlink_base_cmd()
    if sl_cmd:
        print("Streamlink command:", " ".join(sl_cmd))
    else:
        print("WARNING: Streamlink is not installed. Run install_deps.cmd or: python -m pip install streamlink")

    print(f"""
Twitch recorder manager started
Local:  http://localhost:{PORT}
Server: http://<SERVER-IP>:{PORT}
Press Ctrl+C to stop
""")

    def open_default_browser():
        time.sleep(2)
        url = f"http://localhost:{PORT}"
        try:
            if os.name == "nt":
                os.startfile(url)
            else:
                webbrowser.open(url)
        except Exception as e:
            print("Could not open browser automatically:", e)
            print("Please open:", url)

    start_all_recordings()
    threading.Thread(target=open_default_browser, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
