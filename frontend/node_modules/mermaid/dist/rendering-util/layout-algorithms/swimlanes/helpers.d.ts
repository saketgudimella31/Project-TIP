import type { LayoutData, Node as MermaidNode, Edge as MermaidEdge } from '../../types.js';
export type Layout = LayoutData;
export type Node = MermaidNode;
export type NodeId = Node['id'];
export type EdgeId = MermaidEdge['id'];
export interface EdgeRef {
    id: EdgeId;
    src: NodeId;
    dst: NodeId;
    weight?: number;
    ref: MermaidEdge;
}
export interface Graph {
    nodes: NodeId[];
    edges: EdgeRef[];
    layout: Layout;
    nodeById: Map<NodeId, Node>;
}
export interface Layering {
    layers: NodeId[][];
    rankOf: Record<NodeId, number>;
    dummy?: Set<NodeId>;
}
export interface OrderedLayers {
    layers: NodeId[][];
}
export interface Coordinates {
    x: Record<NodeId, number>;
    y: Record<NodeId, number>;
}
export type Edge = EdgeRef;
export declare const DEFAULT_SWIMLANE_ID = "__swimlane_default__";
export interface WriteBackOptions {
    layerGap?: number;
    nodeGap?: number;
}
export declare function prepareLayoutForSwimlanes(layout: LayoutData): void;
/**
 * The graph the Sugiyama phases lay out. Edge-label nodes and their layout-only
 * edges are left out, and a labelled edge takes part as itself, so a label never
 * changes a node's rank. `assignCoordinates` places the labels.
 */
export declare function toGraphView(layout: LayoutData): Graph;
export declare function writeBackToLayoutData(g: Graph, ordered: OrderedLayers, coords: Coordinates, opts?: WriteBackOptions): void;
