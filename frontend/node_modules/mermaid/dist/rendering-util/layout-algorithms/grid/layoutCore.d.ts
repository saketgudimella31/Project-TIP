import type { LayoutData } from '../../types.js';
import { type GridRoutingTestOptions } from './router.js';
import type { GridRoutingInstrumentation } from './routerInstrumentation.js';
import { type GridLayoutResult } from './types.js';
/** @internal */
export interface GridLayoutCoreInternalOptions {
    metrics?: GridRoutingInstrumentation;
    routing?: GridRoutingTestOptions;
}
export declare function runGridLayoutCore(data4Layout: LayoutData, options?: GridLayoutCoreInternalOptions): GridLayoutResult;
