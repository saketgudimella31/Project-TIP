import { type GridRoutingInstrumentation } from './routerInstrumentation.js';
import type { ContainerRoutingTopology, GridOrientation, GridSide, RouterPoint } from './types.js';
export type RouterTupleCost = [
    length: number,
    bends: number,
    boundaryTransitions: number,
    endpointCandidateRank: number
];
export interface RouterSearchResult {
    points: RouterPoint[];
    vertexIds: number[];
    cost: RouterTupleCost;
}
export interface RouterSearchCaps {
    maxExpandedStates?: number;
    maxInvocationExpandedStates?: number;
    maxEstimatedBytes?: number;
}
export interface RouterSearchBudget {
    expandedStates: number;
}
export interface RouterSearchOptions {
    metrics?: GridRoutingInstrumentation;
    caps?: RouterSearchCaps;
    endpointCandidateRank?: number;
    recordOutcome?: boolean;
    budget?: RouterSearchBudget;
    initialOrientation?: GridOrientation;
    initialSide?: GridSide;
    initialLength?: number;
    targetOrientation?: GridOrientation;
    targetSide?: GridSide;
    targetLength?: number;
    topologyValidated?: boolean;
    workspace?: RouterSearchWorkspace;
    heuristic?: 'bend-aware' | 'zero';
    queueOrder?: 'canonical' | 'reverse';
    estimatedBytesBase?: number;
    arcAllowed?: (from: RouterPoint, to: RouterPoint) => boolean;
}
export declare class RouterSearchWorkspace {
    stateVertices: Int32Array<ArrayBuffer>;
    orientations: Uint8Array<ArrayBuffer>;
    gLengths: Float64Array<ArrayBuffer>;
    gBends: Float64Array<ArrayBuffer>;
    gBoundaryTransitions: Float64Array<ArrayBuffer>;
    fLengths: Float64Array<ArrayBuffer>;
    fBends: Float64Array<ArrayBuffer>;
    predecessors: Int32Array<ArrayBuffer>;
    depths: Int32Array<ArrayBuffer>;
    ancestor4: Int32Array<ArrayBuffer>;
    best: Int32Array<ArrayBuffer>;
    heapChildren: Int32Array<ArrayBuffer>;
    heapSiblings: Int32Array<ArrayBuffer>;
    heapPairs: number[];
    touchedBestIndices: number[];
    constructor();
    reset(vertexCount: number): void;
    setBest(index: number, state: number): void;
    ensureStateCapacity(required: number): void;
    estimatedBytes(): number;
}
export declare function assertSearchBudgetAvailable(options: Pick<RouterSearchOptions, 'metrics' | 'caps' | 'budget'>): void;
export declare function compareTupleCost(a: RouterTupleCost, b: RouterTupleCost): number;
export declare function findShortestRoute(topology: Pick<ContainerRoutingTopology, 'vertices' | 'adjacency'> & Partial<Pick<ContainerRoutingTopology, 'adjacencyByVertex' | 'searchAdjacencyByVertex' | 'vertexCount' | 'getVertex' | 'getSearchArcs'>>, sourceId: number, targetId: number, options?: RouterSearchOptions): RouterSearchResult | undefined;
