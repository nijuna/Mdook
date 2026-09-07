import { Notice } from "obsidian";
import { ConversionProgress } from "./types";

export class StatusBarManager {
  private el: HTMLElement;
  private currentBookName = "";
  private currentProgress: ConversionProgress | null = null;
  private isActive = false;

  constructor(el: HTMLElement) {
    this.el = el;
    this.el.addClass("mdook-status-bar");
    this.el.onClickEvent(() => {
      if (this.isActive && this.currentProgress) {
        new Notice(
          `Mdook Converting: ${this.currentBookName}\n${this.currentProgress.stageName} (${this.currentProgress.percentage}%)\n${this.currentProgress.detail}`
        );
      }
    });
    this.hide();
  }

  start(bookName: string): void {
    this.isActive = true;
    this.currentBookName = bookName;
    this.currentProgress = null;
    this.el.empty();
    this.el.createSpan({ text: "📖", cls: "mdook-status-bar-icon" });
    this.el.createSpan({ text: ` Mdook: Converting ${bookName}...` });
    this.el.show();
  }

  update(progress: ConversionProgress): void {
    if (!this.isActive) return;
    this.currentProgress = progress;
    this.el.empty();
    this.el.createSpan({ text: "⚡", cls: "mdook-status-spinner" });
    this.el.createSpan({
      text: ` Mdook: ${this.currentBookName} [${progress.percentage}%]`,
    });
    this.el.setAttr(
      "title",
      `${progress.stageName} (${progress.percentage}%)\n${progress.detail}`
    );
  }

  finish(success: boolean, message: string): void {
    this.el.empty();
    if (success) {
      this.el.createSpan({ text: "✓", cls: "mdook-status-bar-icon" });
      this.el.createSpan({ text: ` Mdook: ${this.currentBookName} ready` });
    } else {
      this.el.createSpan({ text: "✗", cls: "mdook-status-bar-icon" });
      this.el.createSpan({ text: ` Mdook: ${this.currentBookName} failed` });
    }

    // Auto-hide after 5 seconds
    setTimeout(() => {
      this.hide();
    }, 5000);
  }

  hide(): void {
    this.isActive = false;
    this.currentBookName = "";
    this.currentProgress = null;
    this.el.empty();
    this.el.hide();
  }
}
