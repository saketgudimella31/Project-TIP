import { createSVGWindow } from "svgdom";

const root = createSVGWindow().document.documentElement;
root.innerHTML = '<g transform="translate(200, 300)"><rect x="10" y="20" width="100" height="50"/></g>';
const bounds = root.getBBox();
if (bounds.x !== 210 || bounds.y !== 320 || bounds.width !== 100 || bounds.height !== 50) {
  throw new Error(`Incorrect SVG bounds: ${JSON.stringify(bounds)}`);
}
console.log("Transformed SVG bounds are correct");