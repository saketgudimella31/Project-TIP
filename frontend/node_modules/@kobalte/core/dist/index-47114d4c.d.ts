import { P as PopperArrow, c as PopperArrowCommonProps, a as PopperArrowOptions, b as PopperArrowProps, d as PopperArrowRenderProps } from './popper-arrow-89a19127.js';
import { t as MenuContentOptions, s as MenuContentCommonProps, v as MenuContentRenderProps, ag as MenuRootOptions, M as MenuCheckboxItem, b as MenuGroup, c as MenuGroupLabel, d as MenuIcon, e as MenuItem, f as MenuItemDescription, g as MenuItemIndicator, h as MenuItemLabel, i as MenuPortal, j as MenuRadioGroup, k as MenuRadioItem, l as MenuSub, m as MenuSubContent, n as MenuSubTrigger, o as MenuCheckboxItemCommonProps, p as MenuCheckboxItemOptions, q as MenuCheckboxItemProps, r as MenuCheckboxItemRenderProps, w as MenuGroupCommonProps, x as MenuGroupLabelCommonProps, y as MenuGroupLabelOptions, z as MenuGroupLabelProps, A as MenuGroupLabelRenderProps, B as MenuGroupOptions, C as MenuGroupProps, D as MenuGroupRenderProps, E as MenuIconCommonProps, F as MenuIconOptions, G as MenuIconProps, H as MenuIconRenderProps, I as MenuItemCommonProps, J as MenuItemDescriptionCommonProps, K as MenuItemDescriptionOptions, L as MenuItemDescriptionProps, N as MenuItemDescriptionRenderProps, O as MenuItemIndicatorCommonProps, P as MenuItemIndicatorOptions, Q as MenuItemIndicatorProps, R as MenuItemIndicatorRenderProps, S as MenuItemLabelCommonProps, T as MenuItemLabelOptions, U as MenuItemLabelProps, V as MenuItemLabelRenderProps, W as MenuItemOptions, X as MenuItemProps, Y as MenuItemRenderProps, Z as MenuPortalProps, _ as MenuRadioGroupCommonProps, $ as MenuRadioGroupOptions, a0 as MenuRadioGroupProps, a1 as MenuRadioGroupRenderProps, a2 as MenuRadioItemCommonProps, a3 as MenuRadioItemOptions, a4 as MenuRadioItemRenderProps, a5 as MenuRadioItemProps, a6 as MenuSubContentCommonProps, a7 as MenuSubContentOptions, a8 as MenuSubContentProps, a9 as MenuSubContentRenderProps, aa as MenuSubOptions, ab as MenuSubProps, ac as MenuSubTriggerCommonProps, ad as MenuSubTriggerOptions, ae as MenuSubTriggerProps, af as MenuSubTriggerRenderProps } from './menu-sub-trigger-29a7ad75.js';
import { MenuTrigger, MenuTriggerCommonProps, MenuTriggerOptions, MenuTriggerProps, MenuTriggerRenderProps } from './menu/index.js';
import { S as SeparatorRoot, a as SeparatorRootCommonProps, b as SeparatorRootOptions, c as SeparatorRootProps, d as SeparatorRootRenderProps } from './separator-root-cb685406.js';
import * as solid_js from 'solid-js';
import { ValidComponent, ParentProps } from 'solid-js';
import { ElementOf, PolymorphicProps } from './polymorphic/index.js';

interface DropdownMenuContentOptions extends MenuContentOptions {
}
interface DropdownMenuContentCommonProps<T extends HTMLElement = HTMLElement> extends MenuContentCommonProps<T> {
}
interface DropdownMenuContentRenderProps extends DropdownMenuContentCommonProps, MenuContentRenderProps {
}
type DropdownMenuContentProps<T extends ValidComponent | HTMLElement = HTMLElement> = DropdownMenuContentOptions & Partial<DropdownMenuContentCommonProps<ElementOf<T>>>;
/**
 * Contains the content to be rendered when the dropdown menu is open.
 */
declare function DropdownMenuContent<T extends ValidComponent = "div">(props: PolymorphicProps<T, DropdownMenuContentProps<T>>): solid_js.JSX.Element;

interface DropdownMenuRootOptions extends MenuRootOptions {
}
interface DropdownMenuRootProps extends ParentProps<DropdownMenuRootOptions> {
}
/**
 * Displays a menu to the user —such as a set of actions or functions— triggered by a button.
 */
declare function DropdownMenuRoot(props: DropdownMenuRootProps): solid_js.JSX.Element;

declare const DropdownMenu: typeof DropdownMenuRoot & {
    Arrow: typeof PopperArrow;
    CheckboxItem: typeof MenuCheckboxItem;
    Content: typeof DropdownMenuContent;
    Group: typeof MenuGroup;
    GroupLabel: typeof MenuGroupLabel;
    Icon: typeof MenuIcon;
    Item: typeof MenuItem;
    ItemDescription: typeof MenuItemDescription;
    ItemIndicator: typeof MenuItemIndicator;
    ItemLabel: typeof MenuItemLabel;
    Portal: typeof MenuPortal;
    RadioGroup: typeof MenuRadioGroup;
    RadioItem: typeof MenuRadioItem;
    Separator: typeof SeparatorRoot;
    Sub: typeof MenuSub;
    SubContent: typeof MenuSubContent;
    SubTrigger: typeof MenuSubTrigger;
    Trigger: typeof MenuTrigger;
};

declare const index_DropdownMenu: typeof DropdownMenu;
type index_DropdownMenuContentCommonProps<T extends HTMLElement = HTMLElement> = DropdownMenuContentCommonProps<T>;
type index_DropdownMenuContentOptions = DropdownMenuContentOptions;
type index_DropdownMenuContentProps<T extends ValidComponent | HTMLElement = HTMLElement> = DropdownMenuContentProps<T>;
type index_DropdownMenuContentRenderProps = DropdownMenuContentRenderProps;
type index_DropdownMenuRootOptions = DropdownMenuRootOptions;
type index_DropdownMenuRootProps = DropdownMenuRootProps;
declare namespace index {
  export {
    PopperArrow as Arrow,
    MenuCheckboxItem as CheckboxItem,
    DropdownMenuContent as Content,
    index_DropdownMenu as DropdownMenu,
    PopperArrowCommonProps as DropdownMenuArrowCommonProps,
    PopperArrowOptions as DropdownMenuArrowOptions,
    PopperArrowProps as DropdownMenuArrowProps,
    PopperArrowRenderProps as DropdownMenuArrowRenderProps,
    MenuCheckboxItemCommonProps as DropdownMenuCheckboxItemCommonProps,
    MenuCheckboxItemOptions as DropdownMenuCheckboxItemOptions,
    MenuCheckboxItemProps as DropdownMenuCheckboxItemProps,
    MenuCheckboxItemRenderProps as DropdownMenuCheckboxItemRenderProps,
    index_DropdownMenuContentCommonProps as DropdownMenuContentCommonProps,
    index_DropdownMenuContentOptions as DropdownMenuContentOptions,
    index_DropdownMenuContentProps as DropdownMenuContentProps,
    index_DropdownMenuContentRenderProps as DropdownMenuContentRenderProps,
    MenuGroupCommonProps as DropdownMenuGroupCommonProps,
    MenuGroupLabelCommonProps as DropdownMenuGroupLabelCommonProps,
    MenuGroupLabelOptions as DropdownMenuGroupLabelOptions,
    MenuGroupLabelProps as DropdownMenuGroupLabelProps,
    MenuGroupLabelRenderProps as DropdownMenuGroupLabelRenderProps,
    MenuGroupOptions as DropdownMenuGroupOptions,
    MenuGroupProps as DropdownMenuGroupProps,
    MenuGroupRenderProps as DropdownMenuGroupRenderProps,
    MenuIconCommonProps as DropdownMenuIconCommonProps,
    MenuIconOptions as DropdownMenuIconOptions,
    MenuIconProps as DropdownMenuIconProps,
    MenuIconRenderProps as DropdownMenuIconRenderProps,
    MenuItemCommonProps as DropdownMenuItemCommonProps,
    MenuItemDescriptionCommonProps as DropdownMenuItemDescriptionCommonProps,
    MenuItemDescriptionOptions as DropdownMenuItemDescriptionOptions,
    MenuItemDescriptionProps as DropdownMenuItemDescriptionProps,
    MenuItemDescriptionRenderProps as DropdownMenuItemDescriptionRenderProps,
    MenuItemIndicatorCommonProps as DropdownMenuItemIndicatorCommonProps,
    MenuItemIndicatorOptions as DropdownMenuItemIndicatorOptions,
    MenuItemIndicatorProps as DropdownMenuItemIndicatorProps,
    MenuItemIndicatorRenderProps as DropdownMenuItemIndicatorRenderProps,
    MenuItemLabelCommonProps as DropdownMenuItemLabelCommonProps,
    MenuItemLabelOptions as DropdownMenuItemLabelOptions,
    MenuItemLabelProps as DropdownMenuItemLabelProps,
    MenuItemLabelRenderProps as DropdownMenuItemLabelRenderProps,
    MenuItemOptions as DropdownMenuItemOptions,
    MenuItemProps as DropdownMenuItemProps,
    MenuItemRenderProps as DropdownMenuItemRenderProps,
    MenuPortalProps as DropdownMenuPortalProps,
    MenuRadioGroupCommonProps as DropdownMenuRadioGroupCommonProps,
    MenuRadioGroupOptions as DropdownMenuRadioGroupOptions,
    MenuRadioGroupProps as DropdownMenuRadioGroupProps,
    MenuRadioGroupRenderProps as DropdownMenuRadioGroupRenderProps,
    MenuRadioItemCommonProps as DropdownMenuRadioItemCommonProps,
    MenuRadioItemOptions as DropdownMenuRadioItemOptions,
    MenuRadioItemRenderProps as DropdownMenuRadioItemPRenderrops,
    MenuRadioItemProps as DropdownMenuRadioItemProps,
    index_DropdownMenuRootOptions as DropdownMenuRootOptions,
    index_DropdownMenuRootProps as DropdownMenuRootProps,
    SeparatorRootCommonProps as DropdownMenuSeparatorCommonProps,
    SeparatorRootOptions as DropdownMenuSeparatorOptions,
    SeparatorRootProps as DropdownMenuSeparatorProps,
    SeparatorRootRenderProps as DropdownMenuSeparatorRenderProps,
    MenuSubContentCommonProps as DropdownMenuSubContentCommonProps,
    MenuSubContentOptions as DropdownMenuSubContentOptions,
    MenuSubContentProps as DropdownMenuSubContentProps,
    MenuSubContentRenderProps as DropdownMenuSubContentRenderProps,
    MenuSubOptions as DropdownMenuSubOptions,
    MenuSubProps as DropdownMenuSubProps,
    MenuSubTriggerCommonProps as DropdownMenuSubTriggerCommonProps,
    MenuSubTriggerOptions as DropdownMenuSubTriggerOptions,
    MenuSubTriggerProps as DropdownMenuSubTriggerProps,
    MenuSubTriggerRenderProps as DropdownMenuSubTriggerRenderProps,
    MenuTriggerCommonProps as DropdownMenuTriggerCommonProps,
    MenuTriggerOptions as DropdownMenuTriggerOptions,
    MenuTriggerProps as DropdownMenuTriggerProps,
    MenuTriggerRenderProps as DropdownMenuTriggerRenderProps,
    MenuGroup as Group,
    MenuGroupLabel as GroupLabel,
    MenuIcon as Icon,
    MenuItem as Item,
    MenuItemDescription as ItemDescription,
    MenuItemIndicator as ItemIndicator,
    MenuItemLabel as ItemLabel,
    MenuPortal as Portal,
    MenuRadioGroup as RadioGroup,
    MenuRadioItem as RadioItem,
    DropdownMenuRoot as Root,
    SeparatorRoot as Separator,
    MenuSub as Sub,
    MenuSubContent as SubContent,
    MenuSubTrigger as SubTrigger,
    MenuTrigger as Trigger,
  };
}

export { DropdownMenuContentOptions as D, DropdownMenuContentCommonProps as a, DropdownMenuContentRenderProps as b, DropdownMenuContentProps as c, DropdownMenuRootOptions as d, DropdownMenuRootProps as e, DropdownMenuContent as f, DropdownMenuRoot as g, DropdownMenu as h, index as i };
