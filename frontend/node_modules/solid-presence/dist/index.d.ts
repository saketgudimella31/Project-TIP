import { MaybeAccessor } from '@corvu/utils/reactivity';
export { MaybeAccessor } from '@corvu/utils/reactivity';
import { Accessor } from 'solid-js';

/**
 * Manages the presence of an element in the DOM while being aware of pending animations.
 *
 * @param props.show - Whether the presence is showing.
 * @param props.element - The element which animations should be tracked.
 * @param props.onStateChange - Callback fired when the presence state changes.
 * @returns ```typescript
 * {
 *   present: Accessor<boolean>
 * }
 * ```
 */
declare const createPresence: (props: {
    show: MaybeAccessor<boolean>;
    element: MaybeAccessor<HTMLElement | null>;
    onStateChange?: (state: "present" | "hiding" | "hidden") => void;
}) => {
    present: Accessor<boolean>;
    state: Accessor<"present" | "hiding" | "hidden">;
};

export { createPresence as default };
