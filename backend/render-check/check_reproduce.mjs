import { JSDOM } from "jsdom";
import sharp from "sharp";
import { writeFile } from "node:fs/promises";
import { createSVGWindow } from "svgdom";

const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  pretendToBeVisual: true,
});
const { window } = dom;
window.SVGElement.prototype.getBBox = function () {
  const measurement = createSVGWindow().document.documentElement;
  measurement.innerHTML = this.outerHTML;
  const bounds = measurement.firstElementChild.getBBox();
  return { x: bounds.x, y: bounds.y, width: bounds.width, height: bounds.height };
};
window.SVGElement.prototype.getComputedTextLength = function () {
  return (this.textContent?.length || 0) * 16 * 0.62;
};
for (const [name, value] of Object.entries({
  window,
  document: window.document,
  DOMParser: window.DOMParser,
  XMLSerializer: window.XMLSerializer,
  Node: window.Node,
  Element: window.Element,
  HTMLElement: window.HTMLElement,
  SVGElement: window.SVGElement,
  CSSStyleSheet: window.CSSStyleSheet,
  navigator: window.navigator,
  getComputedStyle: window.getComputedStyle.bind(window),
})) {
  Object.defineProperty(globalThis, name, { configurable: true, value, writable: true });
}
const { default: mermaid } = await import("mermaid");
mermaid.initialize({
  startOnLoad: false,
  securityLevel: "strict",
  theme: "default",
  htmlLabels: false,
  flowchart: { htmlLabels: false, useMaxWidth: false },
});
const cases = {
  component: "flowchart LR\nShipping[Shipping Service] --> Users[User Service]",
  classes: "classDiagram\nclass ShippingService {\n+ship(order) boolean\n}\nShippingService --> UserService : calls",
  sequence: "sequenceDiagram\nShippingService->>UserService: validate user\nUserService-->>ShippingService: active",
};
for (const [name, source] of Object.entries(cases)) {
  const { svg } = await mermaid.render(`diagram-${name}`, source);
  await writeFile(`${name}.svg`, svg);
  const png = await sharp(Buffer.from(svg)).resize({ width: 1600 })
    .flatten({ background: "#ffffff" }).removeAlpha().png().toBuffer();
  await writeFile(`${name}.png`, png);
  const stats = await sharp(png).stats();
  console.log(name, svg.match(/viewBox="[^"]+"/)?.[0],
    stats.channels.map(({ min, max }) => ({ min, max })));
}
window.close();