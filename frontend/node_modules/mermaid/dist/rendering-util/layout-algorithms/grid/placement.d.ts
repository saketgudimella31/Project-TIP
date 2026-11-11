import type { Node } from '../../types.js';
import { type GridLayoutConfigNormalized, type GridResolvedPlacement, type GridLayoutData, type GridCellStack } from './types.js';
export declare function buildGridSourceOrder(nodes: Node[]): Map<string, number>;
export declare function readGridConfig(data: GridLayoutData): GridLayoutConfigNormalized;
export declare function validateGridPlacementMap(items: Iterable<Node>, config: GridLayoutConfigNormalized): void;
export declare function resolveGridPlacements(items: Node[], sourceOrder: Map<string, number>, config: GridLayoutConfigNormalized): {
    placements: GridResolvedPlacement[];
    cells: Map<string, GridCellStack>;
};
