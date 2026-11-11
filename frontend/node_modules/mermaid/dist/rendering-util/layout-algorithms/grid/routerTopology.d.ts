import { type GridRoutingInstrumentation } from './routerInstrumentation.js';
import type { ContainerRoutingTopology, GridSide, PairedPortal, PortalRange, RouterArc, RouterPoint, RouterRect, RouterSearchArc, RouterVertex } from './types.js';
export declare const ROUTE_CLEARANCE_PX = 6;
export declare const DEFAULT_MAX_ROUTING_ESTIMATED_BYTES: number;
export interface RouterObstacleInput {
    id: string;
    bounds: RouterRect;
}
export interface ContainerTopologyInput {
    containerId: string;
    bounds: RouterRect;
    obstacles: readonly RouterObstacleInput[];
    titleExclusions?: readonly RouterObstacleInput[];
    portalRanges?: readonly PortalRange[];
}
export interface TopologyResourceCaps {
    maxVertices?: number;
    maxAdjacencyEntries?: number;
    maxEstimatedBytes?: number;
}
export interface BuildTopologyOptions {
    metrics?: GridRoutingInstrumentation;
    caps?: TopologyResourceCaps;
}
export declare class EndpointOverlayScratch {
    readonly base: ContainerRoutingTopology;
    readonly addedVertices: RouterVertex[];
    readonly adjacencyOverrides: Map<number, readonly RouterArc[]>;
    readonly searchAdjacencyOverrides: Map<number, readonly RouterSearchArc[]>;
    readonly pointOverrides: Map<string, number>;
    readonly undoLog: number[];
    resetCount: number;
    constructor(base: ContainerRoutingTopology);
    reset(base: ContainerRoutingTopology): void;
    setArcs(id: number, arcs: readonly RouterArc[]): void;
}
export declare function routingPointKey(point: RouterPoint): string;
export declare function derivePortalRanges(ownerId: string, rawBounds: RouterRect, rawTitle?: RouterRect): PortalRange[];
export declare function buildPairedPortal(ownerId: string, bounds: RouterRect, title: RouterRect | undefined, side: GridSide, tangentialCoordinate: number): PairedPortal;
export declare function buildContainerRoutingTopology(input: ContainerTopologyInput, options?: BuildTopologyOptions): ContainerRoutingTopology;
export declare function buildEndpointRoutingOverlay(base: ContainerRoutingTopology, source: RouterPoint, target: RouterPoint, metrics?: GridRoutingInstrumentation, reusableScratch?: EndpointOverlayScratch, lanePoints?: readonly RouterPoint[]): ContainerRoutingTopology;
