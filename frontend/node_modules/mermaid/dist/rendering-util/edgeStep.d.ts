import type { Edge } from './types.js';
/** Seconds the travelling dot spends on one step when `flowchart.stepDuration` is not set. */
export declare const EDGE_STEP_DURATION = 1;
/** The configured step length in seconds, or the default when it is not a positive number. */
export declare const getStepDuration: (value: unknown) => number;
/** True when the edge takes part in the step animation (a positive integer `step`). */
export declare const isStepEdge: (edge: Pick<Edge, "step">) => edge is Pick<Edge, "step"> & {
    step: number;
};
