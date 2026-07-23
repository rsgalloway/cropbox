# Cropbox

A lightweight desktop utility for trimming, cropping, previewing, and exporting video, GIF, and still-image media.

Current release: `0.2.1`

![CropBox screenshot](cropbox.png)

## Features

- MP4, MOV, MKV, WebM, GIF, PNG, JPEG, WebP, and other Qt-readable still-image preview
- Animated GIF playback with trim, frame stepping, and export to MP4, MOV, GIF, and PNG sequences
- Interactive crop overlay with draggable edges and handles
- Ctrl-drag crop handles to preserve the crop aspect ratio
- Live resize, 90° rotation, and horizontal/vertical flip previews
- Toggleable crop-coordinate and trim annotations with time or frame display
- Thumbnail-strip timeline with trim in/out selection
- Exact timeline viewport start/end for precision trimming
- Draggable gray viewport handles, wheel zoom, and frame-step navigation
- Exact trim-in and trim-out entry by timecode or frame number
- Dockable Info panel with editable playback/trim/crop values and source metadata
- Frame stepping and trim-handle nudging from the keyboard
- Playback speed control for preview and export
- Export dialog with format, size, quality, audio, and PNG sequence padding controls
- Remembered export settings and output folder
- FFmpeg export to MP4, MOV, GIF, PNG stills, and PNG sequences
- Headless CLI export with media, trim, and crop options
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
- Ctrl+I: toggle the Info panel
- Left/Right: step one frame
- Shift+Left/Right: nudge selected trim handle by one frame
- Ctrl+Left/Right: nudge selected timeline viewport handle by one frame
- Ctrl+Shift+D: open Resize
- Ctrl+Shift+L/R: rotate left/right 90°
- Ctrl+Shift+U: rotate 180° (upside down)
- Ctrl+Shift+H/V: toggle horizontal/vertical flip
- Ctrl+Shift+0: reset transforms

## Menus

- File: Open, Export, Quit
- Edit: Set Trim In, Set Trim Out, Reset Trim, Reset Timeline, Create Crop, Reset Crop, Playback Speed, Loop Playback
- Transform: Resize, Rotate Left/Right/180°, Flip Horizontal/Vertical, Reset Transform
- View: Info Panel, Show Annotations
- Help: Install FFmpeg, About Cropbox

## Install

Install the latest release from PyPI:

```bash
pip install cropbox
```

Or install from a local source checkout:

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

Open at a specific time or frame:

```bash
cropbox input.mp4 --current-time 00:00:12.500
cropbox input.mp4 --current-frame 300
```

Export directly without opening the UI:

```bash
cropbox big_buck_bunny_1080p_h264.mov -o big_buck_bunny.mp4
```

Export with trim and crop values:

```bash
cropbox input.mp4 --out output.mp4 --trim-in 12.5 --trim-out 20 --crop 100 50 1280 720
```

## CLI Options

- `-o, --out PATH`: export directly to MP4, MOV, GIF, or PNG without opening the UI
- `-f, --force`: overwrite an existing `--out` file
- `--trim-in`: initial trim-in time in seconds or `HH:MM:SS.mmm`
- `--trim-out`: initial trim-out time in seconds or `HH:MM:SS.mmm`
- `--crop X Y WIDTH HEIGHT`: initial crop rectangle in source pixels
- `--current-time`: initial current time in seconds or `HH:MM:SS.mmm` when launching the UI
- `--current-frame`: initial current frame number when launching the UI

## Notes

- Version `0.2.1` fixes GIF probing so animated GIFs open on the timed-media path instead of the still-image path.
- Playback speed affects both preview and export for timed media.
- Resize, rotation, and flip transforms are previewed live and applied to MP4, MOV, GIF, and PNG exports.
- Edit-stage resize is applied after crop; export size presets can optionally resize the transformed result again.
- Headless export defaults to the full media duration when `--trim-out` is omitted.
- Export size presets preserve the cropped aspect ratio and report the resulting dimensions.
- High, Balanced, and Smaller File presets control H.264 quality or GIF palette size.
- Exact trim-in and trim-out values can also be entered from the Edit menu.
- Press Enter in an Info panel field to apply current time/frame, playback FPS, trim, timeline viewport, or crop changes.
- Timeline Start and End zoom the visible timeline; expanding trim automatically expands the timeline viewport when needed.
- Gray viewport-handle drags preview against the current timeline and apply on mouse release.
- Mousewheel over the timeline zooms the visible range; when trim and view match, wheel zoom adjusts both together.
- Reset Timeline restores the full media duration.
- The playhead is constrained to the active trim range.
- `View -> Show Frame Values` toggles the transport and timeline labels between time and frame display.
- Still images disable playback and trim controls, but can still be cropped, transformed, and exported as PNG.
- PNG sequence export defaults to `%08d` frame padding and can be adjusted in the export dialog.
