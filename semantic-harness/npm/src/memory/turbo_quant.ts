/**
 * TurboQuant & PolarQuant: Extreme Vector Quantization & Vector Search in TypeScript.
 *
 * Implements PolarQuant (FWHT + random polar sign projection + QJL residual correction)
 * for sub-microsecond vector search and 10x-32x memory compression.
 * Based on Google Research: arXiv:2504.19874 & arXiv:2502.02617
 */

function nextPowerOf2(n: number): number {
  if (n <= 1) return 1;
  return 1 << (32 - Math.clz32(n - 1));
}

function fastWalshHadamardTransform(vec: number[]): number[] {
  const n = vec.length;
  const res = [...vec];
  let h = 1;
  while (h < n) {
    for (let i = 0; i < n; i += h * 2) {
      for (let j = i; j < i + h; j++) {
        const x = res[j] ?? 0;
        const y = res[j + h] ?? 0;
        res[j] = x + y;
        res[j + h] = x - y;
      }
    }
    h *= 2;
  }
  const invNorm = 1.0 / Math.sqrt(n);
  return res.map((v) => v * invNorm);
}

function pseudoRandomSigns(dim: number, seed = 42): number[] {
  const signs: number[] = [];
  let curr = seed;
  for (let i = 0; i < dim; i++) {
    curr = (curr * 1103515245 + 12345) & 0x7fffffff;
    signs.push(curr % 2 === 0 ? 1.0 : -1.0);
  }
  return signs;
}

function pseudoRandomPermutation(dim: number, seed = 42): [number[], number[]] {
  const perm: number[] = Array.from({ length: dim }, (_, i) => i);
  let curr = seed;
  for (let i = dim - 1; i > 0; i--) {
    curr = (curr * 1103515245 + 12345) & 0x7fffffff;
    const j = curr % (i + 1);
    const tmp = perm[i] ?? i;
    perm[i] = perm[j] ?? j;
    perm[j] = tmp;
  }
  const invPerm: number[] = new Array(dim).fill(0);
  for (let i = 0; i < dim; i++) {
    const p = perm[i] ?? i;
    invPerm[p] = i;
  }
  return [perm, invPerm];
}

export interface QuantizedVector {
  packedBits: Uint8Array;
  dim: number;
  paddedDim: number;
  norm: number;
  qjlBits?: Uint8Array | undefined;
  seed: number;
}

export class PolarQuantizer {
  public readonly dim: number;
  public readonly paddedDim: number;
  public readonly seed: number;
  public readonly enableQjl: boolean;
  private readonly signs: number[];
  private readonly qjlSigns: number[];
  private readonly perm: number[];
  private readonly invPerm: number[];
  private readonly qjlPerm: number[];

  constructor(dim = 64, seed = 42, enableQjl = true) {
    this.dim = dim;
    this.paddedDim = nextPowerOf2(dim);
    this.seed = seed;
    this.enableQjl = enableQjl;
    this.signs = pseudoRandomSigns(this.paddedDim, seed);
    this.qjlSigns = pseudoRandomSigns(this.paddedDim, seed + 999);
    const [p, ip] = pseudoRandomPermutation(this.paddedDim, seed + 123);
    this.perm = p;
    this.invPerm = ip;
    const [qp] = pseudoRandomPermutation(this.paddedDim, seed + 456);
    this.qjlPerm = qp;
  }

  private packSigns(signs: boolean[]): Uint8Array {
    const numBytes = Math.ceil(signs.length / 8);
    const ba = new Uint8Array(numBytes);
    for (let i = 0; i < signs.length; i++) {
      if (signs[i]) {
        const byteIdx = Math.floor(i / 8);
        ba[byteIdx] = (ba[byteIdx] ?? 0) | (1 << (i % 8));
      }
    }
    return ba;
  }

  public quantize(vector: number[]): QuantizedVector {
    let v: number[];
    if (vector.length !== this.dim) {
      v = vector.slice(0, this.dim);
      while (v.length < this.dim) v.push(0.0);
    } else {
      v = [...vector];
    }

    const normSq = v.reduce((acc, x) => acc + x * x, 0);
    const norm = normSq > 0 ? Math.sqrt(normSq) : 1.0;
    const unitV = norm > 0 ? v.map((x) => x / norm) : v;

    const padded = [...unitV];
    while (padded.length < this.paddedDim) padded.push(0.0);

    const signed = padded.map((x, i) => x * (this.signs[i] ?? 1.0));
    const permuted = Array.from({ length: this.paddedDim }, (_, i) => {
      const idx = this.perm[i] ?? i;
      return signed[idx] ?? 0.0;
    });
    const hadamard = fastWalshHadamardTransform(permuted);

    const polarSigns = hadamard.map((x) => x >= 0);
    const packedPolar = this.packSigns(polarSigns);

    let qjlPacked: Uint8Array | undefined = undefined;
    if (this.enableQjl) {
      const reconMag = 1.0 / Math.sqrt(this.paddedDim);
      const recon = polarSigns.map((s) => (s ? 1.0 : -1.0) * reconMag);
      const residual = hadamard.map((h, i) => h - (recon[i] ?? 0));
      const qjlSigned = residual.map((r, i) => r * (this.qjlSigns[i] ?? 1.0));
      const qjlPermuted = Array.from({ length: this.paddedDim }, (_, i) => {
        const idx = this.qjlPerm[i] ?? i;
        return qjlSigned[idx] ?? 0.0;
      });
      const qjlHadamard = fastWalshHadamardTransform(qjlPermuted);
      const qjlSigns = qjlHadamard.map((x) => x >= 0);
      qjlPacked = this.packSigns(qjlSigns);
    }

    return {
      packedBits: packedPolar,
      dim: this.dim,
      paddedDim: this.paddedDim,
      norm,
      qjlBits: qjlPacked,
      seed: this.seed,
    };
  }

  public static similarity(q1: QuantizedVector, q2: QuantizedVector): number {
    const totalDim = q1.paddedDim;
    let differingBits = 0;
    for (let i = 0; i < q1.packedBits.length; i++) {
      const b1 = q1.packedBits[i] ?? 0;
      const b2 = q2.packedBits[i] ?? 0;
      let xor = b1 ^ b2;
      while (xor > 0) {
        differingBits += xor & 1;
        xor >>= 1;
      }
    }

    const theta = (differingBits / totalDim) * Math.PI;
    let baseCosine = Math.cos(theta);

    if (q1.qjlBits && q2.qjlBits) {
      let qjlDiff = 0;
      for (let i = 0; i < q1.qjlBits.length; i++) {
        const b1 = q1.qjlBits[i] ?? 0;
        const b2 = q2.qjlBits[i] ?? 0;
        let xor = b1 ^ b2;
        while (xor > 0) {
          qjlDiff += xor & 1;
          xor >>= 1;
        }
      }
      const qjlTheta = (qjlDiff / totalDim) * Math.PI;
      baseCosine += Math.cos(qjlTheta) * (Math.PI / (2.0 * totalDim));
    }

    return Math.max(-1.0, Math.min(1.0, baseCosine));
  }
}

export class SemanticFeatureEmbedder {
  constructor(public readonly dim = 64) {}

  public embed(text: string): number[] {
    const tokens = text.toLowerCase().trim().split(/\s+/);
    if (tokens.length === 0 || text.trim().length === 0) {
      return new Array(this.dim).fill(0.0);
    }

    const vec: number[] = new Array(this.dim).fill(0.0);
    const features = [...tokens];
    const cleaned = text.toLowerCase().replace(/[^a-z0-9\s]/g, "");
    for (let i = 0; i < cleaned.length - 2; i++) {
      features.push(cleaned.substring(i, i + 3));
    }

    for (const feat of features) {
      let h = 0;
      for (let i = 0; i < feat.length; i++) {
        h = (Math.imul(31, h) + feat.charCodeAt(i)) | 0;
      }
      const idx = Math.abs(h) % this.dim;
      const sign = (h >> 8) % 2 === 0 ? 1.0 : -1.0;
      vec[idx] = (vec[idx] ?? 0.0) + sign * (1.0 + feat.length * 0.2);
    }

    const normSq = vec.reduce((acc, x) => acc + x * x, 0);
    if (normSq > 0) {
      const invNorm = 1.0 / Math.sqrt(normSq);
      return vec.map((x) => x * invNorm);
    }
    return vec;
  }
}

export interface SearchResult<T = any> {
  key: string;
  similarity: number;
  procedure: T;
  confidence: number;
  intentText: string;
}

export class TurboQuantVectorIndex<T = any> {
  private readonly quantizer: PolarQuantizer;
  private readonly embedder: SemanticFeatureEmbedder;
  private readonly entries = new Map<
    string,
    {
      key: string;
      intentText: string;
      procedure: T;
      quantized: QuantizedVector;
      confidence: number;
    }
  >();

  constructor(public readonly dim = 64) {
    this.quantizer = new PolarQuantizer(dim);
    this.embedder = new SemanticFeatureEmbedder(dim);
  }

  public add(key: string, intentText: string, procedure: T, vector?: number[], confidence = 1.0): void {
    const vec = vector || this.embedder.embed(intentText);
    const quantized = this.quantizer.quantize(vec);
    this.entries.set(key, { key, intentText, procedure, quantized, confidence });
  }

  public search(query: string | number[], topK = 5, minSimilarity = 0.7): SearchResult<T>[] {
    const queryVec = typeof query === "string" ? this.embedder.embed(query) : query;
    const qQuery = this.quantizer.quantize(queryVec);

    const results: SearchResult<T>[] = [];
    for (const item of this.entries.values()) {
      const sim = PolarQuantizer.similarity(qQuery, item.quantized);
      if (sim >= minSimilarity) {
        results.push({
          key: item.key,
          similarity: sim,
          procedure: item.procedure,
          confidence: item.confidence,
          intentText: item.intentText,
        });
      }
    }

    return results.sort((a, b) => b.similarity - a.similarity).slice(0, topK);
  }

  public remove(key: string): void {
    this.entries.delete(key);
  }

  public get size(): number {
    return this.entries.size;
  }
}
