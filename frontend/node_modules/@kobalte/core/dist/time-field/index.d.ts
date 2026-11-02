import { F as FormControlDataSet, a as FormControlDescription } from '../form-control-description-330657bc.js';
export { c as TimeFieldDescriptionCommonProps, b as TimeFieldDescriptionOptions, e as TimeFieldDescriptionProps, d as TimeFieldDescriptionRenderProps } from '../form-control-description-330657bc.js';
import { F as FormControlErrorMessage } from '../form-control-error-message-9efcbea8.js';
export { b as TimeFieldErrorMessageCommonProps, a as TimeFieldErrorMessageOptions, d as TimeFieldErrorMessageProps, c as TimeFieldErrorMessageRenderProps } from '../form-control-error-message-9efcbea8.js';
import * as solid_js from 'solid-js';
import { ComponentProps, Accessor, JSX, ValidComponent } from 'solid-js';
import { ElementOf, PolymorphicProps } from '../polymorphic/index.js';
import { ValidationState } from '@kobalte/utils';
import { c as SpinButtonRootRenderProps } from '../spin-button-root-3a44420a.js';

interface TimeFieldHiddenInputProps extends ComponentProps<"input"> {
}
declare function TimeFieldHiddenInput(props: TimeFieldHiddenInputProps): solid_js.JSX.Element;

type TimeFieldGranularity = "hour" | "minute" | "second" | {
    hour: boolean;
    minute: boolean;
    second: boolean;
};
type TimeFieldHourCycle = 12 | 24;
type SegmentType = "hour" | "minute" | "second" | "dayPeriod";
interface Time {
    hour?: number;
    minute?: number;
    second?: number;
}

interface TimeFieldInputOptions {
    children?: (segment: Accessor<SegmentType>) => JSX.Element;
}
interface TimeFieldInputCommonProps<T extends HTMLElement = HTMLElement> {
    id: string;
    ref: T | ((el: T) => void);
    onKeyDown: JSX.EventHandlerUnion<T, KeyboardEvent>;
    onFocusOut: JSX.EventHandlerUnion<T, FocusEvent>;
    "aria-labelledby": string | undefined;
    "aria-describedby": string | undefined;
    "aria-label"?: string;
}
interface TimeFieldInputRenderProps extends TimeFieldInputCommonProps {
    role: "presentation";
    children: JSX.Element;
}
type TimeFieldInputProps<T extends ValidComponent | HTMLElement = HTMLElement> = TimeFieldInputOptions & Partial<TimeFieldInputCommonProps<ElementOf<T>>>;
declare function TimeFieldInput<T extends ValidComponent = "div">(props: PolymorphicProps<T, TimeFieldInputProps<T>>): JSX.Element;

interface TimeFieldLabelOptions {
}
interface TimeFieldLabelCommonProps<T extends HTMLElement = HTMLElement> {
}
interface TimeFieldLabelRenderProps extends TimeFieldLabelCommonProps {
}
type TimeFieldLabelProps<T extends ValidComponent | HTMLElement = HTMLElement> = TimeFieldLabelOptions & Partial<TimeFieldLabelCommonProps<ElementOf<T>>>;
declare function TimeFieldLabel<T extends ValidComponent = "span">(props: PolymorphicProps<T, TimeFieldLabelProps<T>>): solid_js.JSX.Element;

declare const TIME_FIELD_INTL_MESSAGES: {
    hour: string;
    minute: string;
    second: string;
    am: string;
    pm: string;
    dayPeriod: string;
    timeZoneName: string;
    selectedTimeDescription: (time: string) => string;
};
type TimeFieldIntlTranslations = typeof TIME_FIELD_INTL_MESSAGES;

interface TimeFieldRootOptions {
    /** The current value (controlled). */
    value?: Time;
    /** The default value (uncontrolled). */
    defaultValue?: Time;
    /** Handler that is called when the value changes. */
    onChange?: (value: Time) => void;
    /**
     * Whether to display the time in 12 or 24-hour format.
     * By default, this is determined by the user's locale.
     */
    hourCycle?: TimeFieldHourCycle;
    /**
     * Determines the smallest unit that is displayed in the time field.
     * Defaults to `"minute"`.
     */
    granularity?: TimeFieldGranularity;
    /**
     * Whether to always show leading zeros in the hour field.
     * Defaults to `false`
     */
    forceLeadingZeros?: boolean;
    /**
     * A placeholder time shown when no value is selected.
     */
    placeholder?: Time;
    /** The minimum allowed time that a user may select. */
    min?: Time;
    /** The maximum allowed time that a user may select. */
    max?: Time;
    /**
     * A unique identifier for the component.
     * The id is used to generate id attributes for nested components.
     * If no id prop is provided, a generated id will be used.
     */
    id?: string;
    /**
     * The name of the time field.
     * Submitted with its owning form as part of a name/value pair.
     */
    name?: string;
    /** Whether the time field should display its "valid" or "invalid" visual styling. */
    validationState?: ValidationState;
    /** Whether the time field is required. */
    required?: boolean;
    /** Whether the time field is disabled. */
    disabled?: boolean;
    /** Whether the time field is read only. */
    readOnly?: boolean;
    /** The localized strings of the component. */
    translations?: TimeFieldIntlTranslations;
}
interface TimeFieldRootCommonProps<T extends HTMLElement = HTMLElement> {
    id: string;
    ref: T | ((el: T) => void);
    "aria-labelledby": string | undefined;
    "aria-describedby": string | undefined;
    "aria-label"?: string;
    children: JSX.Element;
}
interface TimeFieldRootRenderProps extends TimeFieldRootCommonProps, FormControlDataSet {
    role: "group";
    "aria-invalid": boolean | undefined;
    "aria-required": boolean | undefined;
    "aria-disabled": boolean | undefined;
    "aria-readonly": boolean | undefined;
}
type TimeFieldRootProps<T extends ValidComponent | HTMLElement = HTMLElement> = TimeFieldRootOptions & Partial<TimeFieldRootCommonProps<ElementOf<T>>>;
declare function TimeFieldRoot<T extends ValidComponent = "div">(props: PolymorphicProps<T, TimeFieldRootProps<T>>): JSX.Element;

interface TimeFieldSegmentOptions {
    segment: SegmentType;
}
interface TimeFieldSegmentCommonProps<T extends HTMLElement = HTMLElement> {
    id: string;
    ref: T | ((el: T) => void);
    onBeforeInput: JSX.EventHandlerUnion<T, InputEvent>;
    onInput: JSX.EventHandlerUnion<T, InputEvent>;
    onKeyDown: JSX.EventHandlerUnion<T, KeyboardEvent>;
    onFocus: JSX.EventHandlerUnion<T, FocusEvent>;
    children: JSX.Element;
}
interface TimeFieldSegmentRenderProps extends TimeFieldSegmentCommonProps, SpinButtonRootRenderProps {
}
type TimeFieldSegmentProps<T extends ValidComponent | HTMLElement = HTMLElement> = TimeFieldSegmentOptions & Partial<TimeFieldSegmentCommonProps<ElementOf<T>>>;
declare function TimeFieldSegment<T extends ValidComponent = "div">(props: PolymorphicProps<T, TimeFieldSegmentProps<T>>): JSX.Element;

declare const TimeField: typeof TimeFieldRoot & {
    Label: typeof TimeFieldLabel;
    Input: typeof TimeFieldInput;
    Segment: typeof TimeFieldSegment;
    Description: typeof FormControlDescription;
    ErrorMessage: typeof FormControlErrorMessage;
    HiddenInput: typeof TimeFieldHiddenInput;
};

export { FormControlDescription as Description, FormControlErrorMessage as ErrorMessage, TimeFieldHiddenInput as HiddenInput, TimeFieldInput as Input, TimeFieldLabel as Label, TimeFieldRoot as Root, TimeFieldSegment as Segment, TimeField, TimeFieldHiddenInputProps, TimeFieldInputCommonProps, TimeFieldInputOptions, TimeFieldInputProps, TimeFieldInputRenderProps, TimeFieldLabelCommonProps, TimeFieldLabelOptions, TimeFieldLabelProps, TimeFieldLabelRenderProps, TimeFieldRootCommonProps, TimeFieldRootOptions, TimeFieldRootProps, TimeFieldRootRenderProps, TimeFieldSegmentCommonProps, TimeFieldSegmentOptions, TimeFieldSegmentProps, TimeFieldSegmentRenderProps };
