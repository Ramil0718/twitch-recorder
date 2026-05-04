# Twitch Recorder Manager (Streamlink + FFmpeg)

[简体中文](https://github.com/Ramil0718/twitch-recorder/blob/main/README.zh.md)  
A small **Twitch auto-recording** tool with a web control panel (Flask). It uses [Streamlink](https://streamlink.github.io/) to fetch the stream and optionally uses FFmpeg to remux recorded segments (lossless `-c copy`).

- Web UI port: `8888`
- Output folder: `recordings/`
- Segment duration: `01:00:00` (edit `SEGMENT_DURATION` in `manager.py` if needed)

## Features

- Multi-channel management: add/remove channels, start/stop recording
- Auto polling: waits while offline and starts recording when the stream goes live
- Segmented recording: saves fixed-length segments
- Optional remuxing: `ts -> mp4/mkv/flv` via FFmpeg copy (no re-encode)
- Basic settings: HTTPS proxy, quality, output format, FFmpeg path

## Requirements

- Windows (this folder includes `start_manager.cmd` / `record.cmd`)
- Python 3 in PATH
- Python deps: see `requirements.txt`
  - `Flask`
  - `streamlink`
- FFmpeg (any one of the following):
  - Put `ffmpeg.exe` next to `manager.py` (this folder already contains `ffmpeg.exe`)
  - Or set the FFmpeg path in the Web UI
  - Or have `ffmpeg` available in PATH

## Quick Start (Web UI)

1. Install dependencies (run in this folder):

```powershell
python -m pip install -r requirements.txt
```

2. Start the manager:

```powershell
.\start_manager.cmd
```

Or:

```powershell
python manager.py
```

3. Open in a browser:

- Local: `http://localhost:8888`
- From another device on LAN: `http://<YOUR-PC-IP>:8888`

## Configuration (channels.json)

The app reads/writes `channels.json` in the same folder (saving settings in the Web UI updates it too).

Key fields:

- `channels`: list of channels, each item contains:
  - `url`: Twitch channel URL, e.g. `https://www.twitch.tv/aceu`
  - `name`: channel name (used for file naming and internal ID)
- `proxy`: optional proxy, e.g. `http://127.0.0.1:7890`
- `quality`: Streamlink quality, e.g. `best` / `1080p60` / `720p60` / `worst`
- `output_format`: `ts` / `mp4` / `mkv` / `flv`
- `ffmpeg_path`: optional, path to FFmpeg (empty means auto-detect)
- `keep_raw`: keep raw `.ts` when `output_format != ts`

## Single-Channel Script Mode (record.cmd)

If you do not need the Web UI, `record.cmd` can record one channel in a loop: it checks periodically and records when live.

1. Make sure Streamlink works:

```powershell
python -m streamlink --version
```

2. Edit the config block at the top of `record.cmd` (`CHANNEL`/`QUALITY`/`PROXY`/`CHECK_INTERVAL`), then run:

```powershell
.\record.cmd
```

Output goes to `recordings/`.

## Security Notes (Important)

This repo includes a `config.yml` that contains **example Twitch cookies** (`auth-token`, etc.). Treat them as sensitive:

- Do NOT commit your own cookies to GitHub
- If the cookies in `config.yml` are real and still valid, invalidate them by logging out/resetting sessions on Twitch
- `manager.py` only tries to import `live_rooms.url` (channel URLs) from `config.yml`; it does not read/use the cookies there

## Troubleshooting

- Streamlink not found:
  - Run `python -m pip install streamlink` or `python -m pip install -r requirements.txt`
- FFmpeg not found:
  - Ensure `ffmpeg.exe` exists in this folder, or set it in the Web UI, or add FFmpeg to PATH
- Getting `.ts` outputs:
  - Set `Output format` to `mp4/mkv/flv` in the Web UI and ensure FFmpeg is available



__all created by ai:__  
__projet created by *claude*__  
__code debug by *codex*__  

more questions:[Q&A](https://github.com/Ramil0718/twitch-recorder/blob/main/Q%26A.md)
