import type { Node } from '../../types.js';
import { type GridForest } from './types.js';
export declare function buildGridForest(nodes: Node[]): GridForest;
export declare function isAncestorGroup(ancestorId: string, node: Node | undefined, nodeById: Map<string, Node>): boolean;
