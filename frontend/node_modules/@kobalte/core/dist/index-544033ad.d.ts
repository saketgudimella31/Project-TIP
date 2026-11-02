import { P as PopperArrow, c as PopperArrowCommonProps, a as PopperArrowOptions, b as PopperArrowProps, d as PopperArrowRenderProps } from './popper-arrow-89a19127.js';
import { M as MenuCheckboxItem, a as MenuContent, b as MenuGroup, c as MenuGroupLabel, d as MenuIcon, e as MenuItem, f as MenuItemDescription, g as MenuItemIndicator, h as MenuItemLabel, i as MenuPortal, j as MenuRadioGroup, k as MenuRadioItem, l as MenuSub, m as MenuSubContent, n as MenuSubTrigger, o as MenuCheckboxItemCommonProps, p as MenuCheckboxItemOptions, q as MenuCheckboxItemProps, r as MenuCheckboxItemRenderProps, s as MenuContentCommonProps, t as MenuContentOptions, u as MenuContentProps, v as MenuContentRenderProps, w as MenuGroupCommonProps, x as MenuGroupLabelCommonProps, y as MenuGroupLabelOptions, z as MenuGroupLabelProps, A as MenuGroupLabelRenderProps, B as MenuGroupOptions, C as MenuGroupProps, D as MenuGroupRenderProps, E as MenuIconCommonProps, F as MenuIconOptions, G as MenuIconProps, H as MenuIconRenderProps, I as MenuItemCommonProps, J as MenuItemDescriptionCommonProps, K as MenuItemDescriptionOptions, L as MenuItemDescriptionProps, N as MenuItemDescriptionRenderProps, O as MenuItemIndicatorCommonProps, P as MenuItemIndicatorOptions, Q as MenuItemIndicatorProps, R as MenuItemIndicatorRenderProps, S as MenuItemLabelCommonProps, T as MenuItemLabelOptions, U as MenuItemLabelProps, V as MenuItemLabelRenderProps, W as MenuItemOptions, X as MenuItemProps, Y as MenuItemRenderProps, Z as MenuPortalProps, _ as MenuRadioGroupCommonProps, $ as MenuRadioGroupOptions, a0 as MenuRadioGroupProps, a1 as MenuRadioGroupRenderProps, a2 as MenuRadioItemCommonProps, a3 as MenuRadioItemOptions, a4 as MenuRadioItemRenderProps, a5 as MenuRadioItemProps, a6 as MenuSubContentCommonProps, a7 as MenuSubContentOptions, a8 as MenuSubContentProps, a9 as MenuSubContentRenderProps, aa as MenuSubOptions, ab as MenuSubProps, ac as MenuSubTriggerCommonProps, ad as MenuSubTriggerOptions, ae as MenuSubTriggerProps, af as MenuSubTriggerRenderProps } from './menu-sub-trigger-29a7ad75.js';
import { MenuTriggerProps, MenuTriggerCommonProps, MenuTriggerOptions, MenuTriggerRenderProps } from './menu/index.js';
import { S as SeparatorRoot, a as SeparatorRootCommonProps, b as SeparatorRootOptions, c as SeparatorRootProps, d as SeparatorRootRenderProps } from './separator-root-cb685406.js';
import { M as MenubarRoot, a as MenubarMenu, b as MenubarContextValue, c as MenubarMenuOptions, d as MenubarMenuProps, e as MenubarRootCommonProps, f as MenubarRootOptions, g as MenubarRootProps, h as MenubarRootRenderProps, u as useMenubarContext } from './menubar-context-c1a81ca0.js';
import * as solid_js from 'solid-js';
import { ValidComponent } from 'solid-js';
import { PolymorphicProps } from './polymorphic/index.js';

/**
 * The button that toggles the menubar menu or a menubar link.
 */
declare function MenubarTrigger<T extends ValidComponent = "button">(props: PolymorphicProps<T, MenuTriggerProps<T>>): solid_js.JSX.Element;

declare const Menubar: typeof MenubarRoot & {
    Arrow: typeof PopperArrow;
    CheckboxItem: typeof MenuCheckboxItem;
    Content: typeof MenuContent;
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
    Menu: typeof MenubarMenu;
    Separator: typeof SeparatorRoot;
    Sub: typeof MenuSub;
    SubContent: typeof MenuSubContent;
    SubTrigger: typeof MenuSubTrigger;
    Trigger: typeof MenubarTrigger;
};

declare const index_Menubar: typeof Menubar;
declare const index_MenubarContextValue: typeof MenubarContextValue;
declare const index_MenubarMenuOptions: typeof MenubarMenuOptions;
declare const index_MenubarMenuProps: typeof MenubarMenuProps;
declare const index_MenubarRootCommonProps: typeof MenubarRootCommonProps;
declare const index_MenubarRootOptions: typeof MenubarRootOptions;
declare const index_MenubarRootProps: typeof MenubarRootProps;
declare const index_MenubarRootRenderProps: typeof MenubarRootRenderProps;
declare const index_useMenubarContext: typeof useMenubarContext;
declare namespace index {
  export {
    PopperArrow as Arrow,
    MenuCheckboxItem as CheckboxItem,
    MenuContent as Content,
    MenuGroup as Group,
    MenuGroupLabel as GroupLabel,
    MenuIcon as Icon,
    MenuItem as Item,
    MenuItemDescription as ItemDescription,
    MenuItemIndicator as ItemIndicator,
    MenuItemLabel as ItemLabel,
    MenubarMenu as Menu,
    index_Menubar as Menubar,
    PopperArrowCommonProps as MenubarArrowCommonProps,
    PopperArrowOptions as MenubarArrowOptions,
    PopperArrowProps as MenubarArrowProps,
    PopperArrowRenderProps as MenubarArrowRenderProps,
    MenuCheckboxItemCommonProps as MenubarCheckboxItemCommonProps,
    MenuCheckboxItemOptions as MenubarCheckboxItemOptions,
    MenuCheckboxItemProps as MenubarCheckboxItemProps,
    MenuCheckboxItemRenderProps as MenubarCheckboxItemRenderProps,
    MenuContentCommonProps as MenubarContentCommonProps,
    MenuContentOptions as MenubarContentOptions,
    MenuContentProps as MenubarContentProps,
    MenuContentRenderProps as MenubarContentRenderProps,
    index_MenubarContextValue as MenubarContextValue,
    MenuGroupCommonProps as MenubarGroupCommonProps,
    MenuGroupLabelCommonProps as MenubarGroupLabelCommonProps,
    MenuGroupLabelOptions as MenubarGroupLabelOptions,
    MenuGroupLabelProps as MenubarGroupLabelProps,
    MenuGroupLabelRenderProps as MenubarGroupLabelRenderProps,
    MenuGroupOptions as MenubarGroupOptions,
    MenuGroupProps as MenubarGroupProps,
    MenuGroupRenderProps as MenubarGroupRenderProps,
    MenuIconCommonProps as MenubarIconCommonProps,
    MenuIconOptions as MenubarIconOptions,
    MenuIconProps as MenubarIconProps,
    MenuIconRenderProps as MenubarIconRenderProps,
    MenuItemCommonProps as MenubarItemCommonProps,
    MenuItemDescriptionCommonProps as MenubarItemDescriptionCommonProps,
    MenuItemDescriptionOptions as MenubarItemDescriptionOptions,
    MenuItemDescriptionProps as MenubarItemDescriptionProps,
    MenuItemDescriptionRenderProps as MenubarItemDescriptionRenderProps,
    MenuItemIndicatorCommonProps as MenubarItemIndicatorCommonProps,
    MenuItemIndicatorOptions as MenubarItemIndicatorOptions,
    MenuItemIndicatorProps as MenubarItemIndicatorProps,
    MenuItemIndicatorRenderProps as MenubarItemIndicatorRenderProps,
    MenuItemLabelCommonProps as MenubarItemLabelCommonProps,
    MenuItemLabelOptions as MenubarItemLabelOptions,
    MenuItemLabelProps as MenubarItemLabelProps,
    MenuItemLabelRenderProps as MenubarItemLabelRenderProps,
    MenuItemOptions as MenubarItemOptions,
    MenuItemProps as MenubarItemProps,
    MenuItemRenderProps as MenubarItemRenderProps,
    index_MenubarMenuOptions as MenubarMenuOptions,
    index_MenubarMenuProps as MenubarMenuProps,
    MenuPortalProps as MenubarPortalProps,
    MenuRadioGroupCommonProps as MenubarRadioGroupCommonProps,
    MenuRadioGroupOptions as MenubarRadioGroupOptions,
    MenuRadioGroupProps as MenubarRadioGroupProps,
    MenuRadioGroupRenderProps as MenubarRadioGroupRenderProps,
    MenuRadioItemCommonProps as MenubarRadioItemCommonProps,
    MenuRadioItemOptions as MenubarRadioItemOptions,
    MenuRadioItemRenderProps as MenubarRadioItemPRenderrops,
    MenuRadioItemProps as MenubarRadioItemProps,
    index_MenubarRootCommonProps as MenubarRootCommonProps,
    index_MenubarRootOptions as MenubarRootOptions,
    index_MenubarRootProps as MenubarRootProps,
    index_MenubarRootRenderProps as MenubarRootRenderProps,
    SeparatorRootCommonProps as MenubarSeparatorCommonProps,
    SeparatorRootOptions as MenubarSeparatorOptions,
    SeparatorRootProps as MenubarSeparatorProps,
    SeparatorRootRenderProps as MenubarSeparatorRenderProps,
    MenuSubContentCommonProps as MenubarSubContentCommonProps,
    MenuSubContentOptions as MenubarSubContentOptions,
    MenuSubContentProps as MenubarSubContentProps,
    MenuSubContentRenderProps as MenubarSubContentRenderProps,
    MenuSubOptions as MenubarSubOptions,
    MenuSubProps as MenubarSubProps,
    MenuSubTriggerCommonProps as MenubarSubTriggerCommonProps,
    MenuSubTriggerOptions as MenubarSubTriggerOptions,
    MenuSubTriggerProps as MenubarSubTriggerProps,
    MenuSubTriggerRenderProps as MenubarSubTriggerRenderProps,
    MenuTriggerCommonProps as MenubarTriggerCommonProps,
    MenuTriggerOptions as MenubarTriggerOptions,
    MenuTriggerProps as MenubarTriggerProps,
    MenuTriggerRenderProps as MenubarTriggerRenderProps,
    MenuPortal as Portal,
    MenuRadioGroup as RadioGroup,
    MenuRadioItem as RadioItem,
    MenubarRoot as Root,
    SeparatorRoot as Separator,
    MenuSub as Sub,
    MenuSubContent as SubContent,
    MenuSubTrigger as SubTrigger,
    MenubarTrigger as Trigger,
    index_useMenubarContext as useMenubarContext,
  };
}

export { MenubarTrigger as M, Menubar as a, index as i };
