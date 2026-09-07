# Mdook Obsidian Plugin

The official desktop companion plugin for [Mdook](https://github.com/nijuna/Mdook) — bringing multi-format book conversion directly into Obsidian.

Convert `.pdf`, `.epub`, and `.docx` books into structured, readable Obsidian vaults without leaving your personal knowledge base.

---

## Features

- **In-Vault Book Conversion**: Right-click any `.pdf`, `.epub`, or `.docx` file in your file explorer to convert it into an interconnected book note hierarchy.
- **Folder Batch Processing**: Right-click any folder containing books to batch convert all of them with live queue progress.
- **Custom Destination Picker**: Choose where converted books should be created (default `Books/`, or customize per book).
- **Non-Destructive**: Original book files always remain untouched in your vault.
- **Profile Selection**: Auto-detect, Literature, or Technical profiles.
- **AI Structure Review**: Optional OpenAI-compatible LLM review for heading hierarchies.
- **Live Status Bar Feedback**: Real-time progress percentage and stage indicators while you work.
- **Auto-Open Index**: Automatically opens the generated Index note once conversion finishes.

---

## Prerequisites

The plugin requires the `mdook` CLI tool to be installed on your machine.

Install `mdook` using `uv` (recommended) or `pip`:

```bash
# Using uv (recommended)
uv tool install mdook

# Or using pip
pip install mdook
```

Verify your installation in terminal:
```bash
mdook version
```

---

## Installation

### Manual Installation (Development / Direct)

1. Open your Obsidian vault.
2. Navigate to `<Vault>/.obsidian/plugins/`.
3. Create a folder named `mdook`.
4. Copy the following files from this repository into that folder:
   - `main.js`
   - `manifest.json`
   - `styles.css`
5. In Obsidian, go to **Settings** $\rightarrow$ **Community Plugins** $\rightarrow$ Click **Reload plugins**.
6. Toggle **Mdook Book Importer** ON.

---

## Usage

### 1. Convert an Individual Book
1. In the Obsidian File Explorer, right-click any `.pdf`, `.epub`, or `.docx` file.
2. Select **Mdook: Convert to Book Notes**.
3. Watch the progress in the bottom status bar (`⚡ Mdook: [Title] [65%]`).
4. When finished, Obsidian automatically opens the book's Index note!

### 2. Convert with Custom Options
1. Right-click the file $\rightarrow$ **Mdook Options...** (or click the **Mdook Ribbon Icon** on the left).
2. Set the destination folder, choose a specific profile, or toggle AI structure review.
3. Click **Convert**.

### 3. Batch Convert a Folder of Books
1. Put one or more book files into a folder (e.g. `_inbox/` or `Library/`).
2. Right-click the folder $\rightarrow$ **Mdook: Convert N Books in Folder...**.
3. Review the detected books and click **Convert**.

---

## Settings

In Obsidian under **Settings** $\rightarrow$ **Mdook Book Importer**:

- **Mdook Executable Path**: Custom path to `mdook` binary (or auto-detected from `$PATH`).
- **Test Connection**: Click to verify that Obsidian can communicate with the `mdook` CLI.
- **Default Output Folder**: Folder where converted books are saved (default: `Books`).
- **Prompt for Destination Folder**: Whether to prompt for output folder on every conversion.
- **Default Profile**: `Auto-Detect`, `Literature`, or `Technical`.
- **Open Index Note Automatically**: Toggle whether to open the book index after conversion.
- **AI Structure Review**: Configure endpoint, model, and API key for outline review.

---

## Development & Building

```bash
cd obsidian-plugin

# Install dependencies
npm install

# Build production bundle
npm run build

# Watch mode for development
npm run dev
```

---

## License

MIT License. Copyright (c) 2026 Mdook Team.
