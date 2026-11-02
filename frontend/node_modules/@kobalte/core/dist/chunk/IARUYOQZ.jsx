import {
  DATA_TOP_LAYER_ATTR
} from "./3DLZMX4Z.jsx";

// src/primitives/create-interact-outside/create-interact-outside.ts
import {
  access,
  composeEventHandlers,
  getDocument,
  isCtrlKey,
  noop
} from "@kobalte/utils";
import { createEffect, onCleanup } from "solid-js";
import { isServer } from "solid-js/web";

// src/primitives/create-interact-outside/utils.ts
import { contains } from "@kobalte/utils";
function getEventTarget(event) {
  const path = typeof event.composedPath === "function" ? event.composedPath() : void 0;
  const target = path?.[0] ?? event.target;
  return target instanceof Element ? target : null;
}
function containsComposed(parent, child) {
  if (!parent) {
    return false;
  }
  let node = child;
  while (node) {
    if (contains(parent, node)) {
      return true;
    }
    const root = node.getRootNode();
    node = root instanceof ShadowRoot ? root.host : null;
  }
  return false;
}
function closestComposed(element, selector) {
  let node = element;
  while (node) {
    const match = node.closest(selector);
    if (match) {
      return match;
    }
    const root = node.getRootNode();
    node = root instanceof ShadowRoot ? root.host : null;
  }
  return null;
}

// src/primitives/create-interact-outside/create-interact-outside.ts
var POINTER_DOWN_OUTSIDE_EVENT = "interactOutside.pointerDownOutside";
var FOCUS_OUTSIDE_EVENT = "interactOutside.focusOutside";
function createInteractOutside(props, ref) {
  let pointerDownTimeoutId;
  let clickHandler = noop;
  const ownerDocument = () => getDocument(ref());
  const onPointerDownOutside = (e) => props.onPointerDownOutside?.(e);
  const onFocusOutside = (e) => props.onFocusOutside?.(e);
  const onInteractOutside = (e) => props.onInteractOutside?.(e);
  const isEventOutside = (e) => {
    const target = getEventTarget(e);
    if (!target) {
      return false;
    }
    if (closestComposed(target, `[${DATA_TOP_LAYER_ATTR}]`)) {
      return false;
    }
    if (!containsComposed(ownerDocument(), target)) {
      return false;
    }
    if (containsComposed(ref(), target)) {
      return false;
    }
    return !props.shouldExcludeElement?.(target);
  };
  const onPointerDown = (e) => {
    function handler() {
      const container = ref();
      const target = getEventTarget(e);
      if (!container || !target || !isEventOutside(e)) {
        return;
      }
      const handler2 = composeEventHandlers([
        onPointerDownOutside,
        onInteractOutside
      ]);
      target.addEventListener(POINTER_DOWN_OUTSIDE_EVENT, handler2, {
        once: true
      });
      const pointerDownOutsideEvent = new CustomEvent(
        POINTER_DOWN_OUTSIDE_EVENT,
        {
          bubbles: false,
          cancelable: true,
          detail: {
            originalEvent: e,
            isContextMenu: e.button === 2 || isCtrlKey(e) && e.button === 0
          }
        }
      );
      target.dispatchEvent(pointerDownOutsideEvent);
    }
    if (e.pointerType === "touch") {
      ownerDocument().removeEventListener("click", handler);
      clickHandler = handler;
      ownerDocument().addEventListener("click", handler, { once: true });
    } else {
      handler();
    }
  };
  const onFocusIn = (e) => {
    const container = ref();
    const target = getEventTarget(e);
    if (!container || !target || !isEventOutside(e)) {
      return;
    }
    const handler = composeEventHandlers([
      onFocusOutside,
      onInteractOutside
    ]);
    target.addEventListener(FOCUS_OUTSIDE_EVENT, handler, { once: true });
    const focusOutsideEvent = new CustomEvent(FOCUS_OUTSIDE_EVENT, {
      bubbles: false,
      cancelable: true,
      detail: {
        originalEvent: e,
        isContextMenu: false
      }
    });
    target.dispatchEvent(focusOutsideEvent);
  };
  createEffect(() => {
    if (isServer) {
      return;
    }
    if (access(props.isDisabled)) {
      return;
    }
    pointerDownTimeoutId = window.setTimeout(() => {
      ownerDocument().addEventListener("pointerdown", onPointerDown, true);
    }, 0);
    ownerDocument().addEventListener("focusin", onFocusIn, true);
    onCleanup(() => {
      window.clearTimeout(pointerDownTimeoutId);
      ownerDocument().removeEventListener("click", clickHandler);
      ownerDocument().removeEventListener("pointerdown", onPointerDown, true);
      ownerDocument().removeEventListener("focusin", onFocusIn, true);
    });
  });
}

export {
  createInteractOutside
};
