import { JSX, ValidComponent } from 'solid-js';
import { ElementOf, PolymorphicProps } from './polymorphic/index.js';

interface PopperArrowOptions {
    /** The size of the arrow. */
    size?: number;
}
interface PopperArrowCommonProps<T extends HTMLElement = HTMLElement> {
    ref: T | ((el: T) => void);
    style?: JSX.CSSProperties | string;
}
interface PopperArrowRenderProps extends PopperArrowCommonProps {
    children: JSX.Element;
    "aria-hidden": "true";
}
type PopperArrowProps<T extends ValidComponent | HTMLElement = HTMLElement> = PopperArrowOptions & Partial<PopperArrowCommonProps<ElementOf<T>>>;
/**
 * An optional arrow element to render alongside the popper content.
 * Must be rendered in the popper content.
 */
declare function PopperArrow<T extends ValidComponent = "div">(props: PolymorphicProps<T, PopperArrowProps<T>>): JSX.Element;

export { PopperArrow as P, PopperArrowOptions as a, PopperArrowProps as b, PopperArrowCommonProps as c, PopperArrowRenderProps as d };
