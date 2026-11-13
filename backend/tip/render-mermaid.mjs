import path from "node:path";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import { mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { createSVGWindow } from "svgdom";

const require = createRequire(path.join(process.cwd(), "package.json"));
const { JSDOM } = require("jsdom");
const sharp = require("sharp");

let source = "";

for await (const chunk of process.stdin) {
  source += chunk;
  if (source.length > 50_000) {
    throw new Error("Mermaid source exceeds the size limit");
  }
}

if (!source.trim()) {
  throw new Error("Mermaid source is empty");
}

const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  pretendToBeVisual: true,
});
const { window } = dom;

window.SVGElement.prototype.getBBox = function getBBox() {
  const measurement = createSVGWindow().document.documentElement;
  measurement.innerHTML = this.outerHTML;

  const element = measurement.firstElementChild;
  if (!element || typeof element.getBBox !== "function") {
    throw new Error("Cannot measure Mermaid SVG element");
  }

  const bounds = element.getBBox();

  return {
    x: bounds.x,
    y: bounds.y,
    width: bounds.width,
    height: bounds.height,
  };
};

window.SVGElement.prototype.getComputedTextLength =
  function getComputedTextLength() {
    return this.getBBox().width;
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
  Object.defineProperty(globalThis, name, {
    configurable: true,
    value,
    writable: true,
  });
}

try {
  const mermaidUrl = pathToFileURL(require.resolve("mermaid"));
  const { default: mermaid } = await import(mermaidUrl.href);

    mermaid.initialize({
    startOnLoad: false,
    securityLevel: "strict",
    theme: "default",
    themeVariables: {
      background: "#ffffff",
      primaryColor: "#e8eef8",
      primaryTextColor: "#111111",
      primaryBorderColor: "#334155",
      lineColor: "#334155",
      secondaryColor: "#f1f5f9",
      tertiaryColor: "#ffffff",
    },
    htmlLabels: false,
    flowchart: {
      htmlLabels: false,
      useMaxWidth: false,
    },
    class: {
      htmlLabels: false,
      useMaxWidth: false,
    },
  });

  const { svg } = await mermaid.render("tip-generated-diagram", source);

    const png = await sharp(Buffer.from(svg))
    .resize({ width: 1600 })
    .flatten({ background: "#ffffff" })
    .removeAlpha()
    .png()
    .toBuffer();

  const stats = await sharp(png).stats();
  const isSolidColor = stats.channels.every(
    (channel) => channel.min === channel.max,
  );


    if (isSolidColor) {
    const directory = await mkdtemp(
      path.join(tmpdir(), "tip-diagram-debug-"),
    );

    await writeFile(path.join(directory, "diagram.svg"), svg, "utf8");
    await writeFile(path.join(directory, "diagram.png"), png);

    throw new Error(
      `Rendering produced a single-color PNG. ` +
      `Local diagnostic files saved in: ${directory}`,
    );
  }

  process.stdout.write(png);

} finally {
  window.close();
}