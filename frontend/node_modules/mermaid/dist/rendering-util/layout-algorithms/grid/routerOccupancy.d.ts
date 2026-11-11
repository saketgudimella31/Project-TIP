import type { Point } from '../../../types.js';
import type { RouterPoint } from './types.js';
/**
 * Parallel runs of different edges closer than this are hard to tell apart, so candidates avoid them.
 * Perpendicular crossings are not affected.
 */
export declare const EDGE_CLEARANCE_PX = 24;
/**
 * Container-scoped index of committed route segments.
 *
 * Routes from different edges must not share a corridor, so every routed edge registers its
 * nonterminal segments here and later candidates query it with the clearance rule
 * (`segmentsTooClose`). Segments are bucketed by their fixed coordinate so a query
 * only inspects lines within the clearance instead of every committed segment.
 *
 * Routes are append-only and can be truncated back to an earlier size, which is how bundle retries
 * roll back state.
 */
export declare class RouteOccupancyIndex {
    private readonly lines;
    private readonly sortedCoordinates;
    private readonly log;
    get size(): number;
    add(route: readonly Point[], pairKey: string): void;
    truncate(size: number): void;
    /** Reports whether a route shares a corridor with a committed route of another edge pair. */
    conflictsWithRoute(route: readonly Point[], pairKey: string): boolean;
    conflictsWithArc(from: RouterPoint, to: RouterPoint, pairKey: string): boolean;
    private conflicts;
    private coordinatesFor;
}
