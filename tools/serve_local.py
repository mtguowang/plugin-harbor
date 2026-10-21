#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地模拟 GitHub raw —— 端到端验证 App 的插件库拉取功能。

## 用途

在没有真机、也不想真连 github.com 的情况下，验证：
  App 配地址 → 拉 index.json → 列插件 → 勾选 → 下载 .qbpkg → 校验 sha256 → 导入

## 目录映射（模拟 raw.githubusercontent.com 的路径结构）

    /<owner>/<repo>/main/index.json              → plugin-harbor/index.json
    /<owner>/<repo>/main/dist/<id>.qbpkg         → plugin-harbor/dist/<id>.qbpkg

## 用法

    python tools/serve_local.py            # 默认 8000 端口
    python tools/serve_local.py 8888       # 指定端口

然后 App 设置页填：

    http://<本机IP>:8000/mtguowang/plugin-harbor

（App 的 normalizeToRawUrl 会把非 github 的基址补上 /index.json）
"""
import http.server
import os
import socket
import socketserver
import sys
import urllib.parse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HARBOR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OWNER = "mtguowang"
REPO = "plugin-harbor"


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        prefix = "/%s/%s/main/" % (OWNER, REPO)

        if not path.startswith(prefix):
            self._send(404, b"not found", "text/plain")
            return

        rel = path[len(prefix):]
        # 防路径穿越
        if ".." in rel.split("/"):
            self._send(400, b"bad path", "text/plain")
            return

        full = os.path.join(HARBOR, *rel.split("/"))
        if not os.path.isfile(full):
            self._send(404, b"not found", "text/plain")
            return

        with open(full, "rb") as f:
            data = f.read()

        ctype = ("application/json"
                 if rel.endswith(".json") else "application/octet-stream")
        self._send(200, data, ctype)

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # 只打印请求行，便于观察 App 实际请求了什么
        print("  %s %s -> %s" % (self.command, self.path, args[1] if len(args) > 1 else ""))


def local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000

    if not os.path.isfile(os.path.join(HARBOR, "index.json")):
        print("错误: %s 下没有 index.json，先跑 tools/build_index.py" % HARBOR)
        return 1

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", port), Handler) as httpd:
        ip = local_ip()
        print("=" * 66)
        print("本地插件库已启动（模拟 GitHub raw）")
        print("=" * 66)
        print("  仓库根：%s" % HARBOR)
        print("  监听：  0.0.0.0:%d" % port)
        print()
        print("  App 设置页填（二选一）：")
        print("    http://%s:%d/%s/%s" % (ip, port, OWNER, REPO))
        print("    http://10.0.2.2:%d/%s/%s   ← Android 模拟器访问宿主机"
              % (port, OWNER, REPO))
        print()
        print("  验证地址（浏览器/curl）：")
        print("    http://127.0.0.1:%d/%s/%s/main/index.json" % (port, OWNER, REPO))
        print()
        print("  Ctrl+C 停止")
        print("=" * 66)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止")
    return 0


if __name__ == "__main__":
    sys.exit(main())
