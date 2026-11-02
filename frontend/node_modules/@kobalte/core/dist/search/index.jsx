import {
  ComboboxBase,
  ComboboxContent,
  ComboboxControl,
  ComboboxHiddenSelect,
  ComboboxIcon,
  ComboboxInput,
  ComboboxListbox,
  ComboboxPortal
} from "../chunk/VXJSV7WD.jsx";
import "../chunk/GSF7SFRW.jsx";
import {
  ListboxItem,
  ListboxItemDescription,
  ListboxItemLabel,
  ListboxSection
} from "../chunk/2UV3VFID.jsx";
import "../chunk/FINWO3A5.jsx";
import {
  PopperArrow
} from "../chunk/OGE3DKII.jsx";
import "../chunk/BDJEWKR2.jsx";
import "../chunk/RFN6X5VH.jsx";
import "../chunk/FKUFPCQ6.jsx";
import "../chunk/LP6E37CW.jsx";
import "../chunk/KEL2LLJM.jsx";
import "../chunk/TDEUK6C2.jsx";
import "../chunk/AAA75RJW.jsx";
import "../chunk/IGYOA2ZZ.jsx";
import "../chunk/IARUYOQZ.jsx";
import "../chunk/3DLZMX4Z.jsx";
import "../chunk/JHMNWOLY.jsx";
import "../chunk/E53DB7BS.jsx";
import "../chunk/YFEENJN5.jsx";
import {
  FormControlLabel
} from "../chunk/FOXVCQFV.jsx";
import "../chunk/QJIB6BDF.jsx";
import {
  FormControlDescription
} from "../chunk/XUUROM4M.jsx";
import "../chunk/EJ5I5XML.jsx";
import "../chunk/JNCCF6MP.jsx";
import "../chunk/FN6EICGO.jsx";
import "../chunk/OYES4GOP.jsx";
import {
  Polymorphic
} from "../chunk/FLVHQV4A.jsx";
import "../chunk/5WXHJDCZ.jsx";

// src/search/search-indicator.tsx
import { Show, splitProps } from "solid-js";

// src/search/search-context.tsx
import { createContext, useContext } from "solid-js";
var SearchContext = createContext();
function useSearchContext() {
  const context = useContext(SearchContext);
  if (context === void 0) {
    throw new Error(
      "[kobalte]: `useSearchContext` must be used within a `Search` component"
    );
  }
  return context;
}

// src/search/search-indicator.tsx
function SearchIndicator(props) {
  const [local, other] = splitProps(props, ["loadingComponent"]);
  const context = useSearchContext();
  return <Polymorphic as="span" aria-hidden="true" {...other}><Show
    when={context.isLoadingSuggestions() === false || !local.loadingComponent}
    fallback={local.loadingComponent}
  >{props.children}</Show></Polymorphic>;
}

// src/search/search-no-result.tsx
import { Show as Show2 } from "solid-js";
function SearchNoResult(props) {
  const context = useSearchContext();
  return <Show2 when={context.noResult()}><Polymorphic as="div" {...props} /></Show2>;
}

// src/search/search-root.tsx
import {
  createEffect,
  createMemo,
  createSignal,
  splitProps as splitProps2
} from "solid-js";

// src/search/utils.ts
var DebouncerTimeout = () => {
  let _debounceMillisecond = 0;
  let lastCallbackTime = 0;
  let timeout;
  return {
    debounce: (callback) => {
      if (lastCallbackTime > Date.now() - _debounceMillisecond)
        clearTimeout(timeout);
      timeout = setTimeout(callback, _debounceMillisecond);
      lastCallbackTime = Date.now();
      return timeout;
    },
    setDebounceMillisecond: (debounceMillisecond = 0) => {
      _debounceMillisecond = debounceMillisecond;
    }
  };
};

// src/search/search-root.tsx
function SearchRoot(props) {
  const [local, omit, others] = splitProps2(
    props,
    [
      "options",
      "value",
      "defaultValue",
      "onChange",
      "multiple",
      "onInputChange",
      "debounceOptionsMillisecond"
    ],
    // @ts-expect-error filter is handled externally, so it's omitted
    ["defaultFilter"]
  );
  const [isLoadingSuggestions, setIsLoadingSuggestions] = createSignal(false);
  const [suggestionTimeout, setSuggestionTimeout] = createSignal();
  const inputChangeDebouncer = DebouncerTimeout();
  createEffect(
    () => inputChangeDebouncer.setDebounceMillisecond(
      local.debounceOptionsMillisecond
    )
  );
  const onInputChange = (value2) => {
    if (local.onInputChange === void 0)
      return;
    setIsLoadingSuggestions(true);
    const timeout = inputChangeDebouncer.debounce(async () => {
      await local.onInputChange(value2);
      setIsLoadingSuggestions(false);
    });
    setSuggestionTimeout(timeout);
  };
  const value = createMemo(() => {
    if (local.value != null) {
      return local.multiple ? local.value : [local.value];
    }
    return local.value;
  });
  const defaultValue = createMemo(() => {
    if (local.defaultValue != null) {
      return local.multiple ? local.defaultValue : [local.defaultValue];
    }
    return local.defaultValue;
  });
  const onChange = (value2) => {
    clearTimeout(suggestionTimeout());
    setIsLoadingSuggestions(false);
    if (local.multiple) {
      local.onChange?.(value2 ?? []);
    } else {
      local.onChange?.(value2[0] ?? null);
    }
  };
  const noResult = () => local.options.length === 0;
  const context = {
    noResult,
    isLoadingSuggestions
  };
  return <SearchContext.Provider value={context}><ComboboxBase
    closeOnSelection
    shouldFocusWrap
    noResetInputOnBlur
    allowsEmptyCollection={true}
    options={local.options}
    value={value()}
    defaultValue={defaultValue()}
    onInputChange={onInputChange}
    defaultFilter={() => true}
    onChange={onChange}
    selectionMode={local.multiple ? "multiple" : "single"}
    {...others}
  /></SearchContext.Provider>;
}

// src/search/index.tsx
var Search = Object.assign(SearchRoot, {
  Arrow: PopperArrow,
  Content: ComboboxContent,
  Control: ComboboxControl,
  Description: FormControlDescription,
  HiddenSelect: ComboboxHiddenSelect,
  Icon: ComboboxIcon,
  Input: ComboboxInput,
  Item: ListboxItem,
  ItemDescription: ListboxItemDescription,
  ItemLabel: ListboxItemLabel,
  Label: FormControlLabel,
  Listbox: ComboboxListbox,
  Portal: ComboboxPortal,
  Section: ListboxSection,
  NoResult: SearchNoResult,
  Indicator: SearchIndicator
});
export {
  PopperArrow as Arrow,
  ComboboxContent as Content,
  ComboboxControl as Control,
  FormControlDescription as Description,
  ComboboxHiddenSelect as HiddenSelect,
  ComboboxIcon as Icon,
  SearchIndicator as Indicator,
  ComboboxInput as Input,
  ListboxItem as Item,
  ListboxItemDescription as ItemDescription,
  ListboxItemLabel as ItemLabel,
  FormControlLabel as Label,
  ComboboxListbox as Listbox,
  SearchNoResult as NoResult,
  ComboboxPortal as Portal,
  SearchRoot as Root,
  Search,
  ListboxSection as Section,
  useSearchContext
};
