/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue';
  const component: DefineComponent<
    Record<string, unknown>, // props
    Record<string, unknown>, // raw bindings
    unknown // data
  >;
  export default component;
}
