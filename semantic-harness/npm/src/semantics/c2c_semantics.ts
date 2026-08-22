import { z, ZodType } from "zod";

/**
 * Chaos2Clarity (C2C) Semantics Module
 *
 * Implements strict runtime validation and automatic diagnostic feedback for agent outputs.
 * Based on Chaos2Clarity research: https://zenodo.org/records/19414309
 */

export interface C2CValidationResult<T = any> {
  isValid: boolean;
  data?: T;
  errors?: string[];
  retryPrompt?: string;
}

export class C2CSemantics {
  /**
   * Chaos2Clarity Semantic Layer.
   * Enforces schema conformance on raw outputs and generates repair prompts.
   */
  static validateAndMap<T>(data: any, targetSchema: ZodType<T>): T {
    const result = targetSchema.safeParse(data);
    
    if (!result.success) {
      const formattedErrors = result.error.issues.map((err: any) => `Field '${err.path.join('.')}': ${err.message}`);
      const errorMessage = "Semantic Validation Failed. Please correct your output:\n" + formattedErrors.join("\n");
      throw new Error(errorMessage);
    }
    
    return result.data;
  }
}
