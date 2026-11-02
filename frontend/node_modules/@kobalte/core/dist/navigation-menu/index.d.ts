import { Orientation } from '@kobalte/utils';
export { Orientation } from '@kobalte/utils';
import { t as MenuContentOptions, s as MenuContentCommonProps, v as MenuContentRenderProps, X as MenuItemProps, Z as MenuPortalProps, M as MenuCheckboxItem, b as MenuGroup, c as MenuGroupLabel, d as MenuIcon, f as MenuItemDescription, g as MenuItemIndicator, h as MenuItemLabel, j as MenuRadioGroup, k as MenuRadioItem, l as MenuSub, m as MenuSubContent, n as MenuSubTrigger } from '../menu-sub-trigger-29a7ad75.js';
export { o as NavigationMenuCheckboxItemCommonProps, p as NavigationMenuCheckboxItemOptions, q as NavigationMenuCheckboxItemProps, r as NavigationMenuCheckboxItemRenderProps, w as NavigationMenuGroupCommonProps, x as NavigationMenuGroupLabelCommonProps, y as NavigationMenuGroupLabelOptions, z as NavigationMenuGroupLabelProps, A as NavigationMenuGroupLabelRenderProps, B as NavigationMenuGroupOptions, C as NavigationMenuGroupProps, D as NavigationMenuGroupRenderProps, E as NavigationMenuIconCommonProps, F as NavigationMenuIconOptions, G as NavigationMenuIconProps, H as NavigationMenuIconRenderProps, I as NavigationMenuItemCommonProps, J as NavigationMenuItemDescriptionCommonProps, K as NavigationMenuItemDescriptionOptions, L as NavigationMenuItemDescriptionProps, N as NavigationMenuItemDescriptionRenderProps, O as NavigationMenuItemIndicatorCommonProps, P as NavigationMenuItemIndicatorOptions, Q as NavigationMenuItemIndicatorProps, R as NavigationMenuItemIndicatorRenderProps, S as NavigationMenuItemLabelCommonProps, T as NavigationMenuItemLabelOptions, U as NavigationMenuItemLabelProps, V as NavigationMenuItemLabelRenderProps, W as NavigationMenuItemOptions, Y as NavigationMenuItemRenderProps, _ as NavigationMenuRadioGroupCommonProps, $ as NavigationMenuRadioGroupOptions, a0 as NavigationMenuRadioGroupProps, a1 as NavigationMenuRadioGroupRenderProps, a2 as NavigationMenuRadioItemCommonProps, a3 as NavigationMenuRadioItemOptions, a4 as NavigationMenuRadioItemPRenderrops, a5 as NavigationMenuRadioItemProps, a6 as NavigationMenuSubContentCommonProps, a7 as NavigationMenuSubContentOptions, a8 as NavigationMenuSubContentProps, a9 as NavigationMenuSubContentRenderProps, aa as NavigationMenuSubOptions, ab as NavigationMenuSubProps, ac as NavigationMenuSubTriggerCommonProps, ad as NavigationMenuSubTriggerOptions, ae as NavigationMenuSubTriggerProps, af as NavigationMenuSubTriggerRenderProps } from '../menu-sub-trigger-29a7ad75.js';
import { S as SeparatorRoot } from '../separator-root-cb685406.js';
export { a as NavigationMenuSeparatorCommonProps, b as NavigationMenuSeparatorOptions, c as NavigationMenuSeparatorProps, d as NavigationMenuSeparatorRenderProps } from '../separator-root-cb685406.js';
import * as solid_js from 'solid-js';
import { ValidComponent, JSX, Setter, Accessor } from 'solid-js';
import { ElementOf, PolymorphicProps } from '../polymorphic/index.js';
import { a as PopperArrowOptions, c as PopperArrowCommonProps, d as PopperArrowRenderProps } from '../popper-arrow-89a19127.js';
import { c as MenubarMenuOptions, d as MenubarMenuProps, f as MenubarRootOptions, e as MenubarRootCommonProps, h as MenubarRootRenderProps, i as MenubarDataSet } from '../menubar-context-c1a81ca0.js';
import { b as PopperRootOptions, P as Placement } from '../popper-root-c2da235c.js';
import { MenuTriggerOptions, MenuTriggerCommonProps, MenuTriggerRenderProps } from '../menu/index.js';
import { DismissableLayerRenderProps } from '../dismissable-layer/index.js';
import { PointerDownOutsideEvent, FocusOutsideEvent, InteractOutsideEvent } from '../primitives/create-interact-outside/index.js';
import 'solid-js/web';
import '../create-list-state-d9a0f1f2.js';
import '../types-f8ae18e5.js';
import '../types-6adf33e1.js';
import '../button-root-da654b3e.js';
import '../utils-45fb8d63.js';

interface NavigationMenuArrowOptions extends PopperArrowOptions {
}
interface NavigationMenuArrowCommonProps<T extends HTMLElement = HTMLElement> extends PopperArrowCommonProps<T> {
}
interface NavigationMenuArrowRenderProps extends NavigationMenuArrowCommonProps, PopperArrowRenderProps {
}
type NavigationMenuArrowProps<T extends ValidComponent | HTMLElement = HTMLElement> = NavigationMenuArrowOptions & Partial<NavigationMenuArrowCommonProps<ElementOf<T>>>;
/**
 * An optional arrow element to render alongside the viewport content.
 * Must be rendered in the viewport.
 */
declare function NavigationMenuArrow<T extends ValidComponent = "div">(props: PolymorphicProps<T, NavigationMenuArrowProps<T>>): solid_js.JSX.Element;

type Motion = "to-start" | "to-end" | "from-start" | "from-end";
interface NavigationMenuContentOptions extends MenuContentOptions {
}
interface NavigationMenuContentCommonProps<T extends HTMLElement = HTMLElement> extends MenuContentCommonProps<T> {
    onPointerEnter: JSX.EventHandlerUnion<T, PointerEvent>;
    onPointerLeave: JSX.EventHandlerUnion<T, PointerEvent>;
}
interface NavigationMenuContentRenderProps extends MenuContentRenderProps, NavigationMenuContentCommonProps {
    "data-motion"?: Motion;
}
type NavigationMenuContentProps<T extends ValidComponent | HTMLElement = HTMLElement> = NavigationMenuContentOptions & Partial<NavigationMenuContentCommonProps<ElementOf<T>>>;
declare function NavigationMenuContent<T extends ValidComponent = "ul">(props: PolymorphicProps<T, NavigationMenuContentProps<T>>): JSX.Element;

/**
 * An item of the navigation menu.
 */
declare function NavigationMenuItem<T extends ValidComponent = "a">(props: PolymorphicProps<T, MenuItemProps<T>>): solid_js.JSX.Element;

interface NavigationMenuMenuOptions extends MenubarMenuOptions {
}
interface NavigationMenuMenuProps extends MenubarMenuProps {
}
/**
 * Displays a menu to the user —such as a set of actions or functions— triggered by a button.
 */
declare function NavigationMenuMenu(props: NavigationMenuMenuProps): solid_js.JSX.Element;

interface NavigationMenuPortalProps extends MenuPortalProps {
}
/**
 * Portals its children into the NavigationMenu.Viewport when the menu is open.
 */
declare function NavigationMenuPortal(props: NavigationMenuPortalProps): solid_js.JSX.Element;

interface NavigationMenuRootOptions extends MenubarRootOptions, Omit<PopperRootOptions, "anchorRef" | "contentRef" | "onCurrentPlacementChange"> {
    /**
     * Delay before the menu opens on hover (default 200).
     */
    delayDuration?: number;
    /**
     * Open immediately if hovered again within delay (default 300).
     */
    skipDelayDuration?: number;
    /**
     * Used to force mounting when more control is needed.
     * Useful when controlling animation with SolidJS animation libraries.
     */
    forceMount?: boolean;
    autoFocusMenu?: boolean;
    onAutoFocusMenuChange?: Setter<boolean>;
}
interface NavigationMenuRootCommonProps<T extends HTMLElement = HTMLElement> extends MenubarRootCommonProps<T> {
    ref: T | ((el: T) => void);
}
interface NavigationMenuRootRenderProps extends NavigationMenuRootCommonProps, MenubarRootRenderProps {
}
type NavigationMenuRootProps<T extends ValidComponent | HTMLElement = HTMLElement> = NavigationMenuRootOptions & Partial<NavigationMenuRootCommonProps<ElementOf<T>>>;
/**
 * A visually persistent menu common in desktop applications that provides quick access to a consistent set of commands.
 */
declare function NavigationMenuRoot<T extends ValidComponent = "ul">(props: PolymorphicProps<T, NavigationMenuRootProps<T>>): JSX.Element;

interface NavigationMenuTriggerOptions extends MenuTriggerOptions {
}
interface NavigationMenuTriggerCommonProps<T extends HTMLElement = HTMLElement> extends MenuTriggerCommonProps<T> {
    onPointerEnter: JSX.EventHandlerUnion<T, PointerEvent>;
    onPointerLeave: JSX.EventHandlerUnion<T, PointerEvent>;
}
interface NavigationMenuTriggerRenderProps extends NavigationMenuTriggerCommonProps, MenuTriggerRenderProps {
}
type NavigationMenuTriggerProps<T extends ValidComponent | HTMLElement = HTMLElement> = NavigationMenuTriggerOptions & Partial<NavigationMenuTriggerCommonProps<ElementOf<T>>>;
/**
 * The button that toggles the menubar menu or a menubar link.
 */
declare function NavigationMenuTrigger<T extends ValidComponent = "button">(props: PolymorphicProps<T, NavigationMenuTriggerProps<T>>): JSX.Element;

interface NavigationMenuViewportOptions {
    /**
     * Event handler called when the escape key is down.
     * It can be prevented by calling `event.preventDefault`.
     */
    onEscapeKeyDown?: (event: KeyboardEvent) => void;
    /**
     * Event handler called when a pointer event occurs outside the bounds of the component.
     * It can be prevented by calling `event.preventDefault`.
     */
    onPointerDownOutside?: (event: PointerDownOutsideEvent) => void;
    /**
     * Event handler called when the focus moves outside the bounds of the component.
     * It can be prevented by calling `event.preventDefault`.
     */
    onFocusOutside?: (event: FocusOutsideEvent) => void;
    /**
     * Event handler called when an interaction (pointer or focus event) happens outside the bounds of the component.
     * It can be prevented by calling `event.preventDefault`.
     */
    onInteractOutside?: (event: InteractOutsideEvent) => void;
}
interface NavigationMenuViewportCommonProps<T extends HTMLElement = HTMLElement> {
    ref: T | ((el: T) => void);
    style: JSX.CSSProperties | string;
}
interface NavigationMenuViewportRenderProps extends NavigationMenuViewportCommonProps, DismissableLayerRenderProps, MenubarDataSet {
    "data-orientation": Orientation;
}
type NavigationMenuViewportProps<T extends ValidComponent | HTMLElement = HTMLElement> = NavigationMenuViewportOptions & Partial<NavigationMenuViewportCommonProps<ElementOf<T>>>;
declare function NavigationMenuViewport<T extends ValidComponent = "li">(props: PolymorphicProps<T, NavigationMenuViewportProps<T>>): JSX.Element;

interface NavigationMenuDataSet {
    "data-expanded": string | undefined;
    "data-closed": string | undefined;
}
interface NavigationMenuContextValue {
    dataset: Accessor<NavigationMenuDataSet>;
    delayDuration: Accessor<number>;
    skipDelayDuration: Accessor<number>;
    autoFocusMenu: Accessor<boolean>;
    setAutoFocusMenu: Setter<boolean>;
    startLeaveTimer: () => void;
    cancelLeaveTimer: () => void;
    rootRef: Accessor<HTMLElement | undefined>;
    setRootRef: Setter<HTMLElement>;
    viewportRef: Accessor<HTMLElement | undefined>;
    setViewportRef: Setter<HTMLElement>;
    viewportPresent: Accessor<boolean>;
    currentPlacement: Accessor<Placement>;
    previousMenu: Accessor<string | undefined>;
    setPreviousMenu: Setter<string | undefined>;
}
declare function useNavigationMenuContext(): NavigationMenuContextValue;

declare const NavigationMenu: typeof NavigationMenuRoot & {
    Arrow: typeof NavigationMenuArrow;
    CheckboxItem: typeof MenuCheckboxItem;
    Content: typeof NavigationMenuContent;
    Group: typeof MenuGroup;
    GroupLabel: typeof MenuGroupLabel;
    Icon: typeof MenuIcon;
    Item: typeof NavigationMenuItem;
    ItemDescription: typeof MenuItemDescription;
    ItemIndicator: typeof MenuItemIndicator;
    ItemLabel: typeof MenuItemLabel;
    Portal: typeof NavigationMenuPortal;
    RadioGroup: typeof MenuRadioGroup;
    RadioItem: typeof MenuRadioItem;
    Menu: typeof NavigationMenuMenu;
    Separator: typeof SeparatorRoot;
    Sub: typeof MenuSub;
    SubContent: typeof MenuSubContent;
    SubTrigger: typeof MenuSubTrigger;
    Trigger: typeof NavigationMenuTrigger;
    Viewport: typeof NavigationMenuViewport;
};

export { NavigationMenuArrow as Arrow, MenuCheckboxItem as CheckboxItem, NavigationMenuContent as Content, MenuGroup as Group, MenuGroupLabel as GroupLabel, MenuIcon as Icon, NavigationMenuItem as Item, MenuItemDescription as ItemDescription, MenuItemIndicator as ItemIndicator, MenuItemLabel as ItemLabel, NavigationMenuMenu as Menu, Motion, NavigationMenu, NavigationMenuArrowCommonProps, NavigationMenuArrowOptions, NavigationMenuArrowProps, NavigationMenuArrowRenderProps, NavigationMenuContentCommonProps, NavigationMenuContentOptions, NavigationMenuContentProps, NavigationMenuContentRenderProps, NavigationMenuContextValue, MenuItemProps as NavigationMenuItemProps, NavigationMenuMenuOptions, NavigationMenuMenuProps, NavigationMenuPortalProps, NavigationMenuRootCommonProps, NavigationMenuRootOptions, NavigationMenuRootProps, NavigationMenuRootRenderProps, NavigationMenuTriggerCommonProps, NavigationMenuTriggerOptions, NavigationMenuTriggerProps, NavigationMenuTriggerRenderProps, NavigationMenuViewportCommonProps, NavigationMenuViewportOptions, NavigationMenuViewportProps, NavigationMenuViewportRenderProps, NavigationMenuPortal as Portal, MenuRadioGroup as RadioGroup, MenuRadioItem as RadioItem, NavigationMenuRoot as Root, SeparatorRoot as Separator, MenuSub as Sub, MenuSubContent as SubContent, MenuSubTrigger as SubTrigger, NavigationMenuTrigger as Trigger, NavigationMenuViewport as Viewport, useNavigationMenuContext };
