import { ZodType } from "zod";

export class C2CSemantics {
  /**
   * Concept-to-Concept Semantic Layer.
   * Ensures data flowing between workflow stages strictly adheres to expected 
   * semantic schemas using Zod.
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
