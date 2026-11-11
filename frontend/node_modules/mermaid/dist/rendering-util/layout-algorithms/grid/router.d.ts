import type { LayoutData } from '../../types.js';
import type { GridRoutingInstrumentation } from './routerInstrumentation.js';
import type { RouterSearchCaps } from './routerSearch.js';
import type { TopologyResourceCaps } from './routerTopology.js';
import type { GridLayoutResult } from './types.js';
export { areExactlyAxisAligned, boundedAlternativePortalCoordinates, } from './routerCompatibility.js';
export { validateSameContainerRoute } from './routerConstraint.js';
export { assignCompactPortalCoordinates } from './routerPlanning.js';
export interface GridRoutingDualRouteComparison {
    edgeId: string;
    sparse: {
        valid: boolean;
        length: number;
        bends: number;
    };
    legacy: {
        valid: boolean;
        length: number;
        bends: number;
    };
}
export interface GridRoutingOptions {
    topologyCaps?: TopologyResourceCaps;
    searchCaps?: RouterSearchCaps;
}
/** @internal */
export interface GridRoutingTestOptions extends GridRoutingOptions {
    onDualRouteComparison?: (comparison: GridRoutingDualRouteComparison) => void;
}
export declare function routeGridEdges(layout: LayoutData, result: GridLayoutResult, metrics?: GridRoutingInstrumentation, options?: GridRoutingOptions): void;
