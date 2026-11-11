import type { Point } from '../../../types.js';
import type { Node } from '../../types.js';
import { type EndpointCandidate } from './routerPlanning.js';
import type { GridContainerId, GridLayoutResult, GridOrientation, RouterPoint, RouterRect } from './types.js';
export declare function isPairSeparationError(error: unknown): boolean;
export declare function routerRect(node: Node): RouterRect;
export declare function validateSameContainerRoute(points: readonly Point[], source: Node, target: Node, containerId: GridContainerId, result: GridLayoutResult): boolean;
export declare function validateContainerSegment(points: readonly Point[], startOwnerId: string, endOwnerId: string, containerId: GridContainerId, result: GridLayoutResult): boolean;
export interface OrthogonalSegment {
    a: Point;
    b: Point;
    orientation: GridOrientation;
}
export declare function nonterminalSegments(points: readonly Point[]): OrthogonalSegment[];
export declare function pairSegmentsConflict(candidate: OrthogonalSegment, committed: OrthogonalSegment): boolean;
export declare function routeSatisfiesPairConstraints(points: readonly Point[], pairRoutes: readonly (readonly Point[])[]): boolean;
export declare function routeHasDistinctPairPorts(points: readonly Point[], pairRoutes: readonly (readonly Point[])[]): boolean;
export declare function pairArcAllowed(from: RouterPoint, to: RouterPoint, pairRoutes: readonly (readonly Point[])[]): boolean;
export declare function endpointPairLowerBound(source: EndpointCandidate, target: EndpointCandidate): readonly [length: number, bends: number];
