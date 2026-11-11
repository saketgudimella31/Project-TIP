import type { Point } from '../../../types.js';
import type { Node } from '../../types.js';
import type { GridRoutingTestOptions } from './router.js';
import { RouteOccupancyIndex } from './routerOccupancy.js';
import { type EdgeEndpointPlan, type EdgeRoutePlan, type PreparedEdgeRoutes } from './routerPlanning.js';
import { type GridRoutingInstrumentation } from './routerInstrumentation.js';
import type { GridAttachment, GridContainerId, GridLayoutResult, GridRoutingContext, GridSide, PairedPortal } from './types.js';
export declare const SELF_LOOP_PORT_GAP = 18;
export declare const SELF_LOOP_PORT_OFFSET_STEP = 4;
export interface PreparedRoutingModes {
    compatibilityFastRoutes: Map<string, Point[]>;
    sparseHierarchyIds: Set<string>;
    sparseLcaIds: Set<string>;
    routedContainerIds: GridContainerId[];
    routeOccupancy: Map<GridContainerId, RouteOccupancyIndex>;
}
export declare function boundedAlternativePortalCoordinates(selected: number, low: number, high: number, corridors: readonly number[], limit?: number): number[];
export declare function areExactlyAxisAligned(a: Point, b: Point): boolean;
export declare function routeWithinContainer(containerId: GridContainerId, result: GridLayoutResult, start: GridAttachment, end: GridAttachment, variant: number): Point[];
export declare function itemAttachment(ownerId: string, side: GridSide, demandKey: string, containerId: GridContainerId, result: GridLayoutResult, demandCoords: Map<string, number>, coordinate?: number): GridAttachment;
export declare function boundaryAttachment(containerId: GridContainerId, side: GridSide, demandKey: string, result: GridLayoutResult, demandCoords: Map<string, number>): GridAttachment;
export interface SegmentAttachment extends GridAttachment {
    ownerId: string;
}
export interface SegmentAttachmentAlternative {
    attachment: SegmentAttachment;
    select: () => void;
}
export declare function portalAttachment(portal: PairedPortal, interior: boolean): SegmentAttachment;
export declare function groupBoundaryEndpointAttachment(ownerId: string, side: GridSide, demandKey: string, result: GridLayoutResult, demandCoords: Map<string, number>): SegmentAttachment;
export declare function reversePoints(points: Point[]): Point[];
export declare function combinePointChains(chains: Point[][]): Point[];
export declare function orderedSelfLoopSides(node: Node, counts: Map<string, number>, selfLoopCounts: Map<string, number>): GridSide[];
export declare function routeObstacleClearSelfLoop(owner: Node, ownerSideCounts: Map<string, number>, selfLoopCounts: Map<string, number>, result: GridLayoutResult): {
    points: Point[];
    side: GridSide;
    index: number;
};
export declare function rootContainerMeta(result: GridLayoutResult): void;
export declare function buildRoutingContext(containerIds: readonly GridContainerId[], result: GridLayoutResult, metrics: GridRoutingInstrumentation | undefined, options: GridRoutingTestOptions): GridRoutingContext;
export declare function validatedCompatibilitySegment(edgeId: string, containerId: GridContainerId, start: SegmentAttachment, end: SegmentAttachment, route: () => Point[], result: GridLayoutResult, metrics?: GridRoutingInstrumentation): Point[];
export declare function compatibilityLcaAttachments(plan: EdgeRoutePlan, result: GridLayoutResult, demandCoords: Map<string, number>): {
    start: SegmentAttachment;
    end: SegmentAttachment;
};
export interface CompatibilitySegmentAttachments {
    containerId: GridContainerId;
    start: SegmentAttachment;
    end: SegmentAttachment;
}
export declare function compatibilityHierarchyAttachments(endpoint: EdgeEndpointPlan, result: GridLayoutResult, demandCoords: Map<string, number>): CompatibilitySegmentAttachments[];
export declare function prepareRoutingModes(prepared: PreparedEdgeRoutes, result: GridLayoutResult, metrics: GridRoutingInstrumentation | undefined, options: GridRoutingTestOptions): PreparedRoutingModes;
