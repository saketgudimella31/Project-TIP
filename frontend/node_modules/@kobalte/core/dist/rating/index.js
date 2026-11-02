import { createDomCollectionItem, createDomCollection } from '../chunk/7CVNMTYF.js';
import { useLocale } from '../chunk/7TPOQ36Z.js';
import { FormControlLabel } from '../chunk/7ZHN3PYD.js';
import { createFormResetListener } from '../chunk/ANN3A2QM.js';
import { FormControlErrorMessage } from '../chunk/ICNSTULC.js';
export { FormControlErrorMessage as ErrorMessage } from '../chunk/ICNSTULC.js';
import { FormControlDescription, useFormControlContext, FORM_CONTROL_PROP_NAMES, createFormControl, FormControlContext } from '../chunk/YKGT7A57.js';
export { FormControlDescription as Description } from '../chunk/YKGT7A57.js';
import { createRegisterId } from '../chunk/E4R2EMM4.js';
import { createControllableSignal } from '../chunk/BLN63FDC.js';
import { Polymorphic } from '../chunk/6Y7B2NEO.js';
import { createComponent, mergeProps, spread, effect, style, memo, template } from 'solid-js/web';
import { mergeDefaultProps, visuallyHiddenStyles, createGenerateId, mergeRefs, isFunction, access, callHandler, EventKey } from '@kobalte/utils';
import { createContext, splitProps, createUniqueId, createSignal, onMount, createMemo, children, createEffect, onCleanup, useContext } from 'solid-js';
import { combineStyle } from '@solid-primitives/props';

var RatingContext = createContext();
function useRatingContext() {
  const context = useContext(RatingContext);
  if (context === void 0) {
    throw new Error("[kobalte]: `useRatingContext` must be used within a `Rating` component");
  }
  return context;
}

// src/rating/rating-control.tsx
function RatingControl(props) {
  const formControlContext = useFormControlContext();
  const context = useRatingContext();
  const defaultId = `${formControlContext.generateId("control")}`;
  const mergedProps = mergeDefaultProps({
    id: defaultId
  }, props);
  const [local, others] = splitProps(mergedProps, ["onPointerLeave"]);
  const onPointerLeave = (e) => {
    if (formControlContext.isDisabled() || formControlContext.isReadOnly())
      return;
    callHandler(e, local.onPointerLeave);
    if (e.pointerType === "touch") {
      return;
    }
    context.setHoveredValue(-1);
  };
  return createComponent(Polymorphic, mergeProps({
    as: "div",
    role: "presentation",
    onPointerLeave
  }, others));
}
var _tmpl$ = /* @__PURE__ */ template(`<input type="text" tabindex="-1">`);
function RatingHiddenInput(props) {
  const formControlContext = useFormControlContext();
  const context = useRatingContext();
  return (() => {
    const _el$ = _tmpl$();
    spread(_el$, mergeProps({
      get name() {
        return formControlContext.name();
      },
      get value() {
        return context.value();
      },
      get required() {
        return formControlContext.isRequired();
      },
      get disabled() {
        return formControlContext.isDisabled();
      },
      get readOnly() {
        return formControlContext.isReadOnly();
      }
    }, props), false, false);
    effect((_$p) => style(_el$, visuallyHiddenStyles, _$p));
    return _el$;
  })();
}
var RatingItemContext = createContext();
function useRatingItemContext() {
  const context = useContext(RatingItemContext);
  if (context === void 0) {
    throw new Error("[kobalte]: `useRatingItemContext` must be used within a `Rating.Item` component");
  }
  return context;
}

// src/rating/utils.ts
function clamp(value) {
  return Math.max(0, Math.min(1, value));
}
function pointFromTouch(e, type = "client") {
  const point = e.touches[0] || e.changedTouches[0];
  return { x: point[`${type}X`], y: point[`${type}Y`] };
}
function pointFromMouse(point, type = "client") {
  return { x: point[`${type}X`], y: point[`${type}Y`] };
}
var isTouchEvent = (event) => "touches" in event && event.touches.length > 0;
function getEventPoint(event, type = "client") {
  return isTouchEvent(event) ? pointFromTouch(event, type) : pointFromMouse(event, type);
}
function getRelativePoint(point, element) {
  const { left, top, width, height } = element.getBoundingClientRect();
  const offset = { x: point.x - left, y: point.y - top };
  const percent = { x: clamp(offset.x / width), y: clamp(offset.y / height) };
  function getPercentValue(options = {}) {
    const { dir = "ltr", orientation = "horizontal", inverted } = options;
    const invertX = typeof inverted === "object" ? inverted.x : inverted;
    const invertY = typeof inverted === "object" ? inverted.y : inverted;
    if (orientation === "horizontal") {
      return dir === "rtl" || invertX ? 1 - percent.x : percent.x;
    }
    return invertY ? 1 - percent.y : percent.y;
  }
  return { offset, percent, getPercentValue };
}

// src/rating/rating-item.tsx
function RatingItem(props) {
  let ref;
  const formControlContext = useFormControlContext();
  const RatingContext2 = useRatingContext();
  const defaultId = `${formControlContext.generateId("item")}-${createUniqueId()}`;
  const mergedProps = mergeDefaultProps({
    id: defaultId
  }, props);
  const [local, others] = splitProps(mergedProps, ["ref", "aria-labelledby", "aria-describedby", "onClick", "onKeyDown", "onPointerMove"]);
  createDomCollectionItem({
    getItem: () => ({
      ref: () => ref,
      disabled: formControlContext.isDisabled(),
      key: others.id,
      textValue: "",
      type: "item"
    })
  });
  const ariaLabelledBy = () => {
    return [local["aria-labelledby"], labelId(), local["aria-labelledby"] != null && others["aria-label"] != null ? others.id : void 0].filter(Boolean).join(" ") || void 0;
  };
  const ariaDescribedBy = () => {
    return [local["aria-describedby"], descriptionId(), RatingContext2.ariaDescribedBy()].filter(Boolean).join(" ") || void 0;
  };
  const {
    direction
  } = useLocale();
  const isLTR = () => direction() === "ltr";
  const [labelId, setLabelId] = createSignal();
  const [descriptionId, setDescriptionId] = createSignal();
  const index = () => ref ? RatingContext2.items().findIndex((v) => v.ref() === ref) : -1;
  const [value, setValue] = createSignal();
  const newValue = () => RatingContext2.isHovering() ? RatingContext2.hoveredValue() : RatingContext2.value();
  const equal = () => Math.ceil(newValue()) === value();
  const highlighted = () => value() <= newValue() || equal();
  const half = () => equal() && Math.abs(newValue() - value()) === 0.5;
  onMount(() => {
    setValue(direction() === "ltr" ? index() + 1 : RatingContext2.items().length - index());
  });
  const tabIndex = () => {
    if (formControlContext.isDisabled())
      return void 0;
    if (formControlContext.isReadOnly())
      equal() ? 0 : void 0;
    return equal() ? 0 : -1;
  };
  const focusItem = (index2) => RatingContext2.items()[Math.round(index2)].ref().focus();
  const setPrevValue = () => {
    const factor = RatingContext2.allowHalf() ? 0.5 : 1;
    const value2 = Math.max(0, RatingContext2.value() - factor);
    RatingContext2.setValue(value2);
    focusItem(Math.max(value2 - 1, 0));
  };
  const setNextValue = () => {
    const factor = RatingContext2.allowHalf() ? 0.5 : 1;
    const value2 = Math.min(RatingContext2.items().length, (RatingContext2.value() === -1 ? 0 : RatingContext2.value()) + factor);
    RatingContext2.setValue(value2);
    focusItem(value2 - 1);
  };
  const onClick = (e) => {
    callHandler(e, local.onClick);
    const value2 = RatingContext2.hoveredValue() === -1 ? index() + 1 : RatingContext2.hoveredValue();
    RatingContext2.setValue(value2);
    RatingContext2.setHoveredValue(-1);
    focusItem(value2 - 1);
  };
  const onPointerMove = (e) => {
    if (formControlContext.isDisabled() || formControlContext.isReadOnly())
      return;
    callHandler(e, local.onPointerMove);
    const point = getEventPoint(e);
    const relativePoint = getRelativePoint(point, e.currentTarget);
    const percentX = relativePoint.getPercentValue({
      orientation: RatingContext2.orientation(),
      dir: direction()
    });
    const isMidway = percentX < 0.5;
    const half2 = RatingContext2.allowHalf() && isMidway;
    const factor = half2 ? 0.5 : 0;
    RatingContext2.setHoveredValue(value() - factor);
  };
  const onKeyDown = (e) => {
    callHandler(e, local.onKeyDown);
    switch (e.key) {
      case EventKey.ArrowLeft:
      case EventKey.ArrowUp:
        e.preventDefault();
        if (isLTR()) {
          setPrevValue();
        } else {
          setNextValue();
        }
        break;
      case EventKey.ArrowRight:
      case EventKey.ArrowDown:
        e.preventDefault();
        if (isLTR()) {
          setNextValue();
        } else {
          setPrevValue();
        }
        break;
      case EventKey.Space:
        e.preventDefault();
        RatingContext2.setValue(newValue());
        break;
      case EventKey.Home:
        e.preventDefault();
        RatingContext2.setValue(1);
        break;
      case EventKey.End:
        e.preventDefault();
        RatingContext2.setValue(RatingContext2.items().length);
        break;
    }
  };
  const dataset = createMemo(() => ({
    ...formControlContext.dataset(),
    "data-checked": equal() ? "" : void 0,
    "data-half": half() ? "" : void 0,
    "data-highlighted": highlighted() ? "" : void 0
  }));
  const context = {
    state: {
      highlighted,
      half
    },
    dataset,
    generateId: createGenerateId(() => others.id),
    itemId: () => others.id,
    registerLabel: createRegisterId(setLabelId),
    registerDescription: createRegisterId(setDescriptionId)
  };
  return createComponent(RatingItemContext.Provider, {
    value: context,
    get children() {
      return createComponent(Polymorphic, mergeProps({
        as: "div",
        ref(r$) {
          const _ref$ = mergeRefs((el) => ref = el, local.ref);
          typeof _ref$ === "function" && _ref$(r$);
        },
        role: "radio",
        get tabIndex() {
          return tabIndex();
        },
        get ["aria-checked"]() {
          return equal();
        },
        get ["aria-required"]() {
          return formControlContext.isRequired() || void 0;
        },
        get ["aria-disabled"]() {
          return formControlContext.isDisabled() || void 0;
        },
        get ["aria-readonly"]() {
          return formControlContext.isReadOnly() || void 0;
        },
        get ["aria-labelledby"]() {
          return ariaLabelledBy();
        },
        get ["aria-describedby"]() {
          return ariaDescribedBy();
        },
        onClick,
        onPointerMove,
        onKeyDown
      }, dataset, others));
    }
  });
}
function RatingItemControl(props) {
  const context = useRatingItemContext();
  const defaultId = `${context.generateId("control")}`;
  const mergedProps = mergeDefaultProps({
    id: defaultId
  }, props);
  const [local, others] = splitProps(mergedProps, ["children"]);
  return createComponent(Polymorphic, mergeProps({
    as: "div",
    role: "presentation"
  }, others, {
    get children() {
      return createComponent(RatingItemControlChild, {
        get state() {
          return {
            highlighted: context.state.highlighted,
            half: context.state.half
          };
        },
        get children() {
          return local.children;
        }
      });
    }
  }));
}
function RatingItemControlChild(props) {
  const resolvedChildren = children(() => {
    const body = props.children;
    return isFunction(body) ? body(props.state) : body;
  });
  return memo(resolvedChildren);
}
function RatingItemDescription(props) {
  const context = useRatingItemContext();
  const mergedProps = mergeDefaultProps({
    id: context.generateId("description")
  }, props);
  createEffect(() => onCleanup(context.registerDescription(mergedProps.id)));
  return createComponent(Polymorphic, mergeProps({
    as: "div"
  }, () => context.dataset(), mergedProps));
}
function RatingItemLabel(props) {
  const context = useRatingItemContext();
  const mergedProps = mergeDefaultProps({
    id: context.generateId("label")
  }, props);
  const [local, others] = splitProps(mergedProps, ["style"]);
  createEffect(() => onCleanup(context.registerLabel(others.id)));
  return createComponent(Polymorphic, mergeProps({
    as: "label",
    get ["for"]() {
      return context.itemId();
    },
    get style() {
      return combineStyle(visuallyHiddenStyles, local.style);
    }
  }, () => context.dataset(), others));
}
function RatingLabel(props) {
  return createComponent(FormControlLabel, mergeProps({
    as: "span"
  }, props));
}
function RatingRoot(props) {
  let ref;
  const defaultId = `Rating-${createUniqueId()}`;
  const mergedProps = mergeDefaultProps({
    id: defaultId,
    orientation: "horizontal"
  }, props);
  const [local, formControlProps, others] = splitProps(mergedProps, ["ref", "value", "defaultValue", "onChange", "allowHalf", "orientation", "aria-labelledby", "aria-describedby"], FORM_CONTROL_PROP_NAMES);
  const [items, setItems] = createSignal([]);
  const {
    DomCollectionProvider
  } = createDomCollection({
    items,
    onItemsChange: setItems
  });
  const [hoveredValue, setHoveredValue] = createSignal(-1);
  const [value, setValue] = createControllableSignal({
    value: () => local.value,
    defaultValue: () => local.defaultValue ?? 0,
    onChange: (value2) => local.onChange?.(value2)
  });
  const {
    formControlContext
  } = createFormControl(formControlProps);
  createFormResetListener(() => ref, () => setValue(local.defaultValue));
  const ariaLabelledBy = () => {
    return formControlContext.getAriaLabelledBy(access(formControlProps.id), others["aria-label"], local["aria-labelledby"]);
  };
  const ariaDescribedBy = () => {
    return formControlContext.getAriaDescribedBy(local["aria-describedby"]);
  };
  const context = {
    value,
    setValue: (newValue) => {
      if (formControlContext.isReadOnly() || formControlContext.isDisabled()) {
        return;
      }
      setValue(newValue);
    },
    allowHalf: () => local.allowHalf,
    orientation: () => local.orientation,
    hoveredValue,
    setHoveredValue,
    isHovering: () => hoveredValue() > -1,
    ariaDescribedBy,
    items,
    setItems
  };
  return createComponent(DomCollectionProvider, {
    get children() {
      return createComponent(FormControlContext.Provider, {
        value: formControlContext,
        get children() {
          return createComponent(RatingContext.Provider, {
            value: context,
            get children() {
              return createComponent(Polymorphic, mergeProps({
                as: "div",
                ref(r$) {
                  const _ref$ = mergeRefs((el) => ref = el, local.ref);
                  typeof _ref$ === "function" && _ref$(r$);
                },
                role: "radiogroup",
                get id() {
                  return access(formControlProps.id);
                },
                get ["aria-invalid"]() {
                  return formControlContext.validationState() === "invalid" || void 0;
                },
                get ["aria-required"]() {
                  return formControlContext.isRequired() || void 0;
                },
                get ["aria-disabled"]() {
                  return formControlContext.isDisabled() || void 0;
                },
                get ["aria-readonly"]() {
                  return formControlContext.isReadOnly() || void 0;
                },
                get ["aria-orientation"]() {
                  return local.orientation;
                },
                get ["aria-labelledby"]() {
                  return ariaLabelledBy();
                },
                get ["aria-describedby"]() {
                  return ariaDescribedBy();
                }
              }, () => formControlContext.dataset(), others));
            }
          });
        }
      });
    }
  });
}

// src/rating/index.tsx
var Rating = Object.assign(RatingRoot, {
  Description: FormControlDescription,
  ErrorMessage: FormControlErrorMessage,
  Control: RatingControl,
  HiddenInput: RatingHiddenInput,
  ItemControl: RatingItemControl,
  ItemDescription: RatingItemDescription,
  ItemLabel: RatingItemLabel,
  Item: RatingItem,
  Label: RatingLabel
});

export { RatingControl as Control, RatingHiddenInput as HiddenInput, RatingItem as Item, RatingItemControl as ItemControl, RatingItemDescription as ItemDescription, RatingItemLabel as ItemLabel, RatingLabel as Label, Rating, RatingRoot as Root };
