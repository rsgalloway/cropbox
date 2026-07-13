# CropBox

A lightweight media crop and trim tool.

## MVP

- MP4/MOV/MKV/GIF playback
- Dark modern UI with central media panel
- Timeline playback bar with play button
- Timeline trimming with in/out sliders
- Crop configuration dialog
- FFmpeg export
- Python 3.8–3.12
- PySide6

## Current controls

- Space: play/pause
- Left/Right: step one frame
- Mute is enabled by default when media opens

## Menus

- File: Open, Save As..., Quit
- Edit: Set Trim In, Set Trim Out, Reset Trim, Crop...
- Help: placeholder

## Run

```bash
pip install -e .
cropbox
```