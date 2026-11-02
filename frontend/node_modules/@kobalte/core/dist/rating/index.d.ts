import { F as FormControlDataSet, a as FormControlDescription } from '../form-control-description-330657bc.js';
export { c as RatingDescriptionCommonProps, b as RatingDescriptionOptions, e as RatingDescriptionProps, d as RatingDescriptionRenderProps } from '../form-control-description-330657bc.js';
import { F as FormControlErrorMessage } from '../form-control-error-message-9efcbea8.js';
export { b as RatingErrorMessageCommonProps, a as RatingErrorMessageOptions, d as RatingErrorMessageProps, c as RatingErrorMessageRenderProps } from '../form-control-error-message-9efcbea8.js';
import * as solid_js from 'solid-js';
import { JSX, ValidComponent, ComponentProps, Accessor } from 'solid-js';
import { ElementOf, PolymorphicProps } from '../polymorphic/index.js';
import { Orientation, ValidationState } from '@kobalte/utils';

interface RatingControlOptions {
}
interface RatingControlCommonProps<T extends HTMLElement = HTMLElement> {
    id: string;
    onPointerLeave: JSX.EventHandlerUnion<T, PointerEvent>;
}
interface RatingControlRenderProps extends RatingControlCommonProps {
    role: "presentation";
}
type RatingControlProps<T extends ValidComponent | HTMLElement = HTMLElement> = RatingControlOptions & Partial<RatingControlCommonProps<ElementOf<T>>>;
declare function RatingControl<T extends ValidComponent = "div">(props: PolymorphicProps<T, RatingControlProps<T>>): JSX.Element;

interface RatingHiddenInputProps extends ComponentProps<"input"> {
}
declare function RatingHiddenInput(props: RatingHiddenInputProps): solid_js.JSX.Element;

interface RatingItemDataSet extends FormControlDataSet {
    "data-checked": string | undefined;
    "data-half": string | undefined;
    "data-highlighted": string | undefined;
}
interface RatingItemState {
    half: Accessor<boolean>;
    highlighted: Accessor<boolean>;
}

interface RatingItemOptions {
}
interface RatingItemCommonProps<T extends HTMLElement = HTMLElement> {
    id: string;
    ref: T | ((el: T) => void);
    "aria-labelledby": string | undefined;
    "aria-describedby": string | undefined;
    "aria-label"?: string;
    onClick: JSX.EventHandlerUnion<T, MouseEvent>;
    onKeyDown: JSX.EventHandlerUnion<T, KeyboardEvent>;
    onPointerMove: JSX.EventHandlerUnion<T, PointerEvent>;
}
interface RatingItemRenderProps extends RatingItemCommonProps, RatingItemDataSet {
    role: "radio";
    tabIndex: number | undefined;
    "aria-required": boolean | undefined;
    "aria-disabled": boolean | undefined;
    "aria-readonly": boolean | undefined;
    "aria-checked": boolean;
}
type RatingItemProps<T extends ValidComponent | HTMLElement = HTMLElement> = RatingItemOptions & Partial<RatingItemCommonProps<ElementOf<T>>>;
declare function RatingItem<T extends ValidComponent = "div">(props: PolymorphicProps<T, RatingItemProps<T>>): JSX.Element;

interface RatingItemControlOptions {
    /**
     * The children of the rating item.
     * Can be a `JSX.Element` or a _render prop_ for having access to the internal state.
     */
    children?: JSX.Element | ((state: RatingItemState) => JSX.Element);
}
interface RatingItemControlCommonProps<T extends HTMLElement = HTMLElement> {
    id: string;
}
interface RatingItemControlRenderProps extends RatingItemControlCommonProps {
    role: "presentation";
    children: JSX.Element;
}
type RatingItemControlProps<T extends ValidComponent | HTMLElement = HTMLElement> = RatingItemControlOptions & Partial<RatingItemControlCommonProps<ElementOf<T>>>;
declare function RatingItemControl<T extends ValidComponent = "div">(props: PolymorphicProps<T, RatingItemControlProps<T>>): JSX.Element;

interface RatingItemDescriptionOptions {
}
interface RatingItemDescriptionCommonProps<T extends HTMLElement = HTMLElement> {
    id: string;
}
interface RatingItemDescriptionRenderProps extends RatingItemDescriptionCommonProps, RatingItemDataSet {
}
type RatingItemDescriptionProps<T extends ValidComponent | HTMLElement = HTMLElement> = RatingItemDescriptionOptions & Partial<RatingItemDescriptionCommonProps<ElementOf<T>>>;
declare function RatingItemDescription<T extends ValidComponent = "div">(props: PolymorphicProps<T, RatingItemDescriptionProps<T>>): solid_js.JSX.Element;

interface RatingItemLabelOptions {
}
interface RatingItemLabelCommonProps<T extends HTMLElement = HTMLElement> {
    id: string;
    style: JSX.CSSProperties | string;
}
interface RatingItemLabelRenderProps extends RatingItemLabelCommonProps, RatingItemDataSet {
    for: string | undefined;
}
type RatingItemLabelProps<T extends ValidComponent | HTMLElement = HTMLElement> = RatingItemLabelOptions & Partial<RatingItemLabelCommonProps<ElementOf<T>>>;
declare function RatingItemLabel<T extends ValidComponent = "label">(props: PolymorphicProps<T, RatingItemLabelProps<T>>): JSX.Element;

interface RatingLabelOptions {
}
interface RatingLabelCommonProps<T extends HTMLElement = HTMLElement> {
}
interface RatingLabelRenderProps extends RatingLabelCommonProps {
}
type RatingLabelProps<T extends ValidComponent | HTMLElement = HTMLElement> = RatingLabelOptions & Partial<RatingLabelCommonProps<ElementOf<T>>>;
declare function RatingLabel<T extends ValidComponent = "span">(props: PolymorphicProps<T, RatingLabelProps<T>>): solid_js.JSX.Element;

interface RatingRootOptions {
    /** The current rating value. */
    value?: number;
    /**
     * The initial value of the rating when it is first rendered.
     * Use when you do not need to control the state of the rating.
     */
    defaultValue?: number;
    /** Event handler called when the value changes. */
    onChange?: (value: number) => void;
    /** Whether to allow half ratings. */
    allowHalf?: boolean;
    /** The axis the rating items should align with. */
    orientation?: Orientation;
    /**
     * A unique identifier for the component.
     * The id is used to generate id attributes for nested components.
     * If no id prop is provided, a generated id will be used.
     */
    id?: string;
    /**
     * The name of the rating.
     * Submitted with its owning form as part of a name/value pair.
     */
    name?: string;
    /** Whether the rating should display its "valid" or "invalid" visual styling. */
    validationState?: ValidationState;
    /** Whether the user must select an item before the owning form can be submitted. */
    required?: boolean;
    /** Whether the rating is disabled. */
    disabled?: boolean;
    /** Whether the rating is read only. */
    readOnly?: boolean;
}
interface RatingRootCommonProps<T extends HTMLElement = HTMLElement> {
    id: string;
    ref: T | ((el: T) => void);
    "aria-labelledby": string | undefined;
    "aria-describedby": string | undefined;
    "aria-label"?: string;
}
interface RatingRootRenderProps extends RatingRootCommonProps, FormControlDataSet {
    role: "radiogroup";
    "aria-invalid": boolean | undefined;
    "aria-required": boolean | undefined;
    "aria-disabled": boolean | undefined;
    "aria-readonly": boolean | undefined;
    "aria-orientation": Orientation | undefined;
}
type RatingRootProps<T extends ValidComponent | HTMLElement = HTMLElement> = RatingRootOptions & Partial<RatingRootCommonProps<ElementOf<T>>>;
declare function RatingRoot<T extends ValidComponent = "div">(props: PolymorphicProps<T, RatingRootProps<T>>): solid_js.JSX.Element;

declare const Rating: typeof RatingRoot & {
    Description: typeof FormControlDescription;
    ErrorMessage: typeof FormControlErrorMessage;
    Control: typeof RatingControl;
    HiddenInput: typeof RatingHiddenInput;
    ItemControl: typeof RatingItemControl;
    ItemDescription: typeof RatingItemDescription;
    ItemLabel: typeof RatingItemLabel;
    Item: typeof RatingItem;
    Label: typeof RatingLabel;
};

export { RatingControl as Control, FormControlDescription as Description, FormControlErrorMessage as ErrorMessage, RatingHiddenInput as HiddenInput, RatingItem as Item, RatingItemControl as ItemControl, RatingItemDescription as ItemDescription, RatingItemLabel as ItemLabel, RatingLabel as Label, Rating, RatingControlCommonProps, RatingControlOptions, RatingControlProps, RatingControlRenderProps, RatingHiddenInputProps, RatingItemCommonProps, RatingItemControlCommonProps, RatingItemControlOptions, RatingItemControlProps, RatingItemControlRenderProps, RatingItemDescriptionCommonProps, RatingItemDescriptionOptions, RatingItemDescriptionProps, RatingItemDescriptionRenderProps, RatingItemLabelCommonProps, RatingItemLabelOptions, RatingItemLabelProps, RatingItemLabelRenderProps, RatingItemOptions, RatingItemProps, RatingItemRenderProps, RatingLabelCommonProps, RatingLabelOptions, RatingLabelProps, RatingLabelRenderProps, RatingRootCommonProps, RatingRootOptions, RatingRootProps, RatingRootRenderProps, RatingRoot as Root };
