export type ProfileType = "auto" | "literature" | "technical";

export interface MdookPluginSettings {
  /** Custom path to mdook binary (e.g. /usr/local/bin/mdook). If empty, auto-detected. */
  mdookPath: string;
  /** Default folder in vault where converted books will be saved (e.g. "Books") */
  defaultOutputFolder: string;
  /** Whether to prompt for output folder location on each conversion */
  promptForOutputFolder: boolean;
  /** Default profile to use: auto, literature, or technical */
  defaultProfile: ProfileType;
  /** Automatically open the generated Index note when conversion succeeds */
  openIndexAfterConversion: boolean;
  /** Enable OpenAI-compatible AI structure review */
  enableAiReview: boolean;
  /** Base URL for AI endpoint (e.g. http://localhost:11434/v1 or https://api.openai.com/v1) */
  aiBaseUrl: string;
  /** API key for AI provider (optional for local Ollama/LM Studio) */
  aiApiKey: string;
  /** Model name for AI review (e.g. gpt-4o-mini, llama3) */
  aiModel: string;
}

export interface ConversionOptions {
  /** Absolute path to source book file (.pdf, .epub, .docx) */
  inputPath: string;
  /** Absolute path to target output directory in vault */
  outputPath: string;
  /** Profile to use */
  profile: ProfileType;
  /** Optional book title override */
  title?: string;
  /** AI review toggle */
  enableAiReview?: boolean;
  /** AI review model */
  aiModel?: string;
  /** AI review base URL */
  aiBaseUrl?: string;
  /** AI review API key */
  aiApiKey?: string;
}

export interface ConversionProgress {
  stage: number;
  totalStages: number;
  stageName: string;
  percentage: number;
  detail: string;
}

export interface ConversionResult {
  success: boolean;
  outputVaultRelativePath: string;
  outputAbsolutePath: string;
  indexNoteVaultPath?: string;
  error?: string;
}
