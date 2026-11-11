import type { LayoutData } from '../../../types.js';
type Direction = 'LR' | 'RL';
export declare function applyBtDirectionTransform(layout: LayoutData): boolean;
/**
 * How far the LR/RL transform stretches the flow axis: the diagram's own nodes' average
 * width over their average height, never below 1. Edge labels and groups do not count, so a
 * label cannot stretch the flow axis.
 */
export declare function flowAxisStretch(nodes: readonly {
    width?: number;
    height?: number;
    isGroup?: boolean;
    isEdgeLabel?: boolean;
}[]): number;
export declare function applyLrDirectionTransform(layout: LayoutData, direction?: Direction): boolean;
export {};
