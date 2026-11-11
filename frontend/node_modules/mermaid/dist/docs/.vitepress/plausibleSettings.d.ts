type Env = Record<string, string | undefined>;
export interface PlausibleSettings {
    domain: string;
    endpoint: string;
}
/**
 * Where the docs report analytics: the Plausible site is the docs hostname (`mermaid.js.org`,
 * or `mermaid.ai` for `DOCS_SITE_URL=https://mermaid.ai/open-source/`), sent to
 * `DOCS_PLAUSIBLE_ENDPOINT` (default: the self-hosted Plausible at p.mermaid.live).
 */
export declare const getPlausibleSettings: (env?: Env) => PlausibleSettings;
export {};
