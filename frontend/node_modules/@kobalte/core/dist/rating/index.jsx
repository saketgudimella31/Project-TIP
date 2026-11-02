import {
  createDomCollection,
  createDomCollectionItem
} from "../chunk/SOM3K36D.jsx";
import {
  useLocale
} from "../chunk/LP6E37CW.jsx";
import {
  FormControlLabel
} from "../chunk/FOXVCQFV.jsx";
import {
  createFormResetListener
} from "../chunk/QJIB6BDF.jsx";
import {
  FormControlErrorMessage
} from "../chunk/ZZYKR3VO.jsx";
import {
  FORM_CONTROL_PROP_NAMES,
  FormControlContext,
  FormControlDescription,
  createFormControl,
  useFormControlContext
} from "../chunk/XUUROM4M.jsx";
import {
  createRegisterId
} from "../chunk/JNCCF6MP.jsx";
import {
  createControllableSignal
} from "../chunk/FN6EICGO.jsx";
import "../chunk/OYES4GOP.jsx";
import {
  Polymorphic
} from "../chunk/FLVHQV4A.jsx";
import "../chunk/5WXHJDCZ.jsx";

// src/rating/rating-control.tsx
import { callHandler, mergeDefaultProps } from "@kobalte/utils";
import { splitProps } from "solid-js";

// src/rating/rating-context.tsx
import {
  createContext,
  useContext
} from "solid-js";
var RatingContext = createContext();
function useRatingContext() {
  const context = useContext(RatingContext);
  if (context === void 0) {
    throw new Error(
      "[kobalte]: `useRatingContext` must be used within a `Rating` component"
    );
  }
  return context;
}

// src/rating/rating-control.tsx
function RatingControl(props) {
  const formControlContext = useFormControlContext();
  const context = useRatingContext();
  const defaultId = `${formControlContext.generateId("control")}`;
  const mergedProps = mergeDefaultProps(
    {
      id: defaultId
    },
    props
  );
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
  return <Polymorphic
    as="div"
    role="presentation"
    onPointerLeave={onPointerLeave}
    {...others}
  />;
}

// src/rating/rating-hidden-input.tsx
import { visuallyHiddenStyles } from "@kobalte/utils";
function RatingHiddenInput(props) {
  const formControlContext = useFormControlContext();
  const context = useRatingContext();
  return <input
    type="text"
    tabIndex={-1}
    style={visuallyHiddenStyles}
    name={formControlContext.name()}
    value={context.value()}
    required={formControlContext.isRequired()}
    disabled={formControlContext.isDisabled()}
    readOnly={formControlContext.isReadOnly()}
    {...props}
  />;
}

// src/rating/rating-item.tsx
import {
  EventKey,
  callHandler as callHandler2,
  createGenerateId,
  mergeDefaultProps as mergeDefaultProps2,
  mergeRefs
} from "@kobalte/utils";
import {
  createMemo,
  createSignal,
  createUniqueId,
  onMount,
  splitProps as splitProps2
} from "solid-js";

// src/rating/rating-item-context.tsx
import { createContext as createContext2, useContext as useContext2 } from "solid-js";
var RatingItemContext = createContext2();
function useRatingItemContext() {
  const context = useContext2(RatingItemContext);
  if (context === void 0) {
    throw new Error(
      "[kobalte]: `useRatingItemContext` must be used within a `Rating.Item` component"
    );
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
  const mergedProps = mergeDefaultProps2(
    {
      id: defaultId
    },
    props
  );
  const [local, others] = splitProps2(mergedProps, [
    "ref",
    "aria-labelledby",
    "aria-describedby",
    "onClick",
    "onKeyDown",
    "onPointerMove"
  ]);
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
    return [
      local["aria-labelledby"],
      labelId(),
      local["aria-labelledby"] != null && others["aria-label"] != null ? others.id : void 0
    ].filter(Boolean).join(" ") || void 0;
  };
  const ariaDescribedBy = () => {
    return [
      local["aria-describedby"],
      descriptionId(),
      RatingContext2.ariaDescribedBy()
    ].filter(Boolean).join(" ") || void 0;
  };
  const { direction } = useLocale();
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
    setValue(
      direction() === "ltr" ? index() + 1 : RatingContext2.items().length - index()
    );
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
    const value2 = Math.min(
      RatingContext2.items().length,
      (RatingContext2.value() === -1 ? 0 : RatingContext2.value()) + factor
    );
    RatingContext2.setValue(value2);
    focusItem(value2 - 1);
  };
  const onClick = (e) => {
    callHandler2(e, local.onClick);
    const value2 = RatingContext2.hoveredValue() === -1 ? index() + 1 : RatingContext2.hoveredValue();
    RatingContext2.setValue(value2);
    RatingContext2.setHoveredValue(-1);
    focusItem(value2 - 1);
  };
  const onPointerMove = (e) => {
    if (formControlContext.isDisabled() || formControlContext.isReadOnly())
      return;
    callHandler2(e, local.onPointerMove);
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
    callHandler2(e, local.onKeyDown);
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
    state: { highlighted, half },
    dataset,
    generateId: createGenerateId(() => others.id),
    itemId: () => others.id,
    registerLabel: createRegisterId(setLabelId),
    registerDescription: createRegisterId(setDescriptionId)
  };
  return <RatingItemContext.Provider value={context}><Polymorphic
    as="div"
    ref={mergeRefs((el) => ref = el, local.ref)}
    role="radio"
    tabIndex={tabIndex()}
    aria-checked={equal()}
    aria-required={formControlContext.isRequired() || void 0}
    aria-disabled={formControlContext.isDisabled() || void 0}
    aria-readonly={formControlContext.isReadOnly() || void 0}
    aria-labelledby={ariaLabelledBy()}
    aria-describedby={ariaDescribedBy()}
    onClick={onClick}
    onPointerMove={onPointerMove}
    onKeyDown={onKeyDown}
    {...dataset()}
    {...others}
  /></RatingItemContext.Provider>;
}

// src/rating/rating-item-control.tsx
import { isFunction, mergeDefaultProps as mergeDefaultProps3 } from "@kobalte/utils";
import { children, splitProps as splitProps3 } from "solid-js";
function RatingItemControl(props) {
  const context = useRatingItemContext();
  const defaultId = `${context.generateId("control")}`;
  const mergedProps = mergeDefaultProps3(
    {
      id: defaultId
    },
    props
  );
  const [local, others] = splitProps3(mergedProps, ["children"]);
  return <Polymorphic
    as="div"
    role="presentation"
    {...others}
  ><RatingItemControlChild
    state={{
      highlighted: context.state.highlighted,
      half: context.state.half
    }}
  >{local.children}</RatingItemControlChild></Polymorphic>;
}
function RatingItemControlChild(props) {
  const resolvedChildren = children(() => {
    const body = props.children;
    return isFunction(body) ? body(props.state) : body;
  });
  return <>{resolvedChildren()}</>;
}

// src/rating/rating-item-description.tsx
import { mergeDefaultProps as mergeDefaultProps4 } from "@kobalte/utils";
import { createEffect, onCleanup } from "solid-js";
function RatingItemDescription(props) {
  const context = useRatingItemContext();
  const mergedProps = mergeDefaultProps4(
    {
      id: context.generateId("description")
    },
    props
  );
  createEffect(() => onCleanup(context.registerDescription(mergedProps.id)));
  return <Polymorphic
    as="div"
    {...context.dataset()}
    {...mergedProps}
  />;
}

// src/rating/rating-item-label.tsx
import { mergeDefaultProps as mergeDefaultProps5, visuallyHiddenStyles as visuallyHiddenStyles2 } from "@kobalte/utils";
import { combineStyle } from "@solid-primitives/props";
import {
  createEffect as createEffect2,
  onCleanup as onCleanup2,
  splitProps as splitProps4
} from "solid-js";
function RatingItemLabel(props) {
  const context = useRatingItemContext();
  const mergedProps = mergeDefaultProps5(
    {
      id: context.generateId("label")
    },
    props
  );
  const [local, others] = splitProps4(mergedProps, ["style"]);
  createEffect2(() => onCleanup2(context.registerLabel(others.id)));
  return <Polymorphic
    as="label"
    for={context.itemId()}
    style={combineStyle(visuallyHiddenStyles2, local.style)}
    {...context.dataset()}
    {...others}
  />;
}

// src/rating/rating-label.tsx
function RatingLabel(props) {
  return <FormControlLabel
    as="span"
    {...props}
  />;
}

// src/rating/rating-root.tsx
import {
  access,
  mergeDefaultProps as mergeDefaultProps6,
  mergeRefs as mergeRefs2
} from "@kobalte/utils";
import {
  createSignal as createSignal2,
  createUniqueId as createUniqueId2,
  splitProps as splitProps5
} from "solid-js";
function RatingRoot(props) {
  let ref;
  const defaultId = `Rating-${createUniqueId2()}`;
  const mergedProps = mergeDefaultProps6(
    {
      id: defaultId,
      orientation: "horizontal"
    },
    props
  );
  const [local, formControlProps, others] = splitProps5(
    mergedProps,
    [
      "ref",
      "value",
      "defaultValue",
      "onChange",
      "allowHalf",
      "orientation",
      "aria-labelledby",
      "aria-describedby"
    ],
    FORM_CONTROL_PROP_NAMES
  );
  const [items, setItems] = createSignal2([]);
  const { DomCollectionProvider } = createDomCollection({
    items,
    onItemsChange: setItems
  });
  const [hoveredValue, setHoveredValue] = createSignal2(-1);
  const [value, setValue] = createControllableSignal({
    value: () => local.value,
    defaultValue: () => local.defaultValue ?? 0,
    onChange: (value2) => local.onChange?.(value2)
  });
  const { formControlContext } = createFormControl(formControlProps);
  createFormResetListener(
    () => ref,
    () => setValue(local.defaultValue)
  );
  const ariaLabelledBy = () => {
    return formControlContext.getAriaLabelledBy(
      access(formControlProps.id),
      others["aria-label"],
      local["aria-labelledby"]
    );
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
  return <DomCollectionProvider><FormControlContext.Provider value={formControlContext}><RatingContext.Provider value={context}><Polymorphic
    as="div"
    ref={mergeRefs2((el) => ref = el, local.ref)}
    role="radiogroup"
    id={access(formControlProps.id)}
    aria-invalid={formControlContext.validationState() === "invalid" || void 0}
    aria-required={formControlContext.isRequired() || void 0}
    aria-disabled={formControlContext.isDisabled() || void 0}
    aria-readonly={formControlContext.isReadOnly() || void 0}
    aria-orientation={local.orientation}
    aria-labelledby={ariaLabelledBy()}
    aria-describedby={ariaDescribedBy()}
    {...formControlContext.dataset()}
    {...others}
  /></RatingContext.Provider></FormControlContext.Provider></DomCollectionProvider>;
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
export {
  RatingControl as Control,
  FormControlDescription as Description,
  FormControlErrorMessage as ErrorMessage,
  RatingHiddenInput as HiddenInput,
  RatingItem as Item,
  RatingItemControl as ItemControl,
  RatingItemDescription as ItemDescription,
  RatingItemLabel as ItemLabel,
  RatingLabel as Label,
  Rating,
  RatingRoot as Root
};
