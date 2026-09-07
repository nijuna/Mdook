import { App, PluginSettingTab, Setting } from "obsidian";
import type MdookPlugin from "./main";
import { resolveMdook } from "./resolver";

export class MdookSettingTab extends PluginSettingTab {
  plugin: MdookPlugin;

  constructor(app: App, plugin: MdookPlugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();

    containerEl.createEl("h2", { text: "Mdook Book Importer Settings" });

    // --- SECTION 1: CLI Configuration & Health Check ---
    containerEl.createEl("h3", { text: "CLI Engine & Environment" });

    const cliSetting = new Setting(containerEl)
      .setName("Mdook Executable Path")
      .setDesc("Absolute path to the mdook CLI binary. Leave blank to auto-detect from PATH or uv.")
      .addText((text) =>
        text
          .setPlaceholder("Auto-detect")
          .setValue(this.plugin.settings.mdookPath)
          .onChange(async (value) => {
            this.plugin.settings.mdookPath = value;
            await this.plugin.saveSettings();
          })
      );

    cliSetting.addButton((btn) => {
      btn.setButtonText("Test Connection").onClick(async () => {
        btn.setDisabled(true);
        btn.setButtonText("Testing...");
        const result = await resolveMdook(this.plugin.settings.mdookPath);
        btn.setDisabled(false);
        btn.setButtonText("Test Connection");

        const existingBadge = containerEl.querySelector(".mdook-cli-test-result");
        if (existingBadge) existingBadge.remove();

        const badge = containerEl.createDiv({ cls: "mdook-cli-test-result" });
        if (result.success) {
          badge.addClass("mdook-badge", "mdook-badge-success");
          badge.setText(`✓ Connected: Mdook v${result.version} (${result.command?.resolvedPath})`);
        } else {
          badge.addClass("mdook-badge", "mdook-badge-error");
          badge.setText(`✗ ${result.error || "CLI executable not found"}`);
        }
      });
    });

    // --- SECTION 2: Vault Output & Organization ---
    containerEl.createEl("h3", { text: "Vault Output & Organization" });

    new Setting(containerEl)
      .setName("Default Output Folder")
      .setDesc("Folder path in your vault where converted book folders will be saved.")
      .addText((text) =>
        text
          .setPlaceholder("Books")
          .setValue(this.plugin.settings.defaultOutputFolder)
          .onChange(async (value) => {
            this.plugin.settings.defaultOutputFolder = value.trim() || "Books";
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Prompt for Destination Folder")
      .setDesc("Ask for the destination folder on each conversion instead of silently using the default.")
      .addToggle((toggle) =>
        toggle
          .setValue(this.plugin.settings.promptForOutputFolder)
          .onChange(async (value) => {
            this.plugin.settings.promptForOutputFolder = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Open Index Note Automatically")
      .setDesc("Automatically open the book's generated Index note once conversion finishes.")
      .addToggle((toggle) =>
        toggle
          .setValue(this.plugin.settings.openIndexAfterConversion)
          .onChange(async (value) => {
            this.plugin.settings.openIndexAfterConversion = value;
            await this.plugin.saveSettings();
          })
      );

    // --- SECTION 3: Conversion Defaults ---
    containerEl.createEl("h3", { text: "Conversion Defaults" });

    new Setting(containerEl)
      .setName("Default Profile")
      .setDesc("Typography and layout extraction profile to apply by default.")
      .addDropdown((drop) =>
        drop
          .addOption("auto", "Auto-Detect (Recommended)")
          .addOption("literature", "Literature (Fiction, Essays, Memoirs)")
          .addOption("technical", "Technical (Textbooks, Code, Tables)")
          .setValue(this.plugin.settings.defaultProfile)
          .onChange(async (value) => {
            this.plugin.settings.defaultProfile = value as "auto" | "literature" | "technical";
            await this.plugin.saveSettings();
          })
      );

    // --- SECTION 4: AI Structure Review (Optional) ---
    containerEl.createEl("h3", { text: "AI Structure Review (Optional)" });
    containerEl.createEl("p", {
      text: "Uses an OpenAI-compatible endpoint (Local Ollama, LM Studio, vLLM, or cloud models) to review and refine detected heading hierarchies.",
      cls: "setting-item-description",
    });

    new Setting(containerEl)
      .setName("Enable AI Review by Default")
      .setDesc("Submit detected heading candidates to an LLM reviewer during Stage 3.")
      .addToggle((toggle) =>
        toggle
          .setValue(this.plugin.settings.enableAiReview)
          .onChange(async (value) => {
            this.plugin.settings.enableAiReview = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("AI Base URL")
      .setDesc("OpenAI-compatible base URL (e.g. http://localhost:11434/v1 or https://api.openai.com/v1)")
      .addText((text) =>
        text
          .setPlaceholder("http://localhost:11434/v1")
          .setValue(this.plugin.settings.aiBaseUrl)
          .onChange(async (value) => {
            this.plugin.settings.aiBaseUrl = value.trim();
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("AI API Key")
      .setDesc("API key for cloud inference providers (leave blank for local Ollama / LM Studio).")
      .addText((text) => {
        text.inputEl.type = "password";
        text
          .setPlaceholder("sk-...")
          .setValue(this.plugin.settings.aiApiKey)
          .onChange(async (value) => {
            this.plugin.settings.aiApiKey = value.trim();
            await this.plugin.saveSettings();
          });
      });

    new Setting(containerEl)
      .setName("AI Model Name")
      .setDesc("Model identifier (e.g. gpt-4o-mini, llama3, deepseek-chat).")
      .addText((text) =>
        text
          .setPlaceholder("gpt-4o-mini")
          .setValue(this.plugin.settings.aiModel)
          .onChange(async (value) => {
            this.plugin.settings.aiModel = value.trim() || "gpt-4o-mini";
            await this.plugin.saveSettings();
          })
      );
  }
}
