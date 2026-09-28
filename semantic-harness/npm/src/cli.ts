#!/usr/bin/env node
import * as fs from "fs";
import * as path from "path";
import { HardwareDetector } from "./core/hardware.js";
import { VERSION } from "./index.js";

function printUsage(): void {
  console.log(`
Semantic Harness (TypeScript / Node) CLI v${VERSION}

Usage:
  semantic-harness <command> [options]

Commands:
  hardware                     Inspect host hardware and accelerator capabilities
  cache inspect <cache-file>   Inspect procedural cache entries and hit statistics
  cache export <cache-file>    Export procedural cache to JSON (optional: -o <path>)
  version                      Display version information
  help                         Show this help message
`);
}

function handleHardware(): void {
  const profile = HardwareDetector.detect();
  console.log("\n=== Semantic Harness Hardware Profile (Node.js) ===");
  console.log(`Accelerator:           ${profile.accelerator}`);
  console.log(`Device Name:           ${profile.deviceName}`);
  console.log(`CPU Cores:             ${profile.cpuCores}`);
  console.log(`Total Memory (GB):     ${profile.totalMemoryGB}`);
  console.log(`Available Memory (GB): ${profile.availableMemoryGB}`);
  console.log(`Recommended Model:     ${profile.recommendedModel}`);
  console.log(`Recommended Provider:  ${profile.recommendedProvider}\n`);
}

function handleCacheInspect(filePath: string): void {
  if (!fs.existsSync(filePath)) {
    console.error(`Error: File not found: ${filePath}`);
    process.exit(1);
  }

  try {
    const raw = fs.readFileSync(filePath, "utf-8");
    const data = JSON.parse(raw);
    const entries = Array.isArray(data) ? data : data.procedures ? Object.values(data.procedures) : [data];

    console.log(`\n=== Procedural Cache Snapshot: ${path.basename(filePath)} ===`);
    console.log(`Total Procedures: ${entries.length}\n`);

    for (const [idx, item] of (entries as any[]).entries()) {
      const intent = item.intentText || item.intent || item.intentHash || "unknown";
      const successes = item.successCount ?? item.successes ?? 0;
      const failures = item.failureCount ?? item.failures ?? 0;
      const total = successes + failures;
      const rate = total > 0 ? ((successes / total) * 100).toFixed(1) : "N/A";
      console.log(`[${idx + 1}] Intent: "${intent}"`);
      console.log(`    Successes: ${successes} | Failures: ${failures} | Success Rate: ${rate}%`);
      console.log(`    Procedure: ${JSON.stringify(item.procedure || item.trajectory || item).slice(0, 80)}...`);
    }
    console.log("");
  } catch (err: any) {
    console.error(`Failed to parse cache file: ${err.message}`);
    process.exit(1);
  }
}

function handleCacheExport(filePath: string, outPath?: string): void {
  if (!fs.existsSync(filePath)) {
    console.error(`Error: File not found: ${filePath}`);
    process.exit(1);
  }

  const raw = fs.readFileSync(filePath, "utf-8");
  const data = JSON.parse(raw);
  const formatted = JSON.stringify(data, null, 2);

  if (outPath) {
    fs.writeFileSync(outPath, formatted, "utf-8");
    console.log(`Exported cache to ${outPath}`);
  } else {
    console.log(formatted);
  }
}

export function main(args: string[] = process.argv.slice(2)): void {
  const cmd = args[0];

  switch (cmd) {
    case "hardware":
      handleHardware();
      break;
    case "cache":
      const subcmd = args[1];
      const targetFile = args[2];
      if (subcmd === "inspect" && targetFile) {
        handleCacheInspect(targetFile);
      } else if (subcmd === "export" && targetFile) {
        const outIdx = args.indexOf("-o");
        const outPath = outIdx !== -1 && args[outIdx + 1] ? args[outIdx + 1] : undefined;
        handleCacheExport(targetFile, outPath);
      } else {
        printUsage();
      }
      break;
    case "version":
    case "-v":
    case "--version":
      console.log(`semantic-harness v${VERSION}`);
      break;
    case "help":
    case "-h":
    case "--help":
    default:
      printUsage();
      break;
  }
}

// If invoked directly from terminal
if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}
