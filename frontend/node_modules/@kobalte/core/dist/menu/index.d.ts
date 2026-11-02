import { ah as MenuDataSet } from '../menu-sub-trigger-29a7ad75.js';
export { ak as Menu, M as MenuCheckboxItem, o as MenuCheckboxItemCommonProps, p as MenuCheckboxItemOptions, q as MenuCheckboxItemProps, r as MenuCheckboxItemRenderProps, a as MenuContent, s as MenuContentCommonProps, t as MenuContentOptions, u as MenuContentProps, v as MenuContentRenderProps, am as MenuContext, al as MenuContextValue, b as MenuGroup, w as MenuGroupCommonProps, c as MenuGroupLabel, x as MenuGroupLabelCommonProps, y as MenuGroupLabelOptions, z as MenuGroupLabelProps, A as MenuGroupLabelRenderProps, B as MenuGroupOptions, C as MenuGroupProps, D as MenuGroupRenderProps, d as MenuIcon, E as MenuIconCommonProps, F as MenuIconOptions, G as MenuIconProps, H as MenuIconRenderProps, e as MenuItem, I as MenuItemCommonProps, f as MenuItemDescription, J as MenuItemDescriptionCommonProps, K as MenuItemDescriptionOptions, L as MenuItemDescriptionProps, N as MenuItemDescriptionRenderProps, g as MenuItemIndicator, O as MenuItemIndicatorCommonProps, P as MenuItemIndicatorOptions, Q as MenuItemIndicatorProps, R as MenuItemIndicatorRenderProps, h as MenuItemLabel, S as MenuItemLabelCommonProps, T as MenuItemLabelOptions, U as MenuItemLabelProps, V as MenuItemLabelRenderProps, W as MenuItemOptions, X as MenuItemProps, Y as MenuItemRenderProps, ai as MenuOptions, i as MenuPortal, Z as MenuPortalProps, aj as MenuProps, j as MenuRadioGroup, _ as MenuRadioGroupCommonProps, $ as MenuRadioGroupOptions, a0 as MenuRadioGroupProps, a1 as MenuRadioGroupRenderProps, k as MenuRadioItem, a2 as MenuRadioItemCommonProps, a3 as MenuRadioItemOptions, a5 as MenuRadioItemProps, a4 as MenuRadioItemRenderProps, aq as MenuRoot, ag as MenuRootOptions, ap as MenuRootProps, l as MenuSub, m as MenuSubContent, a6 as MenuSubContentCommonProps, a7 as MenuSubContentOptions, a8 as MenuSubContentProps, a9 as MenuSubContentRenderProps, aa as MenuSubOptions, ab as MenuSubProps, n as MenuSubTrigger, ac as MenuSubTriggerCommonProps, ad as MenuSubTriggerOptions, ae as MenuSubTriggerProps, af as MenuSubTriggerRenderProps, ao as useMenuContext, an as useOptionalMenuContext } from '../menu-sub-trigger-29a7ad75.js';
import { Orientation } from '@kobalte/utils';
import { JSX, ValidComponent } from 'solid-js';
import { a as ButtonRootCommonProps, d as ButtonRootRenderProps } from '../button-root-da654b3e.js';
import { D as Direction } from '../utils-45fb8d63.js';
import { ElementOf, PolymorphicProps } from '../polymorphic/index.js';
import 'solid-js/web';
import '../popper-root-c2da235c.js';
import '../dismissable-layer/index.js';
import '../primitives/create-interact-outside/index.js';
import '../create-list-state-d9a0f1f2.js';
import '../types-f8ae18e5.js';
import '../types-6adf33e1.js';

interface MenuTriggerOptions {
}
interface MenuTriggerCommonProps<T extends HTMLElement = HTMLElement> extends ButtonRootCommonProps<T> {
    id: string;
    onPointerDown: JSX.EventHandlerUnion<T, PointerEvent>;
    onClick: JSX.EventHandlerUnion<T, MouseEvent>;
    onKeyDown: JSX.EventHandlerUnion<T, KeyboardEvent>;
    onMouseOver: JSX.EventHandlerUnion<T, MouseEvent>;
    onFocus: JSX.EventHandlerUnion<T, FocusEvent>;
}
interface MenuTriggerRenderProps extends MenuTriggerCommonProps, ButtonRootRenderProps, MenuDataSet {
    role: "menuitem" | undefined;
    "data-kb-menu-value-trigger": string | undefined;
}
type MenuTriggerProps<T extends ValidComponent | HTMLElement = HTMLElement> = MenuTriggerOptions & Partial<MenuTriggerCommonProps<ElementOf<T>>>;
declare const MENUBAR_KEYS: {
    next: (dir: Direction, orientation: Orientation) => "ArrowDown" | "ArrowRight" | "ArrowUp" | "ArrowLeft";
    previous: (dir: Direction, orientation: Orientation) => "ArrowDown" | "ArrowRight" | "ArrowUp" | "ArrowLeft";
};
/**
 * The button that toggles the menu.
 */
declare function MenuTrigger<T extends ValidComponent = "button">(props: PolymorphicProps<T, MenuTriggerProps<T>>): JSX.Element;

export { MENUBAR_KEYS, MenuDataSet, MenuTrigger, MenuTriggerCommonProps, MenuTriggerOptions, MenuTriggerProps, MenuTriggerRenderProps };
