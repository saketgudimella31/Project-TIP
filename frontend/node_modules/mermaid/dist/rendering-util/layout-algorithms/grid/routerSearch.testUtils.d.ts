import { type RouterSearchResult } from './routerSearch.js';
import type { RouterObstacle, RouterPoint, RouterRect } from './types.js';
export interface DenseOracleInput {
    bounds: RouterRect;
    obstacles: readonly RouterObstacle[];
    source: RouterPoint;
    target: RouterPoint;
}
export declare function findDenseOracleRoute(input: DenseOracleInput): RouterSearchResult | undefined;
