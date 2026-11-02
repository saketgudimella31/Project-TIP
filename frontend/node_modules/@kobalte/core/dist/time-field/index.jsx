import {
  SpinButtonRoot
} from "../chunk/ZAGMEN2K.jsx";
import {
  createFilter,
  useLocale
} from "../chunk/LP6E37CW.jsx";
import "../chunk/JHMNWOLY.jsx";
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

// src/time-field/time-field-hidden-input.tsx
import { visuallyHiddenStyles } from "@kobalte/utils";

// src/time-field/time-field-context.tsx
import { createContext, useContext } from "solid-js";
var TimeFieldContext = createContext();
function useTimeFieldContext() {
  const context = useContext(TimeFieldContext);
  if (context === void 0) {
    throw new Error(
      "[kobalte]: `useTimeFieldContext` must be used within a `TimeField` component"
    );
  }
  return context;
}

// src/time-field/time-field-hidden-input.tsx
function TimeFieldHiddenInput(props) {
  const formControlContext = useFormControlContext();
  const context = useTimeFieldContext();
  return (
    // biome-ignore lint/a11y/noAriaHiddenOnFocusable: it is not focusable.
    <input
      type="text"
      tabIndex={-1}
      style={visuallyHiddenStyles}
      name={formControlContext.name()}
      value={context.formattedValue() || ""}
      required={formControlContext.isRequired()}
      disabled={formControlContext.isDisabled()}
      readOnly={formControlContext.isReadOnly()}
      aria-hidden="true"
      onChange={(e) => context.setValue(parseTime(e.currentTarget.value))}
      {...props}
    />
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

// src/time-field/time-field-input.tsx
import { callHandler, mergeDefaultProps, mergeRefs } from "@kobalte/utils";
import {
  Index,
  createEffect,
  splitProps
} from "solid-js";
function TimeFieldInput(props) {
  const formControlContext = useFormControlContext();
  const timeFieldContext = useTimeFieldContext();
  const mergedProps = mergeDefaultProps(
    {
      id: timeFieldContext.generateId("input")
    },
    props
  );
  const [local, others] = splitProps(mergedProps, [
    "ref",
    "children",
    "onKeyDown",
    "onFocusOut",
    "aria-labelledby",
    "aria-describedby"
  ]);
  createEffect(() => timeFieldContext.setFieldAriaLabel(others["aria-label"]));
  createEffect(() => {
    timeFieldContext.setFieldAriaLabelledBy(
      formControlContext.getAriaLabelledBy(
        others.id,
        others["aria-label"],
        local["aria-labelledby"]
      )
    );
  });
  createEffect(() => {
    timeFieldContext.setFieldAriaDescribedBy(
      [local["aria-describedby"], timeFieldContext.ariaDescribedBy()].filter(Boolean).join(" ")
    );
  });
  const { direction } = useLocale();
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
  return <Polymorphic
    as="div"
    role="presentation"
    ref={mergeRefs(timeFieldContext.setInputRef, local.ref)}
    aria-labelledby={timeFieldContext.fieldAriaLabelledBy()}
    aria-describedby={timeFieldContext.fieldAriaDescribedBy()}
    onKeyDown={onKeyDown}
    onFocusOut={onFocusOut}
    {...formControlContext.dataset()}
    {...others}
  ><Index each={timeFieldContext.segments()}>{(segment) => local.children?.(segment)}</Index></Polymorphic>;
}

// src/time-field/time-field-label.tsx
function TimeFieldLabel(props) {
  return <FormControlLabel
    as="span"
    {...props}
  />;
}

// src/time-field/time-field-root.tsx
import {
  access,
  createFocusManager,
  createGenerateId,
  mergeDefaultProps as mergeDefaultProps2,
  mergeRefs as mergeRefs2
} from "@kobalte/utils";
import {
  createMemo as createMemo2,
  createSignal,
  createUniqueId,
  mergeProps,
  splitProps as splitProps2
} from "solid-js";

// src/time-field/time-field-value-description.tsx
import { Show, createEffect as createEffect2, onCleanup } from "solid-js";
function TimeFieldValueDescription() {
  const context = useTimeFieldContext();
  const defaultId = context.generateId("value-description");
  const isValid = () => context.value()?.toString() !== void 0;
  createEffect2(() => {
    if (!isValid()) {
      return;
    }
    onCleanup(context.registerValueDescriptionId(defaultId));
  });
  return <Show when={isValid()}><div id={defaultId} style={{ display: "none" }}>{context.translations().selectedTimeDescription(context.formattedValue())}</div></Show>;
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
  const mergedProps = mergeDefaultProps2(
    {
      id: defaultId,
      granularity: "minute",
      translations: TIME_FIELD_INTL_MESSAGES
    },
    props
  );
  const [local, formControlProps, others] = splitProps2(
    mergedProps,
    [
      "ref",
      "translations",
      "min",
      "max",
      "placeholder",
      "hourCycle",
      "granularity",
      "forceLeadingZeros",
      "validationState",
      "value",
      "defaultValue",
      "onChange",
      "aria-labelledby",
      "aria-describedby",
      "children"
    ],
    FORM_CONTROL_PROP_NAMES
  );
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
    const newValue = { ...value() };
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
  const validationState = createMemo2(() => {
    if (local.validationState) {
      return local.validationState;
    }
    const minTime = Number.parseInt(
      `${(local.min?.hour ?? "00").toString().padStart(2, "0")}${(local.min?.minute ?? "00").toString().padStart(2, "0")}${(local.min?.second ?? "00").toString().padStart(2, "0")}`
    );
    const maxTime = Number.parseInt(
      `${(local.max?.hour ?? "23").toString().padStart(2, "0")}${(local.max?.minute ?? "59").toString().padStart(2, "0")}${(local.max?.second ?? "59").toString().padStart(2, "0")}`
    );
    const val = Number.parseInt(
      `${(value()?.hour ?? "00").toString().padStart(2, "0")}${(value()?.minute ?? "00").toString().padStart(2, "0")}${(value()?.second ?? "00").toString().padStart(2, "0")}`
    );
    if (val > maxTime || val < minTime)
      return "invalid";
    return void 0;
  });
  const { formControlContext } = createFormControl(
    mergeProps(formControlProps, {
      get validationState() {
        return validationState();
      }
    })
  );
  const resolvedGranularity = createMemo2(() => {
    const granularity = props.granularity ?? "minute";
    if (typeof granularity === "object")
      return granularity;
    return {
      hour: true,
      minute: granularity === "minute" || granularity === "second",
      second: granularity === "second"
    };
  });
  const formattedValue = createMemo2(() => {
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
    return formControlContext.getAriaLabelledBy(
      access(formControlProps.id),
      others["aria-label"],
      local["aria-labelledby"]
    );
  };
  const ariaDescribedBy = () => {
    return [
      valueDescriptionId(),
      formControlContext.getAriaDescribedBy(local["aria-describedby"])
    ].filter(Boolean).join(" ") || void 0;
  };
  const segments = createMemo2(() => {
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
  return <FormControlContext.Provider value={formControlContext}><TimeFieldContext.Provider value={context}><Polymorphic
    as="div"
    ref={mergeRefs2(setRef, local.ref)}
    role="group"
    id={access(formControlProps.id)}
    aria-invalid={formControlContext.validationState() === "invalid" || void 0}
    aria-required={formControlContext.isRequired() || void 0}
    aria-disabled={formControlContext.isDisabled() || void 0}
    aria-readonly={formControlContext.isReadOnly() || void 0}
    aria-labelledby={ariaLabelledBy()}
    aria-describedby={ariaDescribedBy()}
    {...formControlContext.dataset()}
    {...others}
  >
    {local.children}
    <TimeFieldValueDescription />
  </Polymorphic></TimeFieldContext.Provider></FormControlContext.Provider>;
}

// src/time-field/time-field-segment.tsx
import { NumberParser } from "@internationalized/number";
import {
  callHandler as callHandler2,
  getActiveElement,
  getScrollParent,
  getWindow,
  isIOS,
  isMac,
  mergeDefaultProps as mergeDefaultProps3,
  mergeRefs as mergeRefs3,
  scrollIntoViewport
} from "@kobalte/utils";
import {
  Show as Show2,
  children,
  createEffect as createEffect3,
  createMemo as createMemo3,
  createUniqueId as createUniqueId2,
  on,
  onCleanup as onCleanup2,
  splitProps as splitProps3
} from "solid-js";
var PAGE_STEP = {
  hour: 2,
  minute: 15,
  second: 15
};
function TimeFieldSegment(props) {
  let ref;
  const formControlContext = useFormControlContext();
  const context = useTimeFieldContext();
  const mergedProps = mergeDefaultProps3(
    {
      id: `${context.generateId("segment")}-${createUniqueId2()}`
    },
    props
  );
  const [local, others] = splitProps3(
    mergedProps,
    [
      "ref",
      "segment",
      "onKeyDown",
      "onBeforeInput",
      "onInput",
      "onFocus",
      "children"
    ]
  );
  const { locale } = useLocale();
  const resolvedChildren = children(() => local.children);
  let enteredKeys = "";
  let composition = "";
  const touchPropOverrides = createMemo3(() => {
    return isIOS() ? {
      role: "textbox",
      "aria-valuemax": void 0,
      "aria-valuemin": void 0,
      "aria-valuetext": void 0,
      "aria-valuenow": void 0
    } : {};
  });
  const firstSegment = createMemo3(() => context.segments()[0]);
  const name = createMemo3(() => {
    return context.translations()[local.segment];
  });
  const ariaLabel = createMemo3(() => {
    return [name(), context.fieldAriaLabel()].filter(Boolean).join(", ");
  });
  const ariaDescribedBy = createMemo3(() => {
    if (local.segment !== firstSegment() && formControlContext.validationState() !== "invalid") {
      return void 0;
    }
    return context.fieldAriaDescribedBy();
  });
  const ariaLabelledBy = createMemo3(() => {
    return [mergedProps.id, context.fieldAriaLabelledBy()].filter(Boolean).join(" ") || void 0;
  });
  const inputMode = createMemo3(() => {
    return formControlContext.isDisabled() || local.segment === "dayPeriod" ? void 0 : "numeric";
  });
  const filter = createFilter({ sensitivity: "base" });
  const numberParser = createMemo3(() => {
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
          context.setValue({ hour: context.value().hour - 12 });
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
      context.setValue({ [local.segment]: void 0 });
    } else {
      context.setValue({ [local.segment]: parsed });
    }
    enteredKeys = newValue;
  };
  const onKeyDown = (e) => {
    callHandler2(e, local.onKeyDown);
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
            context.setValue({ hour: context.value().hour - 12 });
        } else if (filter.startsWith(context.translations().pm, key)) {
          if ((context.value()?.hour ?? 0) < 12)
            context.setValue({ hour: context.value().hour + 12 });
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
          context.setValue({ [local.segment]: numberValue });
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
    callHandler2(e, local.onBeforeInput);
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
    callHandler2(e, local.onInput);
    const { inputType, data } = e;
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
    callHandler2(e, local.onFocus);
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
      context.setValue({ hour: context.value().hour - 12 });
    else
      context.setValue({ hour: context.value().hour + 12 });
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
        context.setValue({ hour: 12 });
      else
        context.setValue({ hour: 0 });
    } else
      context.setValue({ [local.segment]: 0 });
  };
  const onIncrementToMax = () => {
    enteredKeys = "";
    if (local.segment === "dayPeriod") {
      cycleDayPeriod();
      return;
    }
    if (local.segment === "hour" && context.hourCycle() === 12) {
      if ((context.value()?.hour ?? 0) >= 12)
        context.setValue({ hour: 24 });
      else
        context.setValue({ hour: 12 });
    } else
      context.setValue({ [local.segment]: maxValue() });
  };
  createEffect3(
    on([() => ref, () => context.focusManager()], ([ref2, focusManager]) => {
      const element = ref2;
      onCleanup2(() => {
        if (getActiveElement(element) === element) {
          const prev = focusManager.focusPrevious();
          if (!prev) {
            focusManager.focusNext();
          }
        }
      });
    })
  );
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
  const textValue = () => (getValue()?.toString() ?? "-".padStart(padding(), "-")).padStart(
    padding(),
    "0"
  );
  return <>
    <SpinButtonRoot
      ref={mergeRefs3((el) => ref = el, local.ref)}
      tabIndex={formControlContext.isDisabled() ? void 0 : 0}
      value={getValue()}
      textValue={textValue()}
      minValue={0}
      maxValue={maxValue()}
      validationState={formControlContext.validationState()}
      required={formControlContext.isRequired()}
      disabled={formControlContext.isDisabled()}
      readOnly={formControlContext.isReadOnly()}
      contentEditable={!formControlContext.isReadOnly()}
      inputMode={inputMode()}
      autocorrect={!formControlContext.isReadOnly() ? "off" : void 0}
      autoCapitalize={!formControlContext.isReadOnly() ? "off" : void 0}
      spellcheck={!formControlContext.isReadOnly() ? false : void 0}
      enterkeyhint={!formControlContext.isReadOnly() ? "next" : void 0}
      style={{ "caret-color": "transparent" }}
      aria-label={ariaLabel()}
      aria-labelledby={ariaLabelledBy()}
      aria-describedby={ariaDescribedBy()}
      data-placeholder={context.value()?.[local.segment === "dayPeriod" ? "hour" : local.segment] === void 0 ? "" : void 0}
      data-type={local.segment}
      onKeyDown={onKeyDown}
      onBeforeInput={onBeforeInput}
      onInput={onInput}
      onFocus={onFocus}
      onIncrement={onIncrement}
      onDecrement={onDecrement}
      onIncrementPage={onIncrementPage}
      onDecrementPage={onDecrementPage}
      onDecrementToMin={onDecrementToMin}
      onIncrementToMax={onIncrementToMax}
      {...formControlContext.dataset()}
      {...others}
      {...touchPropOverrides()}
    ><Show2
      when={resolvedChildren()}
      fallback={textValue().replaceAll("-", "\u2013")}
    >{resolvedChildren()}</Show2></SpinButtonRoot>
    <Show2
      when={local.segment === "hour" && (context.resolvedGranularity().minute || context.resolvedGranularity().second) || local.segment === "minute" && context.resolvedGranularity().second}
    ><span>:</span></Show2>
  </>;
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
export {
  FormControlDescription as Description,
  FormControlErrorMessage as ErrorMessage,
  TimeFieldHiddenInput as HiddenInput,
  TimeFieldInput as Input,
  TimeFieldLabel as Label,
  TimeFieldRoot as Root,
  TimeFieldSegment as Segment,
  TimeField
};
