import {
  Plugin,
  TFile,
  Notice,
  FileSystemAdapter,
  normalizePath,
} from "obsidian";
import * as path from "path";
import { MdookPluginSettings, ProfileType, ConversionProgress } from "./types";
import { DEFAULT_SETTINGS } from "./settings";
import { MdookSettingTab } from "./settingsTab";
import { resolveMdook } from "./resolver";
import { runConversion, ProgressCallback } from "./runner";
import { StatusBarManager } from "./statusBar";
import { registerFileMenuEvents, SUPPORTED_BOOK_EXTENSIONS } from "./fileMenu";
import { ConversionModal } from "./conversionModal";

export default class MdookPlugin extends Plugin {
  settings: MdookPluginSettings = DEFAULT_SETTINGS;
  statusBar!: StatusBarManager;

  async onload() {
    await this.loadSettings();

    // 1. Status Bar
    this.statusBar = new StatusBarManager(this.addStatusBarItem());

    // 2. Settings Tab
    this.addSettingTab(new MdookSettingTab(this.app, this));

    // 3. File & Folder Context Menus
    registerFileMenuEvents(this);

    // 4. Ribbon Icon
    this.addRibbonIcon("book-open", "Mdook: Convert Book", () => {
      const activeFile = this.app.workspace.getActiveFile();
      if (
        activeFile &&
        SUPPORTED_BOOK_EXTENSIONS.includes(activeFile.extension.toLowerCase())
      ) {
        new ConversionModal(this.app, this, { file: activeFile }).open();
      } else {
        // Find any book file in vault or ask user to select one
        const allBooks = this.app.vault
          .getFiles()
          .filter((f) =>
            SUPPORTED_BOOK_EXTENSIONS.includes(f.extension.toLowerCase())
          );
        if (allBooks.length === 0) {
          new Notice(
            "No book files (.pdf, .epub, .docx) found in this vault. Add a book file to get started!"
          );
        } else {
          new ConversionModal(this.app, this, { file: allBooks[0] }).open();
        }
      }
    });

    // 5. Command Palette Actions
    this.addCommand({
      id: "mdook-convert-active-file",
      name: "Convert Active Book File",
      checkCallback: (checking: boolean) => {
        const file = this.app.workspace.getActiveFile();
        const isSupported =
          file &&
          SUPPORTED_BOOK_EXTENSIONS.includes(file.extension.toLowerCase());
        if (checking) {
          return !!isSupported;
        }
        if (file && isSupported) {
          new ConversionModal(this.app, this, { file }).open();
        }
      },
    });

    this.addCommand({
      id: "mdook-test-environment",
      name: "Check CLI Environment Health",
      callback: async () => {
        new Notice("Checking Mdook CLI status...");
        const res = await resolveMdook(this.settings.mdookPath);
        if (res.success) {
          new Notice(
            `✓ Mdook Connected!\nVersion: ${res.version}\nPath: ${res.command?.resolvedPath}`
          );
        } else {
          new Notice(`✗ Mdook CLI Error:\n${res.error}`);
        }
      },
    });
  }

  onunload() {
    this.statusBar?.hide();
  }

  async loadSettings() {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
  }

  async saveSettings() {
    await this.saveData(this.settings);
  }

  /**
   * Primary entry point to execute conversion on a TFile in the vault.
   */
  async startBookConversion(
    file: TFile,
    targetFolder: string,
    profile: ProfileType,
    enableAi = false,
    onProgress?: ProgressCallback
  ): Promise<void> {
    const adapter = this.app.vault.adapter;
    if (!(adapter instanceof FileSystemAdapter)) {
      throw new Error("Mdook requires desktop filesystem access.");
    }

    const vaultBasePath = adapter.getBasePath();
    const inputAbsolutePath = path.join(vaultBasePath, file.path);
    const outputAbsolutePath = path.join(vaultBasePath, normalizePath(targetFolder));

    // Resolve CLI
    const resolver = await resolveMdook(this.settings.mdookPath);
    if (!resolver.success || !resolver.command) {
      const err =
        resolver.error ||
        "Could not find mdook binary. Please configure the path in settings.";
      new Notice(`Mdook Error: ${err}`);
      throw new Error(err);
    }

    this.statusBar.start(file.basename);

    const progressHandler: ProgressCallback = (p) => {
      this.statusBar.update(p);
      onProgress?.(p);
    };

    const result = await runConversion(
      resolver.command,
      {
        inputPath: inputAbsolutePath,
        outputPath: outputAbsolutePath,
        profile,
        enableAiReview: enableAi,
        aiModel: this.settings.aiModel,
        aiBaseUrl: this.settings.aiBaseUrl,
        aiApiKey: this.settings.aiApiKey,
      },
      vaultBasePath,
      progressHandler
    );

    if (result.success) {
      this.statusBar.finish(true, "Done");
      new Notice(`✓ Successfully converted "${file.name}" with Mdook!`);

      // Trigger Obsidian filesystem refresh
      setTimeout(async () => {
        if (this.settings.openIndexAfterConversion && result.indexNoteVaultPath) {
          const indexFile = this.app.vault.getAbstractFileByPath(
            result.indexNoteVaultPath
          );
          if (indexFile instanceof TFile) {
            await this.app.workspace.getLeaf(true).openFile(indexFile);
          }
        }
      }, 500);
    } else {
      this.statusBar.finish(false, "Failed");
      new Notice(`✗ Failed to convert "${file.name}":\n${result.error}`, 8000);
      throw new Error(result.error || "Unknown conversion error");
    }
  }
}
