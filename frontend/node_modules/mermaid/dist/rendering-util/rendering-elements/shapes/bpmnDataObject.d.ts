import type { D3Selection } from '../../../types.js';
import type { Node } from '../../types.js';
export declare const DATA_WIDTH = 36;
export declare const DATA_HEIGHT = 50;
export declare function bpmnDataObject<T extends SVGGraphicsElement>(parent: D3Selection<T>, node: Node): Promise<D3Selection<SVGGElement>>;
