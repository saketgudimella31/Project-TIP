import type { Node } from '../../types.js';
export type LaneRole = 'pool' | 'lane';
export declare function readLaneRole(node: Node | undefined): LaneRole | undefined;
export declare function readLaneIndex(node: Node | undefined): number | undefined;
export interface LaneModel {
    isPool: (id: string) => boolean;
    isLane: (id: string) => boolean;
    laneIdOf: (id: string) => string | null;
    poolIdOf: (id: string) => string | null;
    lanesByPool: Map<string, string[]>;
    hasPools: boolean;
}
export declare function buildLaneModel(nodes: Node[]): LaneModel;
/** For callers that hold things in a lane: whether a group is a lane, as `buildLaneModel` decides it. */
export declare function isLaneIn(nodes: Node[]): (group: Node) => boolean;
