import type { LayoutData } from '../../../types.js';
export interface Pt {
    x: number;
    y: number;
}
/**
 * The gap a reader can see between two strokes: the arrowhead gap plus the stroke width.
 * A bend closer than this to another route reads as touching it.
 */
export declare const VISIBLE_ROUTE_GAP: number;
export declare const distance: (a: Pt, b: Pt) => number;
export declare function distanceToSegment(p: Pt, a: Pt, b: Pt): number;
export declare const distinct: (points: Pt[]) => Pt[];
/** The points where a route turns. */
export declare function bends(points: Pt[]): Pt[];
/** Every place where the corner of one route lies within the visible gap of another route. */
export declare function routeTouches(layout: LayoutData): string[];
