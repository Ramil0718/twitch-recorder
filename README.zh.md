# Twitch Recorder Manager (Streamlink + FFmpeg)

一个用于 **Twitch 直播自动录制** 的小工具，带 Web 管理面板（Flask），底层使用 [Streamlink](https://streamlink.github.io/) 抓流，并可用 FFmpeg 进行无损封装转码（`-c copy`）。

- Web 管理端口：默认 `8888`
- 录制输出目录：`recordings/`
- 分段时长：默认每段 `01:00:00`（可在 `manager.py` 中修改 `SEGMENT_DURATION`）

## 功能

- 多频道管理：添加/删除频道，启停录制
- 自动轮询：主播离线时等待，开播后自动开始录制
- 分段录制：按固定时长切片保存
- 可选转码封装：`ts -> mp4/mkv/flv`（FFmpeg copy，不重新编码）
- 基础设置：代理（HTTPS proxy）、录制画质、输出格式、FFmpeg 路径

## 环境要求

- Windows（脚本内置了 `start_manager.cmd` / `record.cmd`）
- Python 3（已加入 PATH）
- 依赖：见 `requirements.txt`
  - `Flask`
  - `streamlink`
- FFmpeg（以下任意一种即可）：
  - 将 `ffmpeg.exe` 放在 `manager.py` 同目录（本目录已自带 `ffmpeg.exe`）
  - 或在 Web 设置里填写 `ffmpeg.exe` 路径
  - 或系统 PATH 中有 `ffmpeg`

## 快速开始（Web 管理面板）

1. 安装依赖（在本目录执行）：

```powershell
python -m pip install -r requirements.txt
```

2. 启动管理器：

```powershell
.\start_manager.cmd
```

或直接：

```powershell
python manager.py
```

3. 浏览器打开：

- 本机：`http://localhost:8888`
- 局域网其他设备：`http://<你的电脑IP>:8888`

## 配置说明（channels.json）

程序会在同目录读取/写入 `channels.json`（Web 面板保存设置也会写回）。

关键字段：

- `channels`: 频道列表，每项包含：
  - `url`: Twitch 频道 URL，例如 `https://www.twitch.tv/aceu`
  - `name`: 频道名（用于文件命名与内部标识）
- `proxy`: 可选代理，例如 `http://127.0.0.1:7890`
- `quality`: 录制画质，例如 `best` / `1080p60` / `720p60` / `worst`
- `output_format`: 输出格式，支持 `ts` / `mp4` / `mkv` / `flv`
- `ffmpeg_path`: 可选，FFmpeg 路径（为空则尝试自动查找）
- `keep_raw`: 可选，是否保留原始 `ts`（当 `output_format != ts` 时）

## 单频道脚本模式（record.cmd）

如果你不需要 Web 面板，也可以用 `record.cmd` 录一个频道（循环检测，开播就录）。

1. 先确认 `streamlink` 可用：

```powershell
python -m streamlink --version
```

2. 打开 `record.cmd` 修改顶部配置（`CHANNEL`/`QUALITY`/`PROXY`/`CHECK_INTERVAL`），然后运行：

```powershell
.\record.cmd
```

输出默认在 `recordings/`。

## 安全提示（非常重要）

仓库中自带的 `config.yml` **包含示例 Twitch Cookie（`auth-token` 等）**。这是敏感信息：

- 不要把自己的 Cookie 提交到 GitHub
- 如果这些 Cookie 是真实可用的，建议立刻在 Twitch 侧退出登录/重置会话以失效旧 Cookie
- 该项目的 `manager.py` 仅会从 `config.yml` 里尝试导入 `live_rooms.url`（频道地址）；不会读取/使用其中的 Cookie

## 常见问题

- 提示找不到 Streamlink：
  - 运行 `python -m pip install streamlink`，或 `python -m pip install -r requirements.txt`
- 提示找不到 FFmpeg：
  - 确认同目录有 `ffmpeg.exe`，或在 Web 设置里填写绝对路径，或把 FFmpeg 加进 PATH
- 录到的是 `.ts`：
  - 在 Web 设置里把 `Output format` 改为 `mp4/mkv/flv`，并确保 FFmpeg 可用

