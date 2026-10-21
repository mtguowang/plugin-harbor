#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_index.py —— 把 plugins/*/manifest.json 打包成 dist/*.qbpkg 并生成 index.json。

## 用法

    python tools/build_index.py

在 plugin-harbor 仓库根执行（脚本会自动定位仓库根，不依赖当前目录）。

## 它做什么

1. 扫 `plugins/<id>/manifest.json`
2. 校验 manifest 基本字段（**强校验交给 App / schema/validate.py**，这里只拦明显错误）
3. 打包成 `dist/<id>.qbpkg`（**信封格式必须与 App 的 PluginPackage.encode 逐字一致**）
4. 算 sha256
5. 生成 `index.json`（按 id 排序）
6. 打印摘要

## .qbpkg 信封格式（**与 App 端强绑定，改动必须同步 App**）

App 端定义在 `login-plugin-framework/ui_core/lib/src/plugin_package.dart`：

```dart
const String kQbpkgVersion = '1.0';
const String kQbpkgExportedBy = '登录插件框架';

// encode():
{
  'qbpkg': kQbpkgVersion,
  'manifest': manifest,
  'meta': {'exportedAt': ..., 'exportedBy': ..., 'note': ...},  // 空值字段省略
}
```

解码侧识别规则：顶层含 `qbpkg` 键 → 视为信封，取 `manifest` 继续；
否则视为裸 manifest（向后兼容）。

## index.json 格式

```jsonc
{
  "schemaVersion": 1,
  "name": "插件港",
  "updatedAt": "2026-10-21T13:00:00Z",   // UTC ISO8601
  "plugins": [
    {
      "id": "ct.login",
      "name": "中国电信登录助手",
      "version": "1.0.0",
      "description": "...",     // 可选
      "author": "...",          // 可选
      "allowHosts": ["..."],
      "path": "dist/ct.login.qbpkg",
      "sha256": "..."           // 小写 hex
    }
  ]
}
```
"""
import hashlib
import io
import json
import os
import re
import sys

# Windows 控制台中文输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---- 与 App 端保持一致的常量 ------------------------------------------------
KQBPKG_VERSION = "1.0"
KQBPKG_EXPORTED_BY = "登录插件框架"
INDEX_SCHEMA_VERSION = 1
INDEX_NAME = "插件港"

# 插件 id 正则：与 CONTRACT.md §1 一致（小写数字+点，至少两段）
RE_ID = re.compile(r"^[a-z0-9]+(\.[a-z0-9]+)+$")
# 版本：semver 三段
RE_VERSION = re.compile(r"^\d+\.\d+\.\d+$")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGINS_DIR = os.path.join(ROOT, "plugins")
DIST_DIR = os.path.join(ROOT, "dist")
INDEX_PATH = os.path.join(ROOT, "index.json")


def die(msg):
    print("错误: " + msg)
    sys.exit(1)


def load_manifest(path):
    """读 manifest，返回 dict。UTF-8 严格、拒 BOM。"""
    raw = io.open(path, "rb").read()
    if raw.startswith(b"\xef\xbb\xbf"):
        die("%s 含 UTF-8 BOM（契约要求无 BOM）" % path)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        die("%s 不是合法 UTF-8: %s" % (path, e))
    try:
        obj = json.loads(text)
    except ValueError as e:
        die("%s 不是合法 JSON: %s" % (path, e))
    if not isinstance(obj, dict):
        die("%s 顶层必须是 object" % path)
    return obj


def check_manifest(m, path):
    """基本字段校验。返回错误信息列表（空 = 通过）。"""
    errs = []
    pid = m.get("id")
    if not isinstance(pid, str) or not RE_ID.match(pid):
        errs.append("id 不匹配 ^[a-z0-9]+(\\.[a-z0-9]+)+$（实际 %r）" % pid)
    ver = m.get("version")
    if not isinstance(ver, str) or not RE_VERSION.match(ver):
        errs.append("version 不匹配 ^\\d+\\.\\d+\\.\\d+$（实际 %r）" % ver)
    if not isinstance(m.get("name"), str) or not m.get("name"):
        errs.append("name 缺失或非字符串")
    hosts = m.get("allowHosts")
    if not isinstance(hosts, list) or not hosts:
        errs.append("allowHosts 必须是非空数组")
    if not isinstance(m.get("flow"), list) or not m.get("flow"):
        errs.append("flow 必须是非空数组")
    if not isinstance(m.get("inputs"), list):
        errs.append("inputs 必须是数组")
    if not isinstance(m.get("output"), dict):
        errs.append("output 必须是 object")
    if not isinstance(m.get("engine"), str):
        errs.append("engine 缺失")
    return errs


def build_qbpkg(manifest):
    """构造 .qbpkg 信封文本（与 App PluginPackage.encode 逐字对齐）。

    App 侧 `_encodeJson(..., pretty: true)` 默认 2 空格缩进 + 保留中文，
    这里用 indent=2 + ensure_ascii=False 对齐。
    """
    envelope = {
        "qbpkg": KQBPKG_VERSION,
        "manifest": manifest,
        "meta": {
            "exportedAt": _utc_now_iso(),
            "exportedBy": KQBPKG_EXPORTED_BY,
            "note": "plugin-harbor build_index.py",
        },
    }
    return json.dumps(envelope, ensure_ascii=False, indent=2)


def _utc_now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    if not os.path.isdir(PLUGINS_DIR):
        die("找不到 plugins/ 目录：%s" % PLUGINS_DIR)

    os.makedirs(DIST_DIR, exist_ok=True)

    # 清掉旧的 .qbpkg（不保留历史版本，避免 dist 里堆旧文件）
    for f in os.listdir(DIST_DIR):
        if f.endswith(".qbpkg"):
            os.remove(os.path.join(DIST_DIR, f))

    entries = []
    ok, failed = 0, []

    subdirs = sorted(
        d for d in os.listdir(PLUGINS_DIR)
        if os.path.isdir(os.path.join(PLUGINS_DIR, d))
    )
    if not subdirs:
        print("警告: plugins/ 下没有任何插件目录")

    for d in subdirs:
        mpath = os.path.join(PLUGINS_DIR, d, "manifest.json")
        if not os.path.isfile(mpath):
            failed.append((d, "缺少 manifest.json"))
            continue

        try:
            m = load_manifest(mpath)
        except SystemExit:
            raise
        except Exception as e:  # noqa: BLE001
            failed.append((d, "读取失败: %s" % e))
            continue

        errs = check_manifest(m, mpath)
        if errs:
            failed.append((d, "；".join(errs)))
            continue

        pid = m["id"]
        # 目录名与 id 不一致时以 id 为准（但给出提示，避免维护混乱）
        if d != pid:
            print("  提示: 目录名 %r 与 manifest.id %r 不一致，以 id 为准" % (d, pid))

        text = build_qbpkg(m)
        data = text.encode("utf-8")
        out_name = pid + ".qbpkg"
        out_path = os.path.join(DIST_DIR, out_name)
        with io.open(out_path, "wb") as f:
            f.write(data)

        digest = hashlib.sha256(data).hexdigest()

        entry = {
            "id": pid,
            "name": m["name"],
            "version": m["version"],
            "allowHosts": m["allowHosts"],
            "path": "dist/" + out_name,
            "sha256": digest,
        }
        if m.get("description"):
            entry["description"] = m["description"]
        if m.get("author"):
            entry["author"] = m["author"]
        entries.append(entry)
        ok += 1
        print("  ✅ %-20s v%-8s %6d B  sha256=%s…" % (pid, m["version"], len(data), digest[:12]))

    entries.sort(key=lambda e: e["id"])
    index = {
        "schemaVersion": INDEX_SCHEMA_VERSION,
        "name": INDEX_NAME,
        "updatedAt": _utc_now_iso(),
        "plugins": entries,
    }
    with io.open(INDEX_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(index, ensure_ascii=False, indent=2) + "\n")

    print()
    print("=" * 66)
    print("打包完成：成功 %d 个，失败 %d 个" % (ok, len(failed)))
    if failed:
        print()
        print("失败明细：")
        for name, why in failed:
            print("  ❌ %-20s %s" % (name, why))
    print()
    print("产物：")
    print("  dist/*.qbpkg    %d 个" % ok)
    print("  index.json      %d 个插件" % len(entries))
    print("=" * 66)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
