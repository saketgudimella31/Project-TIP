import type { LayoutData } from '../../../types.js';
export type NodeSizes = Record<string, readonly [width: number, height: number]>;
/**
 * Lays out a swimlane fixture with its captured sizes, replacing the nodes named in
 * `measuredInViewer` by the sizes the dev viewer measures today (the captured files
 * predate its larger node padding, and the layouts differ).
 */
export declare function layOutFixture(name: string, measuredInViewer?: NodeSizes): Promise<LayoutData>;
/** Lays out a fixture that has no captured sizes file, from the sizes the dev viewer measures. */
export declare function layOutMeasured(name: string, measuredInViewer: NodeSizes): Promise<LayoutData>;
