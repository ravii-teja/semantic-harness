import { test } from "node:test";
import * as assert from "node:assert";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";
import { HardwareDetector } from "./core/hardware.js";
import { main as runCli } from "./cli.js";

test("TypeScript HardwareDetector detects host environment", () => {
  const profile = HardwareDetector.detect();
  assert.ok(["METAL", "CUDA", "CPU"].includes(profile.accelerator));
  assert.ok(profile.cpuCores > 0);
  assert.ok(profile.totalMemoryGB > 0);
  assert.ok(profile.availableMemoryGB > 0);
  assert.ok(profile.recommendedModel.length > 0);
  assert.ok(profile.recommendedProvider.length > 0);

  if (process.platform === "darwin" && (process.arch === "arm64" || process.arch === "arm")) {
    assert.strictEqual(profile.accelerator, "METAL");
    assert.strictEqual(profile.recommendedProvider, "mlx");
  }
});

test("TypeScript CLI handles version, hardware, and cache commands", () => {
  // Capture stdout
  const originalLog = console.log;
  const logs: string[] = [];
  console.log = (...args: any[]) => {
    logs.push(args.join(" "));
  };

  try {
    // 1. Version
    runCli(["version"]);
    assert.ok(logs.some((l) => l.includes("0.2.5")));

    // 2. Hardware
    runCli(["hardware"]);
    assert.ok(logs.some((l) => l.includes("=== Semantic Harness Hardware Profile (Node.js) ===")));

    // 3. Cache inspect and export
    const tmpDir = os.tmpdir();
    const testCachePath = path.join(tmpDir, `test_cache_${Date.now()}.json`);
    const testExportPath = path.join(tmpDir, `test_export_${Date.now()}.json`);

    fs.writeFileSync(
      testCachePath,
      JSON.stringify({
        procedures: {
          inv1: {
            intent: "extract_invoice",
            successCount: 5,
            failureCount: 1,
            procedure: { code: "return data" },
          },
        },
      })
    );

    runCli(["cache", "inspect", testCachePath]);
    assert.ok(logs.some((l) => l.includes("Total Procedures: 1")));

    runCli(["cache", "export", testCachePath, "-o", testExportPath]);
    assert.ok(fs.existsSync(testExportPath));

    // Cleanup
    try {
      fs.unlinkSync(testCachePath);
      fs.unlinkSync(testExportPath);
    } catch {}
  } finally {
    console.log = originalLog;
  }
});
