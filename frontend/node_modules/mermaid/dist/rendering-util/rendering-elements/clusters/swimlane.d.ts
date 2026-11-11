export function swimlane(parent: any, node: any, { variant }?: {
    variant?: string | undefined;
}): Promise<{
    cluster: any;
    labelBBox: DOMRect;
}>;
