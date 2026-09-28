import * as os from "os";
import { execSync } from "child_process";

export type AcceleratorType = "METAL" | "CUDA" | "CPU";

export interface HardwareProfile {
  accelerator: AcceleratorType;
  deviceName: string;
  cpuCores: number;
  totalMemoryGB: number;
  availableMemoryGB: number;
  recommendedModel: string;
  recommendedProvider: string;
}

export class HardwareDetector {
  public static detect(): HardwareProfile {
    const platform = process.platform;
    const arch = process.arch;
    const cpuCores = os.cpus().length;
    const totalMemoryGB = Math.round((os.totalmem() / (1024 ** 3)) * 10) / 10;
    const availableMemoryGB = Math.round((os.freemem() / (1024 ** 3)) * 10) / 10;

    // 1. Apple Silicon Metal Detection
    if (platform === "darwin" && (arch === "arm64" || arch === "arm")) {
      const recModel = totalMemoryGB >= 16 ? "mlx/Qwen2.5-7B-Instruct-4bit" : "mlx/Qwen2.5-0.5B-Instruct-4bit";
      return {
        accelerator: "METAL",
        deviceName: "Apple Silicon (Metal)",
        cpuCores,
        totalMemoryGB,
        availableMemoryGB,
        recommendedModel: recModel,
        recommendedProvider: "mlx",
      };
    }

    // 2. NVIDIA CUDA Detection via nvidia-smi
    try {
      const smiOutput = execSync("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader", {
        encoding: "utf-8",
        stdio: ["ignore", "pipe", "ignore"],
        timeout: 1500,
      }).trim();

      if (smiOutput.length > 0) {
        const firstGpu = smiOutput.split("\n")[0];
        return {
          accelerator: "CUDA",
          deviceName: firstGpu || "NVIDIA GPU",
          cpuCores,
          totalMemoryGB,
          availableMemoryGB,
          recommendedModel: "ollama/qwen2.5-coder:3b",
          recommendedProvider: "ollama",
        };
      }
    } catch {
      // nvidia-smi not available or no CUDA GPU
    }

    // 3. CPU Fallback
    const recCpuModel = totalMemoryGB >= 8 ? "ollama/qwen2.5:1.5b" : "ollama/qwen2.5:0.5b";
    return {
      accelerator: "CPU",
      deviceName: `${os.cpus()[0]?.model || "Generic CPU"} (${arch})`,
      cpuCores,
      totalMemoryGB,
      availableMemoryGB,
      recommendedModel: recCpuModel,
      recommendedProvider: "ollama",
    };
  }
}
