import type { Edge } from '../types.js';
import type { SVGGroup } from '../../diagram-api/types.js';
/** Where along an edge the step badge may sit, as fractions of its length, in order of preference. */
export declare const STEP_BADGE_FRACTIONS: number[];
/** Badge radius in diagram units; the badge keeps this size whatever the edge length. */
export declare const STEP_BADGE_RADIUS = 9;
/** Badge text size in diagram units. */
export declare const STEP_BADGE_FONT_SIZE = 11;
interface PathPoint {
    x: number;
    y: number;
}
/** Something on the diagram the badge must not cover: a box around a centre. */
export interface BadgeObstacle extends PathPoint {
    halfWidth: number;
    halfHeight: number;
}
interface PathGeometry {
    getTotalLength?: () => number;
    getPointAtLength?: (distance: number) => PathPoint;
}
export interface StepBadgeOptions {
    points: PathPoint[];
    pathNode?: PathGeometry | null;
    color?: string;
    textColors?: (string | undefined)[];
}
/** Stroke width of the highlight drawn over the edge while its step plays. */
export declare const STEP_HIGHLIGHT_STROKE_WIDTH = 4;
/** Stroke opacity of the step highlight, so the edge line stays visible under it. */
export declare const STEP_HIGHLIGHT_STROKE_OPACITY = 0.6;
/** Radius of the dot that travels along a step edge. */
export declare const STEP_DOT_RADIUS = 4;
export interface EdgeStepTiming {
    begin: number;
    dur: number;
    gap: number;
}
/** When the dot for `step` starts, how long it runs, and how long it waits before the next loop. */
export declare const getEdgeStepTiming: (step: number, stepCount: number, stepDuration?: number) => EdgeStepTiming;
/** A distinct id safe in animation `begin` references: starts with a letter, keeps letters and digits, encodes every other character as `_hex_`. */
export declare const toAnimationId: (value: string) => string;
/** Escapes a string for use as a CSS identifier, using `CSS.escape` when the environment has it. */
export declare const escapeCssIdentifier: (value: string) => string;
/** The point `fraction` of the way along the polyline through `points`, by length. */
export declare const pointAlongPolyline: (points: PathPoint[], fraction: number) => PathPoint | undefined;
/** Samples the rendered path by length, falling back to the routed points when it has no geometry. */
export declare const createPathSampler: (points: PathPoint[], pathNode?: PathGeometry | null) => (fraction: number) => PathPoint | undefined;
/** The first preferred spot on the edge clear of every obstacle, then beside it, else the roomiest. */
export declare const chooseBadgePosition: (sample: (fraction: number) => PathPoint | undefined, obstacles: BadgeObstacle[]) => PathPoint | undefined;
/** The box an arrowhead covers: from `tip` back towards `from` for the arrowhead's length. */
export declare const arrowheadObstacle: (tip: PathPoint, from: PathPoint) => BadgeObstacle;
/** What no badge may cover, in SVG coordinates: labels, nodes and the arrowheads at every edge's marked ends. */
export declare const collectBadgeObstacles: (root: Element | null | undefined) => BadgeObstacle[];
/** The WCAG contrast ratio of two colours, or 0 when either cannot be read. */
export declare const contrastRatio: (first: string, second: string) => number;
/** The first candidate readable on `fill` (4.5:1), else the one with the most contrast. */
export declare const pickBadgeTextColor: (fill: string, candidates: (string | undefined)[]) => string;
/**
 * Appends a badge with the step number on a step edge when `flowchart.stepNumbers` is on, clear of
 * `obstacles` (SVG coordinates). Returns the badge's own box in SVG coordinates.
 */
export declare const insertEdgeStepBadge: (elem: SVGGroup, edge: Edge, options: StepBadgeOptions, obstacles?: BadgeObstacle[]) => BadgeObstacle | undefined;
/**
 * Appends the dot that travels along a step edge and a highlight stroke shown while it travels,
 * plus the reduced-motion rule once per SVG.
 */
export declare const insertEdgeStepDot: (elem: SVGGroup, edge: Edge, pathData: string, diagramId: string, color?: string) => void;
/** Draws the badges queued for `svg` in a layer above everything else, once the whole diagram is in place. */
export declare const placeQueuedStepBadges: (svg: Element | null | undefined) => void;
/** Draws a step edge's dot and highlight now and queues its badge for `placeQueuedStepBadges`. */
export declare const insertEdgeStepMarks: (elem: SVGGroup, edge: Edge, pathData: string, diagramId: string, badge: StepBadgeOptions) => void;
export {};
