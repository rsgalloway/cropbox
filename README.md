# Cropbox

A lightweight desktop utility for trimming, cropping, previewing, and exporting video and GIF media.

![CropBox screenshot](cropbox.png)

## Features

- MP4, MOV, MKV, WebM, and GIF preview
- Interactive crop overlay with draggable edges and handles
- Timeline trim in/out selection
- Exact trim-in and trim-out entry by timecode or frame number
- Frame stepping and trim-handle nudging from the keyboard
- Playback speed control for preview and export
- FFmpeg export to MP4, MOV, and GIF
- CLI startup options for media, trim, and crop values
- Python 3.8–3.12
- PySide6 desktop UI

## Requirements

- Python 3.8 through 3.12
- `ffmpeg`
- `ffprobe`

CropBox checks for `ffmpeg` and `ffprobe` on startup and provides install guidance from `Help -> Install FFmpeg`.

Typical install on Ubuntu/Debian:

```bash
sudo apt install ffmpeg
```

## Controls

- Space: play/pause
- Left/Right: step one frame
- Shift+Left/Right: nudge selected trim handle by one frame

## Menus

- File: Open, Export, Quit
- Edit: Set Trim In, Set Trim Out, Reset Trim, Create Crop, Reset Crop, Playback Speed, Loop Playback
- Help: Install FFmpeg, About Cropbox

## Install

```bash
pip install .
```

## Run

```bash
cropbox
```

Open media immediately:

```bash
cropbox input.mp4
```

Open with initial trim and crop values:

```bash
cropbox input.mp4 --trim-in 12.5 --trim-out 00:00:20.000 --crop 100 50 1280 720
```

## CLI Options

- `--trim-in`: initial trim-in time in seconds or `HH:MM:SS.mmm`
- `--trim-out`: initial trim-out time in seconds or `HH:MM:SS.mmm`
- `--crop X Y WIDTH HEIGHT`: initial crop rectangle in source pixels

## Notes

- Playback speed affects both preview and export.
- Exact trim-in and trim-out values can also be entered from the Edit menu.
