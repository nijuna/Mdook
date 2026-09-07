import { App, Modal, Setting, TFile, Notice } from "obsidian";
import type MdookPlugin from "./main";
import { ProfileType, ConversionOptions, ConversionProgress } from "./types";

export interface ConversionModalOptions {
  file: TFile;
  defaultProfile?: ProfileType;
  defaultOutputFolder?: string;
  onConvert?: (options: ConversionOptions) => Promise<void>;
}

export class ConversionModal extends Modal {
  private plugin: MdookPlugin;
  private file: TFile;
  private selectedProfile: ProfileType;
  private outputFolder: string;
  private enableAi: boolean;

  private isRunning = false;
  private progressBarEl: HTMLElement | null = null;
  private progressTextEl: HTMLElement | null = null;
  private convertBtnEl: HTMLButtonElement | null = null;

  constructor(app: App, plugin: MdookPlugin, options: ConversionModalOptions) {
    super(app);
    this.plugin = plugin;
    this.file = options.file;
    this.selectedProfile = options.defaultProfile || plugin.settings.defaultProfile;
    this.outputFolder = options.defaultOutputFolder || plugin.settings.defaultOutputFolder;
    this.enableAi = plugin.settings.enableAiReview;
  }

  onOpen() {
    const { contentEl } = this;
    contentEl.empty();
    contentEl.addClass("mdook-modal");

    contentEl.createEl("h2", {
      text: "Convert Book with Mdook",
      cls: "mdook-modal-title",
    });

    contentEl.createEl("p", {
      text: `Source Book: ${this.file.name} (${this.file.extension.toUpperCase()})`,
      cls: "setting-item-description",
    });

    // 1. Output Folder
    new Setting(contentEl)
      .setName("Destination Folder")
      .setDesc("Vault folder where the converted book note structure will be created.")
      .addText((text) =>
        text
          .setPlaceholder("Books")
          .setValue(this.outputFolder)
          .onChange((value) => {
            this.outputFolder = value.trim() || "Books";
          })
      );

    // 2. Profile Selection
    new Setting(contentEl)
      .setName("Profile")
      .setDesc("Typography and layout heuristic model.")
      .addDropdown((drop) =>
        drop
          .addOption("auto", "Auto-Detect (Recommended)")
          .addOption("literature", "Literature (Fiction, Essays)")
          .addOption("technical", "Technical (Textbooks, Math, Code)")
          .setValue(this.selectedProfile)
          .onChange((val) => {
            this.selectedProfile = val as ProfileType;
          })
      );

    // 3. AI Review
    new Setting(contentEl)
      .setName("AI Structure Review")
      .setDesc("Use LLM reviewer to audit heading candidate levels.")
      .addToggle((toggle) =>
        toggle.setValue(this.enableAi).onChange((val) => {
          this.enableAi = val;
        })
      );

    // 4. Live Progress Area (hidden initially)
    const progressContainer = contentEl.createDiv({
      cls: "mdook-progress-container",
    });
    progressContainer.style.display = "none";

    this.progressBarEl = progressContainer.createDiv({
      cls: "mdook-progress-bar",
    });

    this.progressTextEl = contentEl.createDiv({
      cls: "mdook-progress-text",
    });
    this.progressTextEl.style.display = "none";

    // 5. Action Buttons
    const actionSetting = new Setting(contentEl);
    actionSetting.addButton((btn) => {
      btn
        .setButtonText("Convert")
        .setCta()
        .onClick(async () => {
          if (this.isRunning) return;
          this.isRunning = true;
          this.convertBtnEl = btn.buttonEl;
          btn.setDisabled(true);
          btn.setButtonText("Converting...");

          progressContainer.style.display = "block";
          if (this.progressTextEl) {
            this.progressTextEl.style.display = "block";
            this.progressTextEl.setText("Initializing conversion...");
          }

          try {
            await this.plugin.startBookConversion(
              this.file,
              this.outputFolder,
              this.selectedProfile,
              this.enableAi,
              (progress) => {
                this.updateProgress(progress);
              }
            );
            this.close();
          } catch (err: any) {
            this.isRunning = false;
            btn.setDisabled(false);
            btn.setButtonText("Convert");
            new Notice(`Conversion error: ${err.message || err}`);
            if (this.progressTextEl) {
              this.progressTextEl.setText(`Error: ${err.message || err}`);
            }
          }
        });
    });

    actionSetting.addButton((btn) => {
      btn.setButtonText("Cancel").onClick(() => {
        this.close();
      });
    });
  }

  updateProgress(progress: ConversionProgress) {
    if (this.progressBarEl) {
      this.progressBarEl.style.width = `${progress.percentage}%`;
    }
    if (this.progressTextEl) {
      this.progressTextEl.setText(
        `${progress.stageName} (${progress.percentage}%)\n${progress.detail}`
      );
    }
  }

  onClose() {
    const { contentEl } = this;
    contentEl.empty();
  }
}
