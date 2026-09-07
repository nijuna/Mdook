import { App, Modal, Setting, TFile, TFolder, Notice } from "obsidian";
import type MdookPlugin from "./main";
import { ProfileType, ConversionProgress } from "./types";

export class BatchConversionModal extends Modal {
  private plugin: MdookPlugin;
  private folder: TFolder;
  private bookFiles: TFile[] = [];
  private selectedProfile: ProfileType;
  private outputFolder: string;
  private enableAi: boolean;

  private isRunning = false;
  private progressBarEl: HTMLElement | null = null;
  private progressTextEl: HTMLElement | null = null;

  constructor(app: App, plugin: MdookPlugin, folder: TFolder, bookFiles: TFile[]) {
    super(app);
    this.plugin = plugin;
    this.folder = folder;
    this.bookFiles = bookFiles;
    this.selectedProfile = plugin.settings.defaultProfile;
    this.outputFolder = plugin.settings.defaultOutputFolder;
    this.enableAi = plugin.settings.enableAiReview;
  }

  onOpen() {
    const { contentEl } = this;
    contentEl.empty();
    contentEl.addClass("mdook-modal");

    contentEl.createEl("h2", {
      text: "Batch Convert Books with Mdook",
      cls: "mdook-modal-title",
    });

    contentEl.createEl("p", {
      text: `Found ${this.bookFiles.length} book(s) in '${this.folder.path}':`,
      cls: "setting-item-description",
    });

    // File list preview
    const fileListEl = contentEl.createDiv({ cls: "mdook-file-list" });
    for (const f of this.bookFiles) {
      const itemEl = fileListEl.createDiv({ cls: "mdook-file-item" });
      itemEl.createSpan({ text: `📄 ${f.name}` });
      itemEl.createSpan({
        text: f.extension.toUpperCase(),
        cls: "setting-item-description",
      });
    }

    // 1. Destination Folder
    new Setting(contentEl)
      .setName("Destination Folder")
      .setDesc("Vault folder where converted book subfolders will be placed.")
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

    // 4. Progress bar
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

    // 5. Buttons
    const actionSetting = new Setting(contentEl);
    actionSetting.addButton((btn) => {
      btn
        .setButtonText(`Convert ${this.bookFiles.length} Books`)
        .setCta()
        .onClick(async () => {
          if (this.isRunning) return;
          this.isRunning = true;
          btn.setDisabled(true);
          btn.setButtonText("Processing Batch...");

          progressContainer.style.display = "block";
          if (this.progressTextEl) {
            this.progressTextEl.style.display = "block";
          }

          let succeeded = 0;
          let failed = 0;

          for (let i = 0; i < this.bookFiles.length; i++) {
            const currentFile = this.bookFiles[i];
            const overallPercent = Math.round((i / this.bookFiles.length) * 100);

            if (this.progressBarEl) {
              this.progressBarEl.style.width = `${overallPercent}%`;
            }
            if (this.progressTextEl) {
              this.progressTextEl.setText(
                `[${i + 1}/${this.bookFiles.length}] Converting: ${currentFile.name}...`
              );
            }

            try {
              await this.plugin.startBookConversion(
                currentFile,
                this.outputFolder,
                this.selectedProfile,
                this.enableAi,
                (p: ConversionProgress) => {
                  if (this.progressTextEl) {
                    this.progressTextEl.setText(
                      `[${i + 1}/${this.bookFiles.length}] ${currentFile.name}: ${p.stageName} (${p.percentage}%)`
                    );
                  }
                }
              );
              succeeded++;
            } catch (e) {
              failed++;
            }
          }

          if (this.progressBarEl) {
            this.progressBarEl.style.width = "100%";
          }
          if (this.progressTextEl) {
            this.progressTextEl.setText(
              `Batch complete! Succeeded: ${succeeded}, Failed: ${failed}`
            );
          }

          new Notice(
            `Mdook Batch: Completed ${succeeded} book(s)${failed > 0 ? `, ${failed} failed` : ""}.`
          );

          setTimeout(() => {
            this.close();
          }, 2000);
        });
    });

    actionSetting.addButton((btn) => {
      btn.setButtonText("Cancel").onClick(() => {
        this.close();
      });
    });
  }

  onClose() {
    const { contentEl } = this;
    contentEl.empty();
  }
}
