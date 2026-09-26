/// <reference types="vite/client" />

// Vite injects VITE_* environment variables into import.meta.env at build time.
interface ImportMetaEnv {
  readonly VITE_BACKEND_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
