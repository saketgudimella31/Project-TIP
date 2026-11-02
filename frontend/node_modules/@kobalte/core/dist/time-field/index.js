import { SpinButtonRoot } from '../chunk/LUHKRAPV.js';
import { useLocale, createFilter } from '../chunk/7TPOQ36Z.js';
import { FormControlLabel } from '../chunk/7ZHN3PYD.js';
import { createFormResetListener } from '../chunk/ANN3A2QM.js';
import { FormControlErrorMessage } from '../chunk/ICNSTULC.js';
export { FormControlErrorMessage as ErrorMessage } from '../chunk/ICNSTULC.js';
import { FormControlDescription, useFormControlContext, FORM_CONTROL_PROP_NAMES, createFormControl, FormControlContext } from '../chunk/YKGT7A57.js';
export { FormControlDescription as Description } from '../chunk/YKGT7A57.js';
import { createRegisterId } from '../chunk/E4R2EMM4.js';
import { createControllableSignal } from '../chunk/BLN63FDC.js';
import { Polymorphic } from '../chunk/6Y7B2NEO.js';
import { spread, mergeProps, effect, style, createComponent, memo, template, setAttribute, insert } from 'solid-js/web';
import { visuallyHiddenStyles, mergeDefaultProps, mergeRefs, createFocusManager, createGenerateId, access, isIOS, getActiveElement, callHandler, isMac, scrollIntoViewport, getScrollParent, getWindow } from '@kobalte/utils';
import { createContext, splitProps, createEffect, Index, createSignal, createUniqueId, createMemo, mergeProps as mergeProps$1, children, on, onCleanup, Show, useContext } from 'solid-js';
import { NumberParser } from '@internationalized/number';

var TimeFieldContext = createContext();
function useTimeFieldContext() {
  const context = useContext(TimeFieldContext);
  if (context === void 0) {
    throw new Error("[kobalte]: `useTimeFieldContext` must be used within a `TimeField` component");
  }
  return context;
}

// src/time-field/time-field-hidden-input.tsx
var _tmpl$ = /* @__PURE__ */ template(`<input type="text" tabindex="-1" aria-hidden="true">`);
function TimeFieldHiddenInput(props) {
  const formControlContext = useFormControlContext();
  const context = useTimeFieldContext();
  return (
    // biome-ignore lint/a11y/noAriaHiddenOnFocusable: it is not focusable.
    (() => {
      const _el$ = _tmpl$();
      _el$.addEventListener("change", (e) => context.setValue(parseTime(e.currentTarget.value)));
      spread(_el$, mergeProps({
        get name() {
          return formControlContext.name();
        },
        get value() {
          return context.formattedValue() || "";
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
    })()
  );
}
var parseTime = (value) => {
  const [time, period] = value.split(" ");
  const [hours, minutes, seconds] = time.split(":");
  const parsedHours = period === "PM" ? Number.parseInt(hours) + 12 : Number.parseInt(hours);
  const parsedMinutes = Number.parseInt(minutes);
  const parsedSeconds = Number.parseInt(seconds);
  return {
    hour: Number.isNaN(parsedHours) ? void 0 : parsedHours,
    minute: Number.isNaN(parsedMinutes) ? void 0 : parsedMinutes,
    second: Number.isNaN(parsedSeconds) ? void 0 : parsedSeconds
  };
};
function TimeFieldInput(props) {
  const formControlContext = useFormControlContext();
  const timeFieldContext = useTimeFieldContext();
  const mergedProps = mergeDefaultProps({
    id: timeFieldContext.generateId("input")
  }, props);
  const [local, others] = splitProps(mergedProps, ["ref", "children", "onKeyDown", "onFocusOut", "aria-labelledby", "aria-describedby"]);
  createEffect(() => timeFieldContext.setFieldAriaLabel(others["aria-label"]));
  createEffect(() => {
    timeFieldContext.setFieldAriaLabelledBy(formControlContext.getAriaLabelledBy(others.id, others["aria-label"], local["aria-labelledby"]));
  });
  createEffect(() => {
    timeFieldContext.setFieldAriaDescribedBy([local["aria-describedby"], timeFieldContext.ariaDescribedBy()].filter(Boolean).join(" "));
  });
  const {
    direction
  } = useLocale();
  const onKeyDown = (e) => {
    callHandler(e, local.onKeyDown);
    switch (e.key) {
      case "ArrowLeft":
        e.preventDefault();
        e.stopPropagation();
        if (direction() === "rtl") {
          timeFieldContext.focusManager().focusNext();
        } else {
          timeFieldContext.focusManager().focusPrevious();
        }
        break;
      case "ArrowRight":
        e.preventDefault();
        e.stopPropagation();
        if (direction() === "rtl") {
          timeFieldContext.focusManager().focusPrevious();
        } else {
          timeFieldContext.focusManager().focusNext();
        }
        break;
    }
  };
  const onFocusOut = (e) => {
    callHandler(e, local.onFocusOut);
    if (formControlContext.isDisabled() || formControlContext.isReadOnly()) {
      return;
    }
  };
  return createComponent(Polymorphic, mergeProps({
    as: "div",
    role: "presentation",
    ref(r$) {
      const _ref$ = mergeRefs(timeFieldContext.setInputRef, local.ref);
      typeof _ref$ === "function" && _ref$(r$);
    },
    get ["aria-labelledby"]() {
      return timeFieldContext.fieldAriaLabelledBy();
    },
    get ["aria-describedby"]() {
      return timeFieldContext.fieldAriaDescribedBy();
    },
    onKeyDown,
    onFocusOut
  }, () => formControlContext.dataset(), others, {
    get children() {
      return createComponent(Index, {
        get each() {
          return timeFieldContext.segments();
        },
        children: (segment) => local.children?.(segment)
      });
    }
  }));
}
function TimeFieldLabel(props) {
  return createComponent(FormControlLabel, mergeProps({
    as: "span"
  }, props));
}
var _tmpl$2 = /* @__PURE__ */ template(`<div>`);
function TimeFieldValueDescription() {
  const context = useTimeFieldContext();
  const defaultId = context.generateId("value-description");
  const isValid = () => context.value()?.toString() !== void 0;
  createEffect(() => {
    if (!isValid()) {
      return;
    }
    onCleanup(context.registerValueDescriptionId(defaultId));
  });
  return createComponent(Show, {
    get when() {
      return isValid();
    },
    get children() {
      const _el$ = _tmpl$2();
      setAttribute(_el$, "id", defaultId);
      _el$.style.setProperty("display", "none");
      insert(_el$, () => context.translations().selectedTimeDescription(context.formattedValue()));
      return _el$;
    }
  });
}

// src/time-field/time-field.intl.ts
var TIME_FIELD_INTL_MESSAGES = {
  hour: "hour",
  minute: "minute",
  second: "second",
  am: "AM",
  pm: "PM",
  dayPeriod: "AM/PM",
  timeZoneName: "time zone",
  selectedTimeDescription: (time) => `Selected Time: ${time}`
};

// src/time-field/time-field-root.tsx
function TimeFieldRoot(props) {
  const [ref, setRef] = createSignal();
  const defaultId = `time-field-${createUniqueId()}`;
  const mergedProps = mergeDefaultProps({
    id: defaultId,
    granularity: "minute",
    translations: TIME_FIELD_INTL_MESSAGES
  }, props);
  const [local, formControlProps, others] = splitProps(mergedProps, ["ref", "translations", "min", "max", "placeholder", "hourCycle", "granularity", "forceLeadingZeros", "validationState", "value", "defaultValue", "onChange", "aria-labelledby", "aria-describedby", "children"], FORM_CONTROL_PROP_NAMES);
  const [inputRef, setInputRef] = createSignal();
  const [valueDescriptionId, setValueDescriptionId] = createSignal();
  const [fieldAriaLabel, setFieldAriaLabel] = createSignal();
  const [fieldAriaLabelledBy, setFieldAriaLabelledBy] = createSignal();
  const [fieldAriaDescribedBy, setFieldAriaDescribedBy] = createSignal();
  const focusManager = createFocusManager(inputRef);
  const [value, _setValue] = createControllableSignal({
    value: () => local.value,
    defaultValue: () => local.defaultValue,
    // @ts-ignore
    onChange: (value2) => local.onChange?.(value2)
  });
  const setValue = (v) => {
    if (!v) {
      _setValue(void 0);
      return;
    }
    const newValue = {
      ...value()
    };
    if ("hour" in v)
      newValue.hour = v.hour;
    if ("minute" in v)
      newValue.minute = v.minute;
    if ("second" in v)
      newValue.second = v.second;
    _setValue(newValue);
  };
  createFormResetListener(ref, () => {
    setValue(local.defaultValue);
  });
  const validationState = createMemo(() => {
    if (local.validationState) {
      return local.validationState;
    }
    const minTime = Number.parseInt(`${(local.min?.hour ?? "00").toString().padStart(2, "0")}${(local.min?.minute ?? "00").toString().padStart(2, "0")}${(local.min?.second ?? "00").toString().padStart(2, "0")}`);
    const maxTime = Number.parseInt(`${(local.max?.hour ?? "23").toString().padStart(2, "0")}${(local.max?.minute ?? "59").toString().padStart(2, "0")}${(local.max?.second ?? "59").toString().padStart(2, "0")}`);
    const val = Number.parseInt(`${(value()?.hour ?? "00").toString().padStart(2, "0")}${(value()?.minute ?? "00").toString().padStart(2, "0")}${(value()?.second ?? "00").toString().padStart(2, "0")}`);
    if (val > maxTime || val < minTime)
      return "invalid";
    return void 0;
  });
  const {
    formControlContext
  } = createFormControl(mergeProps$1(formControlProps, {
    get validationState() {
      return validationState();
    }
  }));
  const resolvedGranularity = createMemo(() => {
    const granularity = props.granularity ?? "minute";
    if (typeof granularity === "object")
      return granularity;
    return {
      hour: true,
      minute: granularity === "minute" || granularity === "second",
      second: granularity === "second"
    };
  });
  const formattedValue = createMemo(() => {
    let hour = value()?.hour ?? 0;
    const pm = hour > 12;
    if (local.hourCycle === 12 && pm) {
      hour -= 12;
    }
    const padding = local.forceLeadingZeros ? 2 : 1;
    const segments2 = [];
    if (resolvedGranularity().hour) {
      segments2.push(hour.toString().padStart(padding, "0"));
    }
    if (resolvedGranularity().minute) {
      segments2.push((value()?.minute ?? 0).toString().padStart(padding, "0"));
    }
    if (resolvedGranularity().second) {
      segments2.push((value()?.second ?? 0).toString().padStart(padding, "0"));
    }
    let val = segments2.join(":");
    if (local.hourCycle === 12) {
      val += ` ${pm ? local.translations?.pm : local.translations?.am}`;
    }
    return val;
  });
  const ariaLabelledBy = () => {
    return formControlContext.getAriaLabelledBy(access(formControlProps.id), others["aria-label"], local["aria-labelledby"]);
  };
  const ariaDescribedBy = () => {
    return [valueDescriptionId(), formControlContext.getAriaDescribedBy(local["aria-describedby"])].filter(Boolean).join(" ") || void 0;
  };
  const segments = createMemo(() => {
    const seg = Object.keys(resolvedGranularity()).filter((k) => resolvedGranularity()[k]);
    if (seg.includes("hour") && local.hourCycle === 12)
      seg.push("dayPeriod");
    return seg;
  });
  const context = {
    translations: () => local.translations,
    value,
    setValue,
    hourCycle: () => local.hourCycle,
    resolvedGranularity,
    forceLeadingZeros: () => local.forceLeadingZeros ?? false,
    placeholder: () => local.placeholder,
    formattedValue,
    focusManager: () => focusManager,
    isDisabled: () => formControlContext.isDisabled() ?? false,
    ariaDescribedBy,
    inputRef,
    setInputRef,
    valueDescriptionId,
    registerValueDescriptionId: createRegisterId(setValueDescriptionId),
    generateId: createGenerateId(() => access(formControlProps.id)),
    segments,
    fieldAriaLabel,
    fieldAriaLabelledBy,
    fieldAriaDescribedBy,
    setFieldAriaLabel,
    setFieldAriaLabelledBy,
    setFieldAriaDescribedBy
  };
  return createComponent(FormControlContext.Provider, {
    value: formControlContext,
    get children() {
      return createComponent(TimeFieldContext.Provider, {
        value: context,
        get children() {
          return createComponent(Polymorphic, mergeProps({
            as: "div",
            ref(r$) {
              const _ref$ = mergeRefs(setRef, local.ref);
              typeof _ref$ === "function" && _ref$(r$);
            },
            role: "group",
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
            get ["aria-labelledby"]() {
              return ariaLabelledBy();
            },
            get ["aria-describedby"]() {
              return ariaDescribedBy();
            }
          }, () => formControlContext.dataset(), others, {
            get children() {
              return [memo(() => local.children), createComponent(TimeFieldValueDescription, {})];
            }
          }));
        }
      });
    }
  });
}
var _tmpl$3 = /* @__PURE__ */ template(`<span>:`);
var PAGE_STEP = {
  hour: 2,
  minute: 15,
  second: 15
};
function TimeFieldSegment(props) {
  let ref;
  const formControlContext = useFormControlContext();
  const context = useTimeFieldContext();
  const mergedProps = mergeDefaultProps({
    id: `${context.generateId("segment")}-${createUniqueId()}`
  }, props);
  const [local, others] = splitProps(mergedProps, ["ref", "segment", "onKeyDown", "onBeforeInput", "onInput", "onFocus", "children"]);
  const {
    locale
  } = useLocale();
  const resolvedChildren = children(() => local.children);
  let enteredKeys = "";
  let composition = "";
  const touchPropOverrides = createMemo(() => {
    return isIOS() ? {
      role: "textbox",
      "aria-valuemax": void 0,
      "aria-valuemin": void 0,
      "aria-valuetext": void 0,
      "aria-valuenow": void 0
    } : {};
  });
  const firstSegment = createMemo(() => context.segments()[0]);
  const name = createMemo(() => {
    return context.translations()[local.segment];
  });
  const ariaLabel = createMemo(() => {
    return [name(), context.fieldAriaLabel()].filter(Boolean).join(", ");
  });
  const ariaDescribedBy = createMemo(() => {
    if (local.segment !== firstSegment() && formControlContext.validationState() !== "invalid") {
      return void 0;
    }
    return context.fieldAriaDescribedBy();
  });
  const ariaLabelledBy = createMemo(() => {
    return [mergedProps.id, context.fieldAriaLabelledBy()].filter(Boolean).join(" ") || void 0;
  });
  const inputMode = createMemo(() => {
    return formControlContext.isDisabled() || local.segment === "dayPeriod" ? void 0 : "numeric";
  });
  const filter = createFilter({
    sensitivity: "base"
  });
  const numberParser = createMemo(() => {
    return new NumberParser(locale(), {
      maximumFractionDigits: 0
    });
  });
  const maxValue = () => local.segment === "hour" ? 23 : 59;
  const onBackspaceKeyDown = () => {
    if (local.segment !== "dayPeriod" && context.value()?.[local.segment] === void 0) {
      context.focusManager().focusPrevious();
      return;
    }
    if (local.segment === "dayPeriod") {
      if ((context.value()?.hour ?? 0) >= 12) {
        if (!formControlContext.isReadOnly())
          context.setValue({
            hour: context.value().hour - 12
          });
      } else
        context.focusManager().focusPrevious();
      return;
    }
    if (formControlContext.isReadOnly())
      return;
    let newValue = (context.value()?.[local.segment] ?? 0).toString().slice(0, -1);
    const parsed = numberParser().parse(newValue);
    newValue = parsed === 0 ? "" : newValue;
    if (newValue.length === 0 || parsed === 0) {
      context.setValue({
        [local.segment]: void 0
      });
    } else {
      context.setValue({
        [local.segment]: parsed
      });
    }
    enteredKeys = newValue;
  };
  const onKeyDown = (e) => {
    callHandler(e, local.onKeyDown);
    if (e.key === "a" && (isMac() ? e.metaKey : e.ctrlKey)) {
      e.preventDefault();
    }
    if (e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) {
      return;
    }
    switch (e.key) {
      case "Backspace":
      case "Delete": {
        e.preventDefault();
        e.stopPropagation();
        onBackspaceKeyDown();
        break;
      }
    }
  };
  const onInputBase = (key) => {
    if (formControlContext.isDisabled() || formControlContext.isReadOnly()) {
      return;
    }
    const newValue = enteredKeys + key;
    switch (local.segment) {
      case "dayPeriod":
        if (filter.startsWith(context.translations().am, key)) {
          if ((context.value()?.hour ?? 0) >= 12)
            context.setValue({
              hour: context.value().hour - 12
            });
        } else if (filter.startsWith(context.translations().pm, key)) {
          if ((context.value()?.hour ?? 0) < 12)
            context.setValue({
              hour: context.value().hour + 12
            });
        } else {
          break;
        }
        context.focusManager().focusNext();
        break;
      case "hour":
      case "minute":
      case "second": {
        if (!numberParser().isValidPartialNumber(newValue)) {
          return;
        }
        let numberValue = numberParser().parse(newValue);
        let allowsZero = true;
        if (local.segment === "hour" && context.hourCycle() === 12) {
          allowsZero = false;
          if (numberValue >= 12) {
            numberValue = numberParser().parse(key);
          }
          if ((context.value()?.hour ?? 0) >= 12) {
            numberValue += 12;
          }
        }
        if (numberValue > maxValue()) {
          numberValue = numberParser().parse(key);
        }
        if (Number.isNaN(numberValue))
          return;
        const shouldSetValue = numberValue !== 0 || allowsZero;
        if (shouldSetValue) {
          context.setValue({
            [local.segment]: numberValue
          });
        }
        if (Number(`${numberValue}0`) > maxValue() || newValue.length >= String(maxValue).length) {
          enteredKeys = "";
          if (shouldSetValue) {
            context.focusManager().focusNext();
          }
        } else {
          enteredKeys = newValue;
        }
        break;
      }
    }
  };
  const onBeforeInput = (e) => {
    callHandler(e, local.onBeforeInput);
    e.preventDefault();
    switch (e.inputType) {
      case "deleteContentBackward":
      case "deleteContentForward":
        if (local.segment !== "dayPeriod" && context.value()?.[local.segment] !== void 0 && !formControlContext.isReadOnly()) {
          onBackspaceKeyDown();
        }
        break;
      case "insertCompositionText":
        if (ref) {
          composition = ref.textContent;
          ref.textContent = ref.textContent;
        }
        break;
      default:
        if (e.data != null) {
          onInputBase(e.data);
        }
        break;
    }
  };
  const onInput = (e) => {
    callHandler(e, local.onInput);
    const {
      inputType,
      data
    } = e;
    if (ref && data != null) {
      switch (inputType) {
        case "insertCompositionText":
          ref.textContent = composition;
          if (filter.startsWith(context.translations().am, data) || filter.startsWith(context.translations().pm, data)) {
            onInputBase(data);
          }
          break;
      }
    }
  };
  const onFocus = (e) => {
    callHandler(e, local.onFocus);
    if (ref) {
      enteredKeys = "";
      scrollIntoViewport(ref, {
        containingElement: getScrollParent(ref)
      });
      const selection = getWindow(ref).getSelection();
      selection?.collapse(ref);
    }
  };
  const cycleDayPeriod = () => {
    if ((context.value()?.hour ?? 0) >= 12)
      context.setValue({
        hour: context.value().hour - 12
      });
    else
      context.setValue({
        hour: context.value().hour + 12
      });
  };
  const adjust = (delta) => {
    const hour = context.value()?.hour ?? context.placeholder()?.hour ?? 0;
    if (local.segment === "hour" && context.hourCycle() === 12) {
      const isPM = hour >= 12;
      const h12 = hour % 12;
      const next = (h12 + delta + 12) % 12;
      return next + (isPM ? 12 : 0);
    }
    const max = maxValue();
    return ((context.value()?.[local.segment] ?? context.placeholder()?.[local.segment] ?? 0) + delta + (max + 1)) % (max + 1);
  };
  const onIncrement = () => {
    enteredKeys = "";
    if (local.segment === "dayPeriod") {
      cycleDayPeriod();
      return;
    }
    context.setValue({
      [local.segment]: adjust(1)
    });
  };
  const onDecrement = () => {
    enteredKeys = "";
    if (local.segment === "dayPeriod") {
      cycleDayPeriod();
      return;
    }
    context.setValue({
      [local.segment]: adjust(-1)
    });
  };
  const onIncrementPage = () => {
    enteredKeys = "";
    if (local.segment === "dayPeriod") {
      cycleDayPeriod();
      return;
    }
    context.setValue({
      [local.segment]: adjust(PAGE_STEP[local.segment])
    });
  };
  const onDecrementPage = () => {
    enteredKeys = "";
    if (local.segment === "dayPeriod") {
      cycleDayPeriod();
      return;
    }
    context.setValue({
      [local.segment]: adjust(-PAGE_STEP[local.segment])
    });
  };
  const onDecrementToMin = () => {
    enteredKeys = "";
    if (local.segment === "dayPeriod") {
      cycleDayPeriod();
      return;
    }
    if (local.segment === "hour" && context.hourCycle() === 12) {
      if ((context.value()?.hour ?? 0) >= 12)
        context.setValue({
          hour: 12
        });
      else
        context.setValue({
          hour: 0
        });
    } else
      context.setValue({
        [local.segment]: 0
      });
  };
  const onIncrementToMax = () => {
    enteredKeys = "";
    if (local.segment === "dayPeriod") {
      cycleDayPeriod();
      return;
    }
    if (local.segment === "hour" && context.hourCycle() === 12) {
      if ((context.value()?.hour ?? 0) >= 12)
        context.setValue({
          hour: 24
        });
      else
        context.setValue({
          hour: 12
        });
    } else
      context.setValue({
        [local.segment]: maxValue()
      });
  };
  createEffect(on([() => ref, () => context.focusManager()], ([ref2, focusManager]) => {
    const element = ref2;
    onCleanup(() => {
      if (getActiveElement(element) === element) {
        const prev = focusManager.focusPrevious();
        if (!prev) {
          focusManager.focusNext();
        }
      }
    });
  }));
  const getValue = () => {
    if (local.segment === "dayPeriod")
      return context.translations()[(context.value()?.hour ?? context.placeholder()?.hour ?? 0) >= 12 ? "pm" : "am"];
    if (local.segment === "hour") {
      const val = context.value()?.hour ?? context.placeholder()?.hour;
      if (val === void 0)
        return void 0;
      if (context.hourCycle() === 12) {
        if (val > 12)
          return val - 12;
        if (val === 0)
          return 12;
      }
      return val;
    }
    return context.value()?.[local.segment] ?? context.placeholder()?.[local.segment];
  };
  const padding = () => local.segment !== "hour" ? 2 : context.forceLeadingZeros() ? 2 : 1;
  const textValue = () => (getValue()?.toString() ?? "-".padStart(padding(), "-")).padStart(padding(), "0");
  return [createComponent(SpinButtonRoot, mergeProps({
    ref(r$) {
      const _ref$ = mergeRefs((el) => ref = el, local.ref);
      typeof _ref$ === "function" && _ref$(r$);
    },
    get tabIndex() {
      return formControlContext.isDisabled() ? void 0 : 0;
    },
    get value() {
      return getValue();
    },
    get textValue() {
      return textValue();
    },
    minValue: 0,
    get maxValue() {
      return maxValue();
    },
    get validationState() {
      return formControlContext.validationState();
    },
    get required() {
      return formControlContext.isRequired();
    },
    get disabled() {
      return formControlContext.isDisabled();
    },
    get readOnly() {
      return formControlContext.isReadOnly();
    },
    get contentEditable() {
      return !formControlContext.isReadOnly();
    },
    get inputMode() {
      return inputMode();
    },
    get autocorrect() {
      return !formControlContext.isReadOnly() ? "off" : void 0;
    },
    get autoCapitalize() {
      return !formControlContext.isReadOnly() ? "off" : void 0;
    },
    get spellcheck() {
      return !formControlContext.isReadOnly() ? false : void 0;
    },
    get enterkeyhint() {
      return !formControlContext.isReadOnly() ? "next" : void 0;
    },
    style: {
      "caret-color": "transparent"
    },
    get ["aria-label"]() {
      return ariaLabel();
    },
    get ["aria-labelledby"]() {
      return ariaLabelledBy();
    },
    get ["aria-describedby"]() {
      return ariaDescribedBy();
    },
    get ["data-placeholder"]() {
      return context.value()?.[local.segment === "dayPeriod" ? "hour" : local.segment] === void 0 ? "" : void 0;
    },
    get ["data-type"]() {
      return local.segment;
    },
    onKeyDown,
    onBeforeInput,
    onInput,
    onFocus,
    onIncrement,
    onDecrement,
    onIncrementPage,
    onDecrementPage,
    onDecrementToMin,
    onIncrementToMax
  }, () => formControlContext.dataset(), others, touchPropOverrides, {
    get children() {
      return createComponent(Show, {
        get when() {
          return resolvedChildren();
        },
        get fallback() {
          return textValue().replaceAll("-", "\u2013");
        },
        get children() {
          return resolvedChildren();
        }
      });
    }
  })), createComponent(Show, {
    get when() {
      return memo(() => local.segment === "hour")() && (context.resolvedGranularity().minute || context.resolvedGranularity().second) || local.segment === "minute" && context.resolvedGranularity().second;
    },
    get children() {
      return _tmpl$3();
    }
  })];
}

// src/time-field/index.tsx
var TimeField = Object.assign(TimeFieldRoot, {
  Label: TimeFieldLabel,
  Input: TimeFieldInput,
  Segment: TimeFieldSegment,
  Description: FormControlDescription,
  ErrorMessage: FormControlErrorMessage,
  HiddenInput: TimeFieldHiddenInput
});

export { TimeFieldHiddenInput as HiddenInput, TimeFieldInput as Input, TimeFieldLabel as Label, TimeFieldRoot as Root, TimeFieldSegment as Segment, TimeField };
