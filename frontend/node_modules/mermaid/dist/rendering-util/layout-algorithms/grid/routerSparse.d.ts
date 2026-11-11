import type { Point } from '../../../types.js';
import type { Node } from '../../types.js';
import type { GridRoutingTestOptions } from './router.js';
import type { RouteOccupancyIndex } from './routerOccupancy.js';
import { type SegmentAttachment, type SegmentAttachmentAlternative } from './routerCompatibility.js';
import { type EdgeRoutePlan, type EndpointCandidate } from './routerPlanning.js';
import { type RouterSearchWorkspace } from './routerSearch.js';
import { type EndpointOverlayScratch } from './routerTopology.js';
import type { GridContainerId, GridLayoutResult, GridRoutingContext, GridSide } from './types.js';
export declare function sparseSameContainerRoute(plan: EdgeRoutePlan, sources: readonly EndpointCandidate[], targets: readonly EndpointCandidate[], source: Node, target: Node, legacyRoute: () => Point[], result: GridLayoutResult, context: GridRoutingContext, searchWorkspace: RouterSearchWorkspace, overlayScratch: EndpointOverlayScratch, options: GridRoutingTestOptions, pairRoutes: readonly (readonly Point[])[], occupied?: {
    index: RouteOccupancyIndex;
    pairKey: string;
}): Point[];
export declare function sparseSelfLoopRoute(plan: EdgeRoutePlan, owner: Node, result: GridLayoutResult, context: GridRoutingContext, searchWorkspace: RouterSearchWorkspace, overlayScratch: EndpointOverlayScratch | undefined, ownerSideCounts: Map<string, number>, selfLoopCounts: Map<string, number>, pairRoutes: readonly (readonly Point[])[], options: GridRoutingTestOptions): {
    points: Point[];
    side: GridSide;
    index: number;
};
export declare function sparseContainerSegment(edgeId: string, containerId: GridContainerId, start: SegmentAttachment, end: SegmentAttachment, legacyRoute: () => Point[], result: GridLayoutResult, context: GridRoutingContext, searchWorkspace: RouterSearchWorkspace, overlayScratch: EndpointOverlayScratch | undefined, options: GridRoutingTestOptions, pairRoutes?: readonly (readonly Point[])[], endAlternatives?: () => readonly SegmentAttachmentAlternative[], startAlternatives?: () => readonly SegmentAttachmentAlternative[], allowSharedPairCorridors?: boolean): Point[];
