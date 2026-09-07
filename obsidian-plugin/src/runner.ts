import { spawn } from "child_process";
import * as path from "path";
import * as fs from "fs";
import { ConversionOptions, ConversionProgress, ConversionResult } from "./types";
import { ResolvedCommand } from "./resolver";

export type ProgressCallback = (progress: ConversionProgress) => void;

/**
 * Runs the mdook convert CLI command asynchronously with streaming progress.
 */
export function runConversion(
  command: ResolvedCommand,
  options: ConversionOptions,
  vaultBasePath: string,
  onProgress?: ProgressCallback
): Promise<ConversionResult> {
  return new Promise((resolve) => {
    const args = [
      ...command.prefixArgs,
      "convert",
      options.inputPath,
      "-o",
      options.outputPath,
      "--profile",
      options.profile,
    ];

    if (options.enableAiReview) {
      args.push("--ai");
      if (options.aiModel) {
        args.push("--ai-model", options.aiModel);
      }
      if (options.aiBaseUrl) {
        args.push("--ai-base-url", options.aiBaseUrl);
      }
      if (options.aiApiKey) {
        args.push("--ai-api-key", options.aiApiKey);
      }
    }

    let stdoutBuffer = "";
    let stderrBuffer = "";

    let currentStage = 1;
    const totalStages = 5;

    // Notify initial state
    onProgress?.({
      stage: 1,
      totalStages: 5,
      stageName: "Initializing",
      percentage: 5,
      detail: `Starting conversion for ${path.basename(options.inputPath)}...`,
    });

    const env = { ...process.env };
    // Pass API keys to env if present
    if (options.aiApiKey) {
      env["MDOOK_AI_API_KEY"] = options.aiApiKey;
    }
    if (options.aiBaseUrl) {
      env["MDOOK_AI_BASE_URL"] = options.aiBaseUrl;
    }
    if (options.aiModel) {
      env["MDOOK_AI_MODEL"] = options.aiModel;
    }

    const child = spawn(command.executable, args, {
      env,
      windowsHide: true,
    });

    child.stdout.on("data", (data: Buffer) => {
      const text = data.toString();
      stdoutBuffer += text;

      // Detect stage updates from terminal stream
      if (/Stage 1\/5|Intake/i.test(text)) {
        currentStage = 1;
        onProgress?.({
          stage: 1,
          totalStages,
          stageName: "Stage 1: Document Intake",
          percentage: 15,
          detail: "Validating file structure and reading metadata...",
        });
      } else if (/Stage 2\/5|Extraction/i.test(text)) {
        currentStage = 2;
        onProgress?.({
          stage: 2,
          totalStages,
          stageName: "Stage 2: Content Extraction",
          percentage: 35,
          detail: "Extracting text blocks, typography metrics, and images...",
        });
      } else if (/Stage 3\/5|Semantic|Heuristics/i.test(text)) {
        currentStage = 3;
        onProgress?.({
          stage: 3,
          totalStages,
          stageName: "Stage 3: Semantic Analysis",
          percentage: 60,
          detail: "Detecting chapter headings, footnotes, and callouts...",
        });
      } else if (/Stage 4\/5|Rendering|Vault/i.test(text)) {
        currentStage = 4;
        onProgress?.({
          stage: 4,
          totalStages,
          stageName: "Stage 4: Vault Rendering",
          percentage: 80,
          detail: "Generating markdown chapters and resolving cross-links...",
        });
      } else if (/Stage 5\/5|Validation/i.test(text)) {
        currentStage = 5;
        onProgress?.({
          stage: 5,
          totalStages,
          stageName: "Stage 5: Validation Audit",
          percentage: 92,
          detail: "Auditing footnote anchors and attachment integrity...",
        });
      } else if (/Parsing EPUB|Parsing Word/i.test(text)) {
        onProgress?.({
          stage: 2,
          totalStages,
          stageName: "Container Parsing",
          percentage: 40,
          detail: text.trim().slice(0, 80),
        });
      }
    });

    child.stderr.on("data", (data: Buffer) => {
      stderrBuffer += data.toString();
    });

    child.on("error", (err: Error) => {
      resolve({
        success: false,
        outputVaultRelativePath: "",
        outputAbsolutePath: options.outputPath,
        error: `Failed to execute mdook process: ${err.message}`,
      });
    });

    child.on("close", (code: number) => {
      if (code === 0) {
        onProgress?.({
          stage: 5,
          totalStages: 5,
          stageName: "Complete",
          percentage: 100,
          detail: "Conversion completed successfully!",
        });

        // Locate generated files
        const findResult = locateGeneratedVault(options.outputPath, vaultBasePath);
        resolve({
          success: true,
          outputVaultRelativePath: findResult.vaultRelativePath,
          outputAbsolutePath: findResult.absolutePath,
          indexNoteVaultPath: findResult.indexNotePath,
        });
      } else {
        const errMsg =
          stderrBuffer.trim() ||
          stdoutBuffer.trim() ||
          `Process exited with status code ${code}`;
        resolve({
          success: false,
          outputVaultRelativePath: "",
          outputAbsolutePath: options.outputPath,
          error: errMsg,
        });
      }
    });
  });
}

/**
 * Searches the target directory for the generated book vault and Index.md.
 */
function locateGeneratedVault(
  targetDir: string,
  vaultBasePath: string
): { vaultRelativePath: string; absolutePath: string; indexNotePath?: string } {
  try {
    if (!fs.existsSync(targetDir)) {
      return { vaultRelativePath: "", absolutePath: targetDir };
    }

    const relPath = path.relative(vaultBasePath, targetDir).replace(/\\/g, "/");

    // Look for * - Index.md or 00 - Index.md
    const files = fs.readdirSync(targetDir);
    let indexFile: string | undefined;

    // Check directly in targetDir
    for (const f of files) {
      if (f.endsWith("Index.md")) {
        indexFile = path.posix.join(relPath, f);
        break;
      }
    }

    // If targetDir contains a subfolder that has Index.md (e.g. targetDir/Book Title/Book Title - Index.md)
    if (!indexFile) {
      for (const f of files) {
        const subPath = path.join(targetDir, f);
        if (fs.statSync(subPath).isDirectory()) {
          const subFiles = fs.readdirSync(subPath);
          for (const sf of subFiles) {
            if (sf.endsWith("Index.md")) {
              const subRel = path.relative(vaultBasePath, subPath).replace(/\\/g, "/");
              return {
                vaultRelativePath: subRel,
                absolutePath: subPath,
                indexNotePath: path.posix.join(subRel, sf),
              };
            }
          }
        }
      }
    }

    return {
      vaultRelativePath: relPath,
      absolutePath: targetDir,
      indexNotePath: indexFile,
    };
  } catch {
    return { vaultRelativePath: "", absolutePath: targetDir };
  }
}
