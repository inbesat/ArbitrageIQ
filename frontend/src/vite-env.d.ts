/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Absolute API base URL for deployed builds; unset locally. */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
