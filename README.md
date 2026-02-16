# ![io github p7mextractor](https://github.com/user-attachments/assets/2615b8fa-e16a-4936-9284-ce463cce1ddc) P7M Extractor
User friendly GTK utility to extract PDF documents from signed P7M files

## Development

Based on https://github.com/saikrishnamallam/P7MConverterApp and developed using AI and basic python and flatpak knowledge. I would be thankful if anyone interested in the app wants to contribute and/or help clean the code.. Since it's "vibe-coded" I can imagine it may be quite bloated.. I just needed an app to extract PDF from P7M offline, and it does its job.

## Features
- GTK4
- Batch conversion of P7M files to PDF
- Single files and folder selection interface
- Drag and drop single files or folders
- Real-time conversion progress tracking
- File listing with scrollable view
- User-friendly GUI with status updates
- Output folder selection interface

## Languages
English, Italian

## Screenshots
<img width="650" height="450" alt="immagine" src="https://github.com/user-attachments/assets/e09bd5e3-1e3b-403e-82bb-e9c47d847fae" />
<img width="650" height="450" alt="immagine" src="https://codeberg.org/magnogna/magnognamediarepo/raw/commit/04344a91b8279e1af2219c5a60ce163236e35088/P7M_Exporter.gif" />

## Flatpak
Runtime: org.gnome.Platform (Version 49)

SDK: org.gnome.Sdk

Permissions:
  - --socket=fallback-x11
  - --socket=wayland
  - --device=dri
  - --share=ipc
  - --filesystem=xdg-run/dconf
  - --filesystem=~/.config/dconf:ro
  - --talk-name=ca.desrt.dconf
  - --env=DCONF_USER_CONFIG_DIR=.config/dconf
  - --filesystem=xdg-config/gtk-3.0:ro
  - --filesystem=xdg-config/gtk-4.0:ro

Download the flatpak from the releases page and install it by running:
```bash
flatpak --user install p7mextractor.flatpak
```

## Build Flatpak

Runtime: org.gnome.Platform (Version 49)
SDK: org.gnome.Sdk

1. Install required packages
```bash
flatpak-builder openssl
```

2. Install required flatpak runtimes
```bash
flatpak install org.gnome.Sdk//49 org.gnome.Platform//49
```

3. Clone this repository:
```bash
git clone https://github.com/magnogna/p7mextractor.git
cd p7mextractor
```

4. Build and install the flatpak
```bash
flatpak-builder --repo=repo --force-clean build_dir io.github.p7mextractor.yml
flatpak-builder --user --install --force-clean build_dir io.github.p7mextractor.yml
```
## Python

1. Install required packages
```bash
python3 openssl
```
2. Clone this repository:
```bash
git clone https://github.com/magnogna/p7mextractor.git
cd p7mextractor
```

3. Create a virtual environment
```bash
python -m venv env
```

4. Install required packages using pip:
```bash
pip install PyGObject
```

5. Run the application
```bash
python p7mextractor.py
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- The icon has been designed starting from Mibea's amazing Hatter icon pack https://github.com/Mibea/Hatter.git
