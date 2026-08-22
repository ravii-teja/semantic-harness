import * as vm from 'vm';

export class NodeREPL {
  private context: vm.Context;

  constructor(initialLocals: Record<string, any> = {}) {
    this.context = vm.createContext({ ...initialLocals, console, Error });
  }

  execute(code: string): { success: boolean; output: string; returnedValue?: any } {
    const logs: string[] = [];
    
    // Override console.log temporarily
    const originalLog = console.log;
    this.context.console = {
      log: (...args: any[]) => {
        logs.push(args.map(a => typeof a === 'object' ? JSON.stringify(a) : a).join(' '));
      }
    };
    
    this.context._return_val = null;

    let success = true;
    let output = "";
    
    try {
      vm.runInContext(code, this.context);
      output = logs.join('\n');
    } catch (e: any) {
      success = false;
      output = e.stack || e.message;
    } finally {
      this.context.console.log = originalLog;
    }

    return { success, output, returnedValue: this.context._return_val };
  }
}
