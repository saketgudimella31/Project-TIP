/**
 * Configuration constants for the Swimlanes layout algorithm.
 * Centralizes all magic numbers and default values for maintainability.
 */
/**
 * Edge routing and spacing constants
 */
export declare const EDGE_ROUTING: {
    /** Spacing between parallel edges in the same corridor (px) */
    readonly EDGE_GAP: 12;
    /** Horizontal offset from lane boundary to corridor center (px) */
    readonly LANE_MARGIN: 20;
    /** Edge of the square the point marker draws an arrowhead in (px); see markers.js */
    readonly ARROWHEAD_SIZE: 8;
    readonly ARROWHEAD_GAP: 4;
    /** Closest two edges may end on one face of a node: an arrowhead and the gap beside it (px) */
    readonly MIN_ARROWHEAD_SPACING: 12;
    readonly EDGE_STROKE_WIDTH: 2;
    /**
     * Distance under which a bend of one route and another route read as one stroke (px): the
     * gap kept between arrowheads plus the stroke width, the least a reader can see between two lines
     */
    readonly ROUTE_TOUCH_TOLERANCE: number;
};
/**
 * Numerical precision constants
 */
export declare const PRECISION: {
    /** Epsilon for floating-point comparisons */
    readonly EPSILON: 0.000001;
};
/**
 * Layer assignment constants
 */
export declare const LAYERING: {
    /** Default number of iterations for gravity-based layering */
    readonly GRAVITY_ITERATIONS: 8;
    /** Maximum number of passes for crossing-based rank optimization */
    readonly MAX_CROSSING_OPTIMIZATION_PASSES: 4;
    /** Whether to compact single-input nodes by default */
    readonly DEFAULT_COMPACT_SINGLE_INPUT: true;
};
/**
 * Coordinate assignment constants
 */
export declare const COORDINATES: {
    /** Default vertical gap between layers (px) */
    readonly DEFAULT_LAYER_GAP: 100;
    /** Default horizontal gap between nodes (px) */
    readonly DEFAULT_NODE_GAP: 40;
    /**
     * Room kept between an edge label and the nodes the edge joins (px). Anchoring
     * keeps a label 12 from an edge's endpoint and buffers it by 3 from other
     * geometry, so a label reserved between two ranks needs 15 to be anchored there;
     * 16 leaves one pixel to spare.
     */
    readonly EDGE_LABEL_CLEARANCE: 16;
};
