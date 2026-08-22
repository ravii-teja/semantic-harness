export class ContextManager {
  private staticBlocks: Map<string, string> = new Map();
  private dynamicBlocks: Map<string, string> = new Map();

  setStatic(key: string, value: string): void {
    this.staticBlocks.set(key, value);
  }

  setDynamic(key: string, expr: string): void {
    this.dynamicBlocks.set(key, expr);
  }

  render(contextLocals: any): string {
    const rendered: string[] = [];
    
    if (this.staticBlocks.size > 0) {
      rendered.push("## Static Context");
      for (const [k, v] of this.staticBlocks.entries()) {
        rendered.push(`<${k}>\n${v}\n</${k}>`);
      }
    }

    if (this.dynamicBlocks.size > 0) {
      rendered.push("## Dynamic Context");
      for (const [k, expr] of this.dynamicBlocks.entries()) {
        // Caution: eval is used here for REPL-like behavior as per NOOA spec
        try {
          // eslint-disable-next-line no-new-func
          const val = new Function(...Object.keys(contextLocals), `return ${expr}`)(...Object.values(contextLocals));
          rendered.push(`<${k}>\n${val}\n</${k}>`);
        } catch (e: any) {
          rendered.push(`<${k}>\nError evaluating '${expr}': ${e.message}\n</${k}>`);
        }
      }
    }

    return rendered.join("\n\n");
  }
}
