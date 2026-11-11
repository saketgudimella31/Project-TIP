import type { Graph, OrderedLayers, Coordinates } from './helpers.js';
export interface CoordOptions {
    layerGap?: number;
    nodeGap?: number;
    laneGap?: number;
    direction?: 'TB' | 'LR' | 'BT' | 'RL';
    laneOrder?: string[];
}
/**
 * Positions every node, and seeds each edge label (which has no rank) where the
 * layout keeps room for it:
 * - the label of an edge between two ranks widens the gap between them by the
 *   label's extent along the flow, in every direction;
 * - the label of an edge within one rank (a cross-lane edge) sits in that row,
 *   beyond the target lane's nodes on the side the edge comes in from. The lane
 *   widens on both sides, so its nodes stay centred where they would be without
 *   the label.
 */
export declare function assignCoordinates(ordered: OrderedLayers, gWithDummies: Graph, opts?: CoordOptions): Coordinates;
