import * as solid_js from 'solid-js';
import { Accessor, ValidComponent } from 'solid-js';
import { ElementOf, PolymorphicProps } from '../polymorphic/index.js';
import { PointerDownOutsideEvent, FocusOutsideEvent, InteractOutsideEvent } from '../primitives/create-interact-outside/index.js';
import '@kobalte/utils';

interface DismissableLayerOptions {
    /**
     * When `true`, hover/focus/click interactions will be disabled on elements outside
     * the layer. Users will need to click twice on outside elements to
     * interact with them: once to close the layer, and again to trigger the element.
     */
    disableOutsidePointerEvents?: boolean;
    /** A list of elements that should not dismiss the layer when interacted with. */
    excludedElements?: Array<Accessor<HTMLElement | undefined>>;
    /**
     * Event handler called when the escape key is down.
     * Can be prevented.
     */
    onEscapeKeyDown?: (event: KeyboardEvent) => void;
    /**
     * Event handler called when a `pointerdown` event happens outside the layer.
     * Can be prevented.
     */
    onPointerDownOutside?: (event: PointerDownOutsideEvent) => void;
    /**
     * Event handler called when the focus moves outside the layer.
     * Can be prevented.
     */
    onFocusOutside?: (event: FocusOutsideEvent) => void;
    /**
     * Event handler called when an interaction happens outside the layer.
     * Specifically, when a `pointerdown` event happens outside or focus moves outside of it.
     * Can be prevented.
     */
    onInteractOutside?: (event: InteractOutsideEvent) => void;
    /** Handler called when the layer should be dismissed. */
    onDismiss?: () => void;
    /** Whether to ignore the "top most layer" check on interact outside. */
    bypassTopMostLayerCheck?: boolean;
}
interface DismissableLayerCommonProps<T extends HTMLElement = HTMLElement> {
    ref: T | ((el: T) => void);
}
interface DismissableLayerRenderProps extends DismissableLayerCommonProps {
}
type DismissableLayerProps<T extends ValidComponent | HTMLElement = HTMLElement> = DismissableLayerOptions & Partial<DismissableLayerCommonProps<ElementOf<T>>>;
declare function DismissableLayer<T extends ValidComponent = "div">(props: PolymorphicProps<T, DismissableLayerProps<T>>): solid_js.JSX.Element;

export { DismissableLayer, DismissableLayerCommonProps, DismissableLayerOptions, DismissableLayerProps, DismissableLayerRenderProps };
