<div align="center">

# Project Codename

[🇧🇷 Português (Brasil)](README.md) · **🇺🇸 English**

### Prepare videos quickly for any destination.

Convert, compress, optimize and share — all with a few clicks and 100% local processing.

<br />

![Beta](https://img.shields.io/badge/status-Beta-007AFF?style=for-the-badge)
![Open Source](https://img.shields.io/badge/Open%20Source-yes-34C759?style=for-the-badge)
![License](https://img.shields.io/badge/license-to%20be%20defined-8E8E93?style=for-the-badge)

![Windows](https://img.shields.io/badge/Windows-supported-2F80ED?style=for-the-badge&logo=windows)
![macOS](https://img.shields.io/badge/macOS-supported-111827?style=for-the-badge&logo=apple)
![Android](https://img.shields.io/badge/Android-in%20development-34A853?style=for-the-badge&logo=android)
![iOS](https://img.shields.io/badge/iOS-planned-8E8E93?style=for-the-badge&logo=apple)

![FFmpeg](https://img.shields.io/badge/FFmpeg-powered-007808?style=for-the-badge&logo=ffmpeg)
![Python](https://img.shields.io/badge/Python-Desktop-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flutter](https://img.shields.io/badge/Flutter-Mobile-02569B?style=for-the-badge&logo=flutter&logoColor=white)
![Media3](https://img.shields.io/badge/Media3-Android-EA4335?style=for-the-badge&logo=android&logoColor=white)

<br />

[About](#about-the-project) · [Features](#features) · [Roadmap](#roadmap) · [Installation](#installation) · [Contributing](#contributing)

</div>

---

## Table of Contents

- [About the Project](#about-the-project)
- [Project Philosophy](#project-philosophy)
- [Naming](#naming)
- [Status](#status)
- [Features](#features)
- [Roadmap](#roadmap)
- [Our Vision](#our-vision)
- [Screenshots](#screenshots)
- [Demo GIF](#demo-gif)
- [Technologies](#technologies)
- [Installation](#installation)
- [Project Structure](#project-structure)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [Open Source](#open-source)
- [Changelog](#changelog)
- [License](#license)
- [Acknowledgements](#acknowledgements)

## About the Project

**Project Codename** started as a simple tool to reduce video file sizes, but the project vision goes beyond compression.

The goal is not to be just another video compressor. The goal is to build a tool that helps people **prepare videos quickly for any destination**:

- convert;
- compress;
- optimize;
- prepare;
- share.

All with just a few clicks, local processing and an interface that stays out of the way.

> [!IMPORTANT]
> This project is under active development and is currently in **Beta**. Features, interface and structure may evolve significantly before a stable release.

## Project Philosophy

This software was born from real everyday problems.

We want a simple tool. We do not want to compete with large video editors. We want anyone to prepare a video in a few seconds without needing to understand codecs, presets, formats, bitrate or advanced settings.

The priority is a fast, clear and trustworthy experience:

- no mandatory upload;
- no unnecessary complexity;
- no heavy workflow for a simple task;
- enough control for users who need to fine-tune the output.

## Naming

The project started as a personal idea and does not have a final name yet.

For now, we use **Project Codename** as a temporary name. Suggestions are very welcome, and the community will be invited to help choose the final name.

If you have a name idea that communicates simplicity, speed and smart video preparation, please open a discussion or issue once the public repository is available.

## Status

| Platform | Status | Notes |
| --- | --- | --- |
| Desktop | ✔ Functional Beta | Python app with a CustomTkinter interface |
| Windows | ✔ Supported | `.exe` packaging planned with PyInstaller |
| macOS | ✔ Supported | Local execution and `.app` packaging planned |
| Linux | 🚧 Future | Possible support after stabilization |
| Android | 🚧 In development | Mobile app built with Flutter |
| iOS | ❌ Planned | No public implementation yet |

## Features

| Feature | Desktop | Android | iOS |
| --- | :---: | :---: | :---: |
| Convert any video to MP4 | ✔ | 🚧 | ❌ |
| Video compression | ✔ | 🚧 | ❌ |
| Quality profiles | ✔ | 🚧 | ❌ |
| Resolution changes | ✔ | 🚧 | ❌ |
| Rotation | ✔ | 🚧 | ❌ |
| Remove audio | ✔ | 🚧 | ❌ |
| Audio extraction | ✔ | 🚧 | ❌ |
| Blur regions in video | ✔ | 🚧 | ❌ |
| Quick cut / clip splitting | ✔ | 🚧 | ❌ |
| Multiple videos in the timeline | ✔ | 🚧 | ❌ |
| Quick sharing | ❌ | 🚧 | ❌ |
| Receive videos from the system Share menu | ❌ | 🚧 | ❌ |
| Local processing | ✔ | 🚧 | ❌ |
| No cloud upload | ✔ | 🚧 | ❌ |

Legend: ✔ available · 🚧 in development · ❌ unavailable

## Roadmap

### Beta

- ✔ Functional Desktop app
- ✔ MP4 compression
- ✔ Quality profiles
- ✔ Resolution changes
- ✔ Rotation
- ✔ Audio removal and extraction
- ✔ Timeline with real segments
- ✔ Temporal blur
- 🚧 Android
- 🚧 UI/UX improvements
- 🚧 Simpler packaging for end users

### Upcoming versions

- Batch compression
- Better final-size estimation
- Smart destination presets
- Direct sharing
- Receive videos from the system Share menu
- Better input codec compatibility
- Better mobile experience
- iOS version
- Technical documentation for contributors

## Our Vision

This project is not meant to grow alone.

We want to learn with the community, receive suggestions, discuss ideas and build something genuinely useful. The goal is to solve a common problem in a simple, transparent and pleasant way.

If you have ever needed to reduce a video for messaging, prepare a file for social media, fix rotation, remove audio or turn a huge video into something shareable, this project is for you.

## Screenshots

> [!NOTE]
> This section is ready for official interface screenshots.

| Desktop | Mobile |
| --- | --- |
| `screenshots/desktop-home.png` | `screenshots/mobile-home.png` |
| `screenshots/desktop-editor.png` | `screenshots/mobile-processing.png` |

## Demo GIF

> Demo GIF coming soon.

```text
assets/demo/demo.gif
```

## Technologies

### Desktop

- Python
- Tkinter / CustomTkinter
- FFmpeg
- FFprobe
- PyInstaller for packaging

### Mobile

- Flutter
- Android
- Media3
- iOS planned

## Installation

### Desktop

#### Requirements

- Python 3.11 or newer recommended
- FFmpeg and FFprobe installed on the system
- Python dependencies from `requirements.txt`

#### macOS

```bash
brew install ffmpeg
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

#### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

FFmpeg can be installed with Chocolatey:

```powershell
choco install ffmpeg
```

Or manually from the official website:

```text
https://ffmpeg.org/download.html
```

#### Linux

> [!NOTE]
> Linux support is not a priority during the Beta phase, but the Python/FFmpeg foundation should work on many distributions.

Ubuntu/Debian:

```bash
sudo apt update
sudo apt install ffmpeg
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

## Project Structure

```text
.
├── main.py                  # Desktop app entry point
├── ui.py                    # Desktop interface
├── compressor.py            # FFmpeg/FFprobe integration
├── editor_state.py          # Temporal editor state
├── editor_timeline.py       # Desktop editor timeline
├── video_preview.py         # Video preview
├── video_filters.py         # Video filter construction
├── blur_state.py            # Shared blur state
├── utils.py                 # General utilities
├── requirements.txt         # Python dependencies
├── mobile_app/              # Flutter mobile project
├── ROADMAP_MOBILE.md        # Mobile roadmap
├── TESTES.md                # Test notes
├── EMPACOTAMENTO.md         # Packaging notes
├── README.md                # Main documentation in PT-BR
└── README_EN.md             # English documentation
```

## Documentation

- [Roadmap](ROADMAP_MOBILE.md)
- [Issues](../../issues)
- [Releases](../../releases)
- [Wiki](../../wiki)
- [Tests](TESTES.md)
- [Packaging](EMPACOTAMENTO.md)

> [!TIP]
> Some links depend on the repository being published on GitHub.

## Contributing

Contributions are welcome.

You can help with:

- code;
- documentation;
- translation;
- design;
- UX;
- testing;
- ideas;
- bugs;
- suggestions.

Before proposing large changes, please open an issue or discussion so we can align on direction. We want to keep the project simple, organized and useful.

## Open Source

We believe sharing knowledge strengthens the whole community.

In a time shaped by AI, we want to collaborate more than compete. This project aims to be a place to learn, build and improve a real tool transparently.

Every contribution will be reviewed carefully. The focus is to preserve quality, consistency and organization while keeping the project open to collaboration.

## Changelog

The official changelog will be published soon.

```text
CHANGELOG.md
```

## License

To be defined.

## Acknowledgements

Thank you to the people, projects and communities that make this work possible:

- Open Source community
- FFmpeg
- Flutter
- Python
- CustomTkinter
- Current and future contributors

---

Built by people who enjoy turning small tools into genuinely useful solutions.
