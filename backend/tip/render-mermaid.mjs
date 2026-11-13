import path from "node:path";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

const require = createRequire(path.join(process.cwd(), "package.json"));
const { Resvg } = require("@resvg/resvg-js");
const { JSDOM } = require("jsdom");

let source = "";
for await (const chunk of process.stdin) {
  source += chunk;
  if (source.length > 50_000) throw new Error("Mermaid source exceeds the size limit");
}

const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  pretendToBeVisual: true,
});
const { window } = dom;
window.SVGElement.prototype.getBBox = function getBBox() {
  const fontSize = Number.parseFloat(this.getAttribute("font-size")) || 16;
  const text = this.textContent?.trim() || "";
  const width = Number.parseFloat(this.getAttribute("width"))
    || Math.max(40, text.length * fontSize * 0.62 + 24);
  const height = Number.parseFloat(this.getAttribute("height"))
    || Math.max(30, fontSize * 1.5 + 16);
  return { x: 0, y: 0, width, height };
};
window.SVGElement.prototype.getComputedTextLength = function getComputedTextLength() {
  const fontSize = Number.parseFloat(this.getAttribute("font-size")) || 16;
  return (this.textContent?.length || 0) * fontSize * 0.62;
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

const mermaidUrl = pathToFileURL(require.resolve("mermaid"));
const { default: mermaid } = await import(mermaidUrl.href);
mermaid.initialize({
  startOnLoad: false,
  securityLevel: "strict",
  theme: "default",
  htmlLabels: false,
  flowchart: { htmlLabels: false, useMaxWidth: true },
});
const { svg } = await mermaid.render("tip-generated-diagram", source);
const png = new Resvg(svg, { fitTo: { mode: "width", value: 1600 } }).render().asPng();
process.stdout.write(png);
window.close();