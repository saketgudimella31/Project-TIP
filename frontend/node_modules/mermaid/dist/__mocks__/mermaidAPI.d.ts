import type { Mock } from 'vitest';
export declare const mermaidAPI: {
    render: Mock;
    parse: {
        (text: string, parseOptions: import("../types.js").ParseOptions & {
            suppressErrors: true;
        }): Promise<import("../types.js").ParseResult | false>;
        (text: string, parseOptions?: import("../types.js").ParseOptions): Promise<import("../types.js").ParseResult>;
    };
    initialize: Mock;
    getConfig: () => import("../config.type.js").MermaidConfig;
    setConfig: (conf: import("../config.type.js").MermaidConfig) => import("../config.type.js").MermaidConfig;
    getSiteConfig: () => import("../config.type.js").MermaidConfig;
    updateSiteConfig: (conf: import("../config.type.js").MermaidConfig) => import("../config.type.js").MermaidConfig;
    reset: () => void;
    globalReset: () => void;
    defaultConfig: import("../config.type.js").MermaidConfig;
};
export default mermaidAPI;
