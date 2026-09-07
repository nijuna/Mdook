import { execFile } from "child_process";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";

export interface ResolvedCommand {
  executable: string;
  prefixArgs: string[];
  resolvedPath: string;
}

export interface ResolverResult {
  success: boolean;
  command?: ResolvedCommand;
  version?: string;
  error?: string;
}

/**
 * Executes a command and captures stdout/stderr.
 */
function execPromise(
  cmd: string,
  args: string[],
  timeoutMs = 5000
): Promise<{ stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    execFile(cmd, args, { timeout: timeoutMs }, (error, stdout, stderr) => {
      if (error) {
        reject(error);
      } else {
        resolve({ stdout, stderr });
      }
    });
  });
}

/**
 * Checks if a file exists and is executable.
 */
function isFileExecutable(filePath: string): boolean {
  try {
    fs.accessSync(filePath, fs.constants.X_OK);
    return true;
  } catch {
    return false;
  }
}

/**
 * Expand tilde (~) in path to user home directory.
 */
export function expandHome(filePath: string): string {
  if (!filePath) return "";
  if (filePath.startsWith("~/") || filePath === "~") {
    return path.join(os.homedir(), filePath.slice(1));
  }
  return filePath;
}

/**
 * Locates the mdook CLI executable or uv wrapper.
 */
export async function resolveMdook(customPath?: string): Promise<ResolverResult> {
  const candidates: ResolvedCommand[] = [];

  // 1. User-specified custom path
  if (customPath && customPath.trim().length > 0) {
    const expanded = expandHome(customPath.trim());
    candidates.push({
      executable: expanded,
      prefixArgs: [],
      resolvedPath: expanded,
    });
  }

  // 2. Direct binary name in PATH
  candidates.push({
    executable: "mdook",
    prefixArgs: [],
    resolvedPath: "mdook (in system PATH)",
  });

  // 3. Common user directory locations
  const home = os.homedir();
  const commonLocations = [
    path.join(home, ".local", "bin", "mdook"),
    path.join(home, ".cargo", "bin", "mdook"),
    "/usr/local/bin/mdook",
    "/usr/bin/mdook",
    path.join(home, ".venv", "bin", "mdook"),
    // Windows common locations
    path.join(process.env.APPDATA || "", "Python", "Scripts", "mdook.exe"),
    path.join(home, "AppData", "Local", "Programs", "Python", "Scripts", "mdook.exe"),
  ];

  for (const loc of commonLocations) {
    if (loc && isFileExecutable(loc)) {
      candidates.push({
        executable: loc,
        prefixArgs: [],
        resolvedPath: loc,
      });
    }
  }

  // 4. Test uv run mdook if uv is available
  candidates.push({
    executable: "uv",
    prefixArgs: ["run", "mdook"],
    resolvedPath: "uv run mdook",
  });

  // Test candidates in sequence
  for (const cand of candidates) {
    try {
      const args = [...cand.prefixArgs, "version"];
      const { stdout } = await execPromise(cand.executable, args, 3500);
      const match = stdout.match(/mdook\s+v?([0-9]+\.[0-9]+\.[0-9]+)/i);
      if (match) {
        return {
          success: true,
          command: cand,
          version: match[1],
        };
      }
    } catch {
      // Candidate failed, continue to next
    }
  }

  return {
    success: false,
    error:
      "Could not find a working 'mdook' CLI executable. Please install mdook via `pip install mdook` or `uv tool install mdook`, or specify the absolute path in plugin settings.",
  };
}
