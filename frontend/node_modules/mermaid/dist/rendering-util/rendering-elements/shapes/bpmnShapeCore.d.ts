import type { D3Selection } from '../../../types.js';
import type { Node } from '../../types.js';
export declare const EVENT_DIAMETER = 36;
export declare const GATEWAY_SIZE = 50;
export declare const ACTIVITY_WIDTH = 100;
export declare const ACTIVITY_HEIGHT = 80;
export declare const LABEL_GAP = 6;
export declare const ICON_SIZE = 16;
export declare const BPMN_ICON_PREFIX = "bpmn";
export declare const EVENT_RINGS: {
    readonly start: {
        readonly rings: 1;
        readonly strokeWidth: 1.6;
    };
    readonly intermediate: {
        readonly rings: 2;
        readonly strokeWidth: 1.4;
    };
    readonly boundary: {
        readonly rings: 2;
        readonly strokeWidth: 1.4;
    };
    readonly end: {
        readonly rings: 1;
        readonly strokeWidth: 3.4;
    };
};
export type EventPosition = keyof typeof EVENT_RINGS;
export declare function ensureBpmnIcons(): Promise<void>;
export type BpmnNode = Node & {
    icon?: string;
    markers?: string[];
};
export declare function dataDirectionOf(node: Node): 'input' | 'output' | undefined;
export declare function isCollectionData(node: Node): boolean;
export declare function glyphSvg(icon: string, size: number): Promise<string>;
export interface LabelBox {
    width: number;
    height: number;
    x?: number;
    y?: number;
    top?: number;
    left?: number;
}
export declare const positionLabelBelow: (label: D3Selection<SVGGElement>, bbox: LabelBox, centerY: number) => void;
export declare const appendGlyph: (group: D3Selection<SVGGElement>, icon: string | undefined, size: number) => Promise<void>;
export declare const reserveBounds: (shapeSvg: D3Selection<SVGGElement>, node: Node, width: number, height: number, drawn?: {
    width: number;
    height: number;
}) => import("d3-selection").Selection<SVGRectElement, unknown, Element | null, unknown>;
export type ShapeFace = 'top' | 'bottom' | 'left' | 'right';
export declare const faceProjectIntersect: (node: Node, width: number, height: number, point: {
    x: number;
    y: number;
}, fixedFace?: ShapeFace) => {
    x: number;
    y: number;
};
export declare const ringIntersect: (node: Node, diameter: number, point: {
    x: number;
    y: number;
}) => {
    x: number;
    y: number;
};
export declare const faceCentreIntersect: (node: Node, width: number, height: number, point: {
    x: number;
    y: number;
}) => {
    x: number;
    y: number;
};
