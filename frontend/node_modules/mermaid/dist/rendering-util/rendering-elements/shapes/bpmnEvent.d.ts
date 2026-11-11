import type { D3Selection } from '../../../types.js';
import type { Node } from '../../types.js';
import { type EventPosition } from './bpmnShapeCore.js';
export declare function renderBpmnEvent<T extends SVGGraphicsElement>(parent: D3Selection<T>, node: Node, position: EventPosition): Promise<D3Selection<SVGGElement>>;
