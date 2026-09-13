import { MdookPluginSettings } from "./types";

export const DEFAULT_SETTINGS: MdookPluginSettings = {
  mdookPath: "",
  defaultOutputFolder: "Books",
  promptForOutputFolder: false,
  defaultProfile: "auto",
  defaultOutputMode: "vault",
  openIndexAfterConversion: true,
  enableAiReview: false,
  aiBaseUrl: "",
  aiApiKey: "",
  aiModel: "gpt-4o-mini",
};
