# San7ModMaker Android 迁移方案

> 状态：规划中，暂不实施。待 Windows 版稳定后启动。

## 可行性分析

### 已确认可行的前提

- 三国群英传7 是解压包运行的，数据文件（Setting/\*.ini、Shape/\*.shp、PCK 等）可以放在 Android 文件系统中
- 游戏数据格式是标准 INI/Binary，Python 解析能力不受平台限制
- core/ 下 20 个模块全部是纯 Python，无平台依赖（除 pywebview）
- 前端 web/ 是完整单页应用，HTML/CSS/JS 可直接复用

### 唯一障碍

**pywebview 不支持 Android。** 需要替换 GUI 层。

## 技术方案

### 架构改造

```
[桌面版]                          [Android 版]
main.py                           main_android.py
  └─ pywebview (GUI)      →        └─ Flask (HTTP Server)
       └─ web/  (前端)                   └─ web/  (前端)
       └─ core/ (后端)                   └─ core/ (后端)
       └─ JS Bridge (pywebview.api)      └─ REST API (/api/*)
```

### 具体改动

| 模块 | 改动 | 行数估计 |
|------|------|----------|
| 新增 `main_android.py` | Flask 服务器 + 367 个 API 路由注册 | ~150 行 |
| 新增 `web/api_adapter.js` | `pywebview.api.xxx()` → `fetch('/api/xxx')` 适配层 | ~80 行 |
| 修改 `web/app.js` | 引入 api_adapter.js，条件加载 | ~5 行 |
| 新增 `build_android.sh` | Termux 一键安装脚本 | ~30 行 |

### 不变的部分

- `core/*` 全部 20 个模块：零改动
- `web/index.html`：零改动
- `web/style.css`：零改动
- `web/app.js`：仅 5 行改动（条件引入适配层）
- `data/*` 45 个 JSON Schema：零改动
- `main.py`（桌面版）：零改动

### 运行方式

1. 安装 Termux（F-Droid 版，非 Google Play 版）
2. `pkg install python`
3. 克隆仓库，运行 `python main_android.py`
4. 手机浏览器打开 `http://localhost:5000`
5. 游戏数据文件夹放在手机存储任意位置，通过"设置游戏目录"选择

## 限制与风险

| 限制 | 影响 | 缓解措施 |
|------|------|----------|
| 文件选择器 | Android 无原生文件对话框，需用 Termux 的 `termux-setup-storage` 授权 | 提供手动输入路径 + 自动检测常见路径 |
| 性能 | 手机 CPU 处理 PCK 解包/Shape 转换比 PC 慢 | 可接受（数据量不大） |
| 屏幕尺寸 | 桌面端 UI 在手机上太小 | 添加响应式 CSS（后续优化） |
| Termux 更新策略 | Google Play 版 Termux 已停更 | 引导用户使用 F-Droid 版 |

## 实施优先级

| 阶段 | 内容 | 预计工时 |
|------|------|----------|
| P0 | `main_android.py` + Flask 路由 | 2h |
| P1 | `api_adapter.js` 适配层 | 1h |
| P2 | Termux 安装脚本 + 文档 | 0.5h |
| P3 | 响应式 CSS 适配 | 4h |
| P4 | APK 打包（BeeWare/PyDroid） | 8h |