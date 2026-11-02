// src/common.ts
import { createMemo } from "solid-js";
function createClassnames(props) {
  return createMemo(() => {
    const name = props.name || "s";
    return {
      enterActive: (props.enterActiveClass || name + "-enter-active").split(" "),
      enter: (props.enterClass || name + "-enter").split(" "),
      enterTo: (props.enterToClass || name + "-enter-to").split(" "),
      exitActive: (props.exitActiveClass || name + "-exit-active").split(" "),
      exit: (props.exitClass || name + "-exit").split(" "),
      exitTo: (props.exitToClass || name + "-exit-to").split(" "),
      move: (props.moveClass || name + "-move").split(" ")
    };
  });
}
function nextFrame(fn) {
  requestAnimationFrame(() => requestAnimationFrame(fn));
}
function enterTransition(classes, events, el, done) {
  const { onBeforeEnter, onEnter, onAfterEnter } = events;
  onBeforeEnter?.(el);
  el.classList.add(...classes.enter);
  el.classList.add(...classes.enterActive);
  queueMicrotask(() => {
    if (!el.parentNode)
      return done?.();
    onEnter?.(el, () => endTransition());
  });
  nextFrame(() => {
    el.classList.remove(...classes.enter);
    el.classList.add(...classes.enterTo);
    if (!onEnter || onEnter.length < 2) {
      el.addEventListener("transitionend", endTransition);
      el.addEventListener("animationend", endTransition);
    }
  });
  function endTransition(e) {
    if (!e || e.target === el) {
      done?.();
      el.removeEventListener("transitionend", endTransition);
      el.removeEventListener("animationend", endTransition);
      el.classList.remove(...classes.enterActive);
      el.classList.remove(...classes.enterTo);
      onAfterEnter?.(el);
    }
  }
}
function exitTransition(classes, events, el, done) {
  const { onBeforeExit, onExit, onAfterExit } = events;
  if (!el.parentNode)
    return done?.();
  onBeforeExit?.(el);
  el.classList.add(...classes.exit);
  el.classList.add(...classes.exitActive);
  onExit?.(el, () => endTransition());
  nextFrame(() => {
    el.classList.remove(...classes.exit);
    el.classList.add(...classes.exitTo);
    if (!onExit || onExit.length < 2) {
      el.addEventListener("transitionend", endTransition);
      el.addEventListener("animationend", endTransition);
    }
  });
  function endTransition(e) {
    if (!e || e.target === el) {
      done?.();
      el.removeEventListener("transitionend", endTransition);
      el.removeEventListener("animationend", endTransition);
      el.classList.remove(...classes.exitActive);
      el.classList.remove(...classes.exitTo);
      onAfterExit?.(el);
    }
  }
}

// src/Transition.ts
import { createSwitchTransition } from "@solid-primitives/transition-group";
import { resolveFirst } from "@solid-primitives/refs";
var TRANSITION_MODE_MAP = {
  inout: "in-out",
  outin: "out-in"
};
var Transition = (props) => {
  const classnames = createClassnames(props);
  return createSwitchTransition(
    resolveFirst(() => props.children),
    {
      mode: TRANSITION_MODE_MAP[props.mode],
      appear: props.appear,
      onEnter(el, done) {
        enterTransition(classnames(), props, el, done);
      },
      onExit(el, done) {
        exitTransition(classnames(), props, el, done);
      }
    }
  );
};

// src/TransitionGroup.ts
import { createListTransition } from "@solid-primitives/transition-group";
import { resolveElements } from "@solid-primitives/refs";
var TransitionGroup = (props) => {
  const classnames = createClassnames(props);
  return createListTransition(resolveElements(() => props.children).toArray, {
    appear: props.appear,
    exitMethod: "keep-index",
    onChange({ added, removed, finishRemoved, list }) {
      const classes = classnames();
      for (const el of added) {
        enterTransition(classes, props, el);
      }
      const toMove = [];
      for (const el of list) {
        if (el.isConnected && (el instanceof HTMLElement || el instanceof SVGElement)) {
          toMove.push({ el, rect: el.getBoundingClientRect() });
        }
      }
      queueMicrotask(() => {
        const moved = [];
        for (const { el, rect } of toMove) {
          if (el.isConnected) {
            const newRect = el.getBoundingClientRect(), dX = rect.left - newRect.left, dY = rect.top - newRect.top;
            if (dX || dY) {
              el.style.transform = `translate(${dX}px, ${dY}px)`;
              el.style.transitionDuration = "0s";
              moved.push(el);
            }
          }
        }
        document.body.offsetHeight;
        for (const el of moved) {
          let endTransition2 = function(e) {
            if (e.target === el || /transform$/.test(e.propertyName)) {
              el.removeEventListener("transitionend", endTransition2);
              el.classList.remove(...classes.move);
            }
          };
          var endTransition = endTransition2;
          el.classList.add(...classes.move);
          el.style.transform = el.style.transitionDuration = "";
          el.addEventListener("transitionend", endTransition2);
        }
      });
      for (const el of removed) {
        exitTransition(classes, props, el, () => finishRemoved([el]));
      }
    }
  });
};
export {
  Transition,
  TransitionGroup
};
