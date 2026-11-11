import type { Edge, LayoutData, Node } from '../../types.js';
import type { GridContainerId, GridLayoutResult, GridSide, RouterPoint } from './types.js';
export declare const TERMINAL_APPROACH_PX = 20;
export declare const LANE_SEPARATION_PX = 8;
export interface EdgeEndpointEntry {
    ownerId: string;
    side: GridSide;
    demandKey: string;
    oppositeCoord: number;
    preferredCoord: number;
    compactPortal: boolean;
}
export interface EdgeEndpointPlan {
    chain: EdgeEndpointEntry[];
    finalKind: 'item' | 'boundary';
}
export interface EdgeRoutePlan {
    edge: Edge;
    lcaContainerId: GridContainerId;
    source: EdgeEndpointPlan;
    target: EdgeEndpointPlan;
    laneIndex: number;
    laneOffset: number;
    bundleSize: number;
    pairKey: string;
}
export interface EdgeRouteCandidates {
    sources: EndpointCandidate[];
    targets: EndpointCandidate[];
}
export interface PreparedEdgeRoutes {
    plans: EdgeRoutePlan[];
    eligiblePlans: EdgeRoutePlan[];
    eligibleIds: Set<string>;
    orderedPlans: EdgeRoutePlan[];
    demandCoords: Map<string, number>;
    endpointCandidatesByEdge: Map<string, EdgeRouteCandidates>;
    endpointIncidentCounts: Map<string, number>;
}
export declare function ownerGroupTitle(node: Node): boolean;
export declare function ownerSideKey(ownerId: string, side: GridSide): string;
export declare function assignCompactPortalCoordinates(desired: readonly number[], low: number, high: number): number[];
export interface EndpointCandidate {
    ownerId: string;
    side: GridSide;
    port: RouterPoint;
    connect: RouterPoint;
    rank: number;
}
export declare function sideOrder(side: GridSide): number;
export declare function sideInterval(owner: Node, side: GridSide): {
    low: number;
    high: number;
} | undefined;
export declare function prepareEdgeRoutes(layout: LayoutData, result: GridLayoutResult): PreparedEdgeRoutes;
