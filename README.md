# 插件港 · plugin-harbor

> 登录插件框架的**插件仓库**。App 里填这个仓库地址，就能浏览、勾选、直接导入这里的插件。

**仓库地址**（填进 App 设置页）：

```
https://github.com/mtguowang/plugin-harbor
```

---

## 一、这是什么

「登录插件框架」是一个 Android App：把逆向出来的登录协议做成**可热插拔的 JSON 插件**。

这个仓库是**插件库**，App 通过它拉取插件：

```
App 设置页填仓库地址
        ↓
拉取 index.json（插件清单）
        ↓
App 里勾选想要的插件
        ↓
下载对应 .qbpkg → 校验 sha256 → 导入
```

**公开仓库，App 不需要任何 token。**

---

## 二、目录结构

```
plugin-harbor/
├── index.json              ← ★ App 读的唯一入口（自动生成，别手改）
├── plugins/                ← 插件源文件（你编辑这里）
│   ├── ct.login/
│   │   └── manifest.json
│   ├── zto.member/
│   │   └── manifest.json
│   └── ysp.ck/
│       └── manifest.json
├── dist/                   ← 打包产物 .qbpkg（自动生成，要提交）
│   ├── ct.login.qbpkg
│   └── ...
└── tools/
    └── build_index.py      ← ★ 一键打包 + 生成索引
```

**为什么源文件是 `manifest.json` 而不是直接放 `.qbpkg`**：
- 编辑时是**可读文本**，`git diff` 清晰
- `.qbpkg` 是信封格式（多一层包装 + 转义），手改容易出错
- `build_index.py` 负责打包，你只管写 manifest

---

## 三、加一个新插件（3 步）

### 1. 建目录，放 manifest

```bash
mkdir -p plugins/my.newplugin
# 把你的 manifest.json 放进去
```

目录名建议与 `manifest.json` 里的 `id` 一致（不一致时脚本以 `id` 为准，但会提示）。

**manifest 要求**（与 App 契约一致）：
- `id` 匹配 `^[a-z0-9]+(\.[a-z0-9]+)+$`（小写数字+点，至少两段）
- `version` 匹配 `^\d+\.\d+\.\d+$`
- `name` / `allowHosts`（非空数组）/ `flow`（非空数组）/ `inputs` / `output` / `engine` 齐全
- **UTF-8 无 BOM**

### 2. 跑打包脚本

```bash
python tools/build_index.py
```

它会：
- 校验每个 manifest 的基本字段
- 打包成 `dist/<id>.qbpkg`
- 算 sha256
- 重新生成 `index.json`

看到这样就算成功：

```
  ✅ ct.login             v1.0.0     15670 B  sha256=ca0a6edf8b04…
打包完成：成功 3 个，失败 0 个
```

### 3. 提交

```bash
git add -A
git commit -m "feat: 新增 xxx 插件"
git push
```

**App 里点刷新就能看到新插件。**

---

## 四、更新已有插件

1. 改 `plugins/<id>/manifest.json`（**记得改 `version`**）
2. `python tools/build_index.py`
3. 提交推送

> **不保留历史版本**：`dist/` 里只放最新版，旧 `.qbpkg` 会被自动清掉。
> 因此 App 只能拿到最新版；要回滚就改回 manifest 再打一次。

---

## 五、index.json 字段说明

```jsonc
{
  "schemaVersion": 1,          // 索引格式版本（App 用来判断兼容性）
  "name": "插件港",             // 库名（App 里显示）
  "updatedAt": "2026-10-21T05:43:28Z",   // 生成时间（UTC）
  "plugins": [
    {
      "id": "ct.login",        // 插件 id（唯一）
      "name": "中国电信登录助手",
      "version": "1.0.0",
      "description": "...",    // 可选
      "author": "...",         // 可选
      "allowHosts": ["appgo.189.cn:9200"],   // 会访问的域名（App 展示给用户）
      "path": "dist/ct.login.qbpkg",         // 相对本仓库根的路径
      "sha256": "ca0a6edf…"    // 下载完整性校验
    }
  ]
}
```

**`sha256` 的作用**：App 下载 `.qbpkg` 后校验，防止文件损坏或被替换。脚本自动算，你不用管。

---

## 六、`.qbpkg` 信封格式

**与 App 端强绑定**（`login-plugin-framework/ui_core/lib/src/plugin_package.dart`）：

```json
{
  "qbpkg": "1.0",
  "manifest": { /* 原样 */ },
  "meta": {
    "exportedAt": "2026-10-21T05:43:28Z",
    "exportedBy": "登录插件框架",
    "note": "plugin-harbor build_index.py"
  }
}
```

> ⚠️ 改这个格式必须同步改 App 端解码，否则 App 解不开。

---

## 七、本地验证

打包完可以自己验一下 `.qbpkg` 能不能被 App 解码：

```bash
cd ../login-plugin-framework/ui_core
# 用 App 的 decodePackage 读一遍（也可直接在 App 里导入试试）
```

最直接的办法：**在 App 里配好地址 → 点插件库 → 勾选导入**，能成功就说明格式对。

---

## 八、注意事项

| 事项 | 说明 |
|---|---|
| **公开仓库** | App 无需认证。**不要放敏感信息**（真实账号、密钥）到 manifest 里 |
| **`sha256` 必填** | 脚本自动生成。手改 `index.json` 时要同步更新，否则 App 会校验失败 |
| **不要手改 `index.json`** | 它由脚本生成；手改会在下次跑脚本时被覆盖 |
| **manifest 无 BOM** | 脚本会拒；用 UTF-8 保存 |
| **插件 id 唯一** | 两个目录用同一个 id 会导致后一个覆盖前一个的 `.qbpkg` |
