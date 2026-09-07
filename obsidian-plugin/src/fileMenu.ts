import { Menu, TAbstractFile, TFile, TFolder } from "obsidian";
import type MdookPlugin from "./main";
import { ConversionModal } from "./conversionModal";
import { BatchConversionModal } from "./batchModal";
import { ProfileType } from "./types";

export const SUPPORTED_BOOK_EXTENSIONS = ["pdf", "epub", "docx"];

export function registerFileMenuEvents(plugin: MdookPlugin): void {
  plugin.registerEvent(
    plugin.app.workspace.on("file-menu", (menu: Menu, file: TAbstractFile) => {
      // 1. Context menu on an individual book file
      if (file instanceof TFile) {
        const ext = file.extension.toLowerCase();
        if (SUPPORTED_BOOK_EXTENSIONS.includes(ext)) {
          buildFileContextMenu(plugin, menu, file);
        }
      }

      // 2. Context menu on a folder
      if (file instanceof TFolder) {
        buildFolderContextMenu(plugin, menu, file);
      }
    })
  );
}

function buildFileContextMenu(plugin: MdookPlugin, menu: Menu, file: TFile): void {
  menu.addSeparator();

  // Primary Action
  menu.addItem((item) => {
    item
      .setTitle("Mdook: Convert to Book Notes")
      .setIcon("book-open")
      .onClick(async () => {
        if (plugin.settings.promptForOutputFolder) {
          new ConversionModal(plugin.app, plugin, { file }).open();
        } else {
          await plugin.startBookConversion(
            file,
            plugin.settings.defaultOutputFolder,
            plugin.settings.defaultProfile,
            plugin.settings.enableAiReview
          );
        }
      });
  });

  // Options Submenu
  menu.addItem((item) => {
    item
      .setTitle("Mdook Options...")
      .setIcon("sliders")
      .onClick(() => {
        new ConversionModal(plugin.app, plugin, { file }).open();
      });
  });

  menu.addSeparator();
}

function buildFolderContextMenu(plugin: MdookPlugin, menu: Menu, folder: TFolder): void {
  const bookFiles: TFile[] = [];

  function collectBooks(f: TFolder) {
    for (const child of f.children) {
      if (child instanceof TFile) {
        if (SUPPORTED_BOOK_EXTENSIONS.includes(child.extension.toLowerCase())) {
          bookFiles.push(child);
        }
      } else if (child instanceof TFolder) {
        collectBooks(child);
      }
    }
  }

  collectBooks(folder);

  if (bookFiles.length > 0) {
    menu.addSeparator();
    menu.addItem((item) => {
      item
        .setTitle(`Mdook: Convert ${bookFiles.length} Books in Folder...`)
        .setIcon("library")
        .onClick(() => {
          new BatchConversionModal(plugin.app, plugin, folder, bookFiles).open();
        });
    });
    menu.addSeparator();
  }
}
