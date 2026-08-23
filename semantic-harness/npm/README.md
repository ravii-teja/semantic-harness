# ⚡ Semantic Harness (TypeScript / Node.js)

[![TypeScript](https://img.shields.io/badge/typescript-5.0+-3178C6.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> TypeScript / Node.js implementation of Semantic Harness — C2C semantic validation, 3-tier memory engine, CodeAct REPL execution, and event-driven agent loop.

---

## 📦 Installation

```bash
npm install @ravii-teja/semantic-harness
```

---

## 🚀 Usage

### 1. Zod-Powered C2C Semantic Validation

```typescript
import { z } from "zod";
import { C2CSemantics } from "./src/semantics/c2c_semantics";

const PlanSchema = z.object({
  title: z.string(),
  steps: z.array(z.string()),
  estimatedMinutes: z.number(),
});

const semantics = new C2CSemantics(PlanSchema);
const validation = semantics.validate({
  title: "Deploy Service",
  steps: ["Build image", "Push to registry", "Apply Helm chart"],
  estimatedMinutes: 15,
});

if (validation.isValid) {
  console.log("Validated plan:", validation.data);
} else {
  console.log("Errors:", validation.errors);
}
```

### 2. Multi-Tier Memory

```typescript
import { ShortTermMemory } from "./src/memory/short_term";
import { LongTermMemory } from "./src/memory/long_term";
import { ProceduralMemory } from "./src/memory/procedural";

// Short-term conversation history
const stm = new ShortTermMemory(10);
stm.add({ role: "user", content: "What is our staging DB host?" });

// Persistent long-term memory
const ltm = new LongTermMemory();
ltm.remember("staging_db", "staging-db.internal.net", 0.9);

// Procedural cache for skipping repeated reasoning
const proc = new ProceduralMemory();
proc.cache("db_lookup", "staging", { host: "staging-db.internal.net" }, 1.0);
```

### 3. Agent Lifecycle & Event Bus

```typescript
import { Agent } from "./src/core/agent";
import { EventBus } from "./src/core/events";

const bus = new EventBus();
bus.on("turn/start", (evt) => console.log("Turn started:", evt));
```

---

## 🧪 Building & Typechecking

```bash
npx tsc --noEmit
```

---

## 📄 License

MIT License. Designed & developed by Ravi Teja.
