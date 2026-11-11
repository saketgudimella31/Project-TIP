export declare const ON_BOUNDARY_TOLERANCE = 1;
export type Axis = 'horizontal' | 'vertical';
export interface Box {
    x: number;
    y: number;
    width: number;
    height: number;
    shape?: string;
}
/** The axis an edge must travel along to meet the face at `p` head-on; undefined off the boundary. */
export declare function faceAxis(node: Box, p: {
    x: number;
    y: number;
}): Axis | undefined;
export declare function lastSegmentAxis(points: {
    x: number;
    y: number;
}[]): Axis;
