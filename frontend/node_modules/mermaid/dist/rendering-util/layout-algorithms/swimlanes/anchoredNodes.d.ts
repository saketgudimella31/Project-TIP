import type { LayoutData, Node } from '../../types.js';
type Direction = 'TB' | 'LR' | 'BT' | 'RL';
export type AnchorSide = 'top' | 'right' | 'bottom' | 'left';
export declare const MAX_ANCHOR_GAP = 10000;
export interface NodeAnchor {
    hostId: string;
    side?: AnchorSide;
    slot?: number;
    gap?: number;
}
export declare function readAnchor(node: Node | undefined): NodeAnchor | undefined;
export declare function resolveAnchorHostId(id: string, byId: Map<string, Node>): string | undefined;
/** For a validator's `isAttached`: whether `nodeId` is pinned to `toId` through its anchor chain. */
export declare function isAnchoredTo(nodes: Node[]): (nodeId: string, toId: string) => boolean;
export declare function collectAnchoredIds(nodes: Node[]): Set<string>;
export declare function defaultAnchorSide(space: 'canonical' | 'final', direction: Direction): AnchorSide;
export interface AnchorPin {
    nodeId: string;
    hostId: string;
    side: AnchorSide;
    x: number;
    y: number;
    outward: {
        x: number;
        y: number;
    };
}
export interface AnchorFootprint {
    /** Room needed on the start side of the host's centre, along its border. */
    before: number;
    /** Room needed on the end side of the host's centre, along its border. */
    after: number;
    /** Room needed outward from the host's border. */
    beyond: number;
}
/**
 * The room each run of stood-off nodes needs, per host and per side the run stands on: a
 * node's own `side` when it has one, otherwise the side its direction defaults to.
 */
export declare function anchorFootprints(nodes: Node[], direction?: Direction): Map<string, Partial<Record<AnchorSide, AnchorFootprint>>>;
/** Whether a group is a lane or a pool, going by the `laneRole` its producer set. */
export declare const hasLaneRole: (group: Node) => boolean;
/**
 * Moves a stood-off node clear of what it overlaps, never out of the lane its host sits in.
 *
 * `isLane` says which group is a lane. The default reads `metadata.laneRole`, so a producer
 * must set it on its lanes and pools or pass a resolver of its own; a group that is not
 * recognised as a lane does not hold the node in.
 */
export declare function clearAnchoredOverlaps(layout: LayoutData, pins: AnchorPin[], isLane?: (group: Node) => boolean): AnchorPin[];
export declare function pinAnchoredNodes(layout: LayoutData, opts: {
    space: 'canonical' | 'final';
    direction: Direction;
}): AnchorPin[];
export declare function squareAnchoredEdges(layout: LayoutData, pins: AnchorPin[]): void;
export {};
