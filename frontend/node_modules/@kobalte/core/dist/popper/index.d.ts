import * as solid_js from 'solid-js';
import { Accessor, JSX, ValidComponent } from 'solid-js';
import { P as Placement, a as PopperRoot } from '../popper-root-c2da235c.js';
export { b as PopperRootOptions, c as PopperRootProps } from '../popper-root-c2da235c.js';
import { P as PopperArrow } from '../popper-arrow-89a19127.js';
export { c as PopperArrowCommonProps, a as PopperArrowOptions, b as PopperArrowProps, d as PopperArrowRenderProps } from '../popper-arrow-89a19127.js';
import { ElementOf, PolymorphicProps } from '../polymorphic/index.js';
import '@kobalte/utils';

interface PopperContextValue {
    currentPlacement: Accessor<Placement>;
    contentRef: Accessor<HTMLElement | undefined>;
    setPositionerRef: (el: HTMLElement) => void;
    setArrowRef: (el: HTMLElement) => void;
}
declare const PopperContext: solid_js.Context<PopperContextValue | undefined>;
declare function usePopperContext(): PopperContextValue;

interface PopperPositionerOptions {
}
interface PopperPositionerCommonProps<T extends HTMLElement = HTMLElement> {
    ref: T | ((el: T) => void);
    style?: JSX.CSSProperties | string;
}
interface PopperPositionerRenderProps extends PopperPositionerCommonProps {
    "data-popper-positioner": "";
}
type PopperPositionerProps<T extends ValidComponent | HTMLElement = HTMLElement> = PopperPositionerOptions & Partial<PopperPositionerCommonProps<ElementOf<T>>>;
/**
 * The wrapper component that positions the popper content relative to the popper anchor.
 */
declare function PopperPositioner<T extends ValidComponent = "div">(props: PolymorphicProps<T, PopperPositionerProps<T>>): JSX.Element;

declare const Popper: typeof PopperRoot & {
    Arrow: typeof PopperArrow;
    Context: solid_js.Context<PopperContextValue | undefined>;
    usePopperContext: typeof usePopperContext;
    Positioner: typeof PopperPositioner;
};

export { PopperArrow as Arrow, PopperContext as Context, Popper, PopperContextValue, PopperPositionerCommonProps, PopperPositionerOptions, PopperPositionerProps, PopperPositionerRenderProps, PopperPositioner as Positioner, PopperRoot as Root, usePopperContext };
