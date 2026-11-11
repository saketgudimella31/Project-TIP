type Env = Record<string, string | undefined>;
/**
 * The public URL the docs are deployed at, including any base path, e.g.
 * `DOCS_SITE_URL=https://mermaid.ai/open-source/`. Used for the VitePress `base`,
 * the sitemap, robots.txt and absolute links such as `og:url`.
 */
export declare const getSiteUrl: (env?: Env) => string;
export declare const getSiteBase: (siteUrl: string) => string;
/** The deployment hostname: `DOCS_HOSTNAME` if set, otherwise the host of the site URL. */
export declare const getDocsHostname: (env?: Env) => string;
/** The URL a page is served at, in the form VitePress uses for the sitemap. */
export declare const getPageUrl: (relativePath: string, siteUrl: string) => string;
export {};
