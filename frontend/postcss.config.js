// Tailwind CSS v3 processes through PostCSS. Without this file Tailwind emits nothing.
// Source: https://v3.tailwindcss.com/docs/installation/using-postcss
//
// NOTE (T01 deviation): this file is one beyond T01's 15-file ownership list. It is
// tooling configuration for the same concern as frontend/tailwind.config.js, which T01
// does own, and it is required for the approved styling system to function at all.
// Flagged in the T01 phase report and recorded in plans/PROGRESS.md.
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
