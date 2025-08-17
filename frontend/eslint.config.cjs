// Flat config (ESLint v9+)
// Uses FlatCompat to bring over legacy "extends" entries safely.
const { FlatCompat } = require('@eslint/eslintrc');
const globals = require('globals');

const tsParser = require('@typescript-eslint/parser');
const tsPlugin = require('@typescript-eslint/eslint-plugin');
const vuePlugin = require('eslint-plugin-vue');
const vueEslintParser = require('vue-eslint-parser');
const prettierConfig = require('eslint-config-prettier');

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

module.exports = [
  // Ignores
  {
    ignores: [
      'node_modules/**',
      'dist/**',
      'build/**',
      'coverage/**',
      'public/**',
      'src/generated/**',
      'eslint.config.cjs',
    ],
  },
  // Vue 3 recommended (flat config array from plugin)
  ...require('eslint-plugin-vue/lib/configs/flat/vue3-recommended'),
  // TypeScript + prettier (still using compat for legacy shareable configs)
  ...compat.extends('plugin:@typescript-eslint/recommended', 'prettier'),

  // Project-specific settings, plugins, and rules
  {
    files: ['**/*.{js,jsx,ts,tsx,vue}'],
    languageOptions: {
      // Use the Vue SFC parser, delegate <script> blocks to TS parser
      parser: vueEslintParser,
      parserOptions: {
        parser: tsParser,
        ecmaVersion: 'latest',
        sourceType: 'module',
        extraFileExtensions: ['.vue'],
      },
      globals: {
        ...globals.browser,
        ...globals.node,
        // Vue SFC <script setup> macros (replacement for env: 'vue/setup-compiler-macros')
        defineProps: 'readonly',
        defineEmits: 'readonly',
        defineExpose: 'readonly',
        withDefaults: 'readonly',

        // Custom globals from your previous config
        ga: 'readonly',
        cordova: 'readonly',
        __statics: 'readonly',
        process: 'readonly',
        chrome: 'readonly',
      },
    },
    plugins: {
      '@typescript-eslint': tsPlugin,
      vue: vuePlugin,
    },
    rules: {
      // Allow rejecting Promises with non-Error values (turned off so code can reject with strings or other primitives without lint errors)
      'prefer-promise-reject-errors': 'off',

      // Enforce single quotes; warns (not errors). Allows escaping when avoiding double quotes would be cumbersome
      quotes: ['warn', 'single', { avoidEscape: true }],

      // Would require every function to have an explicit return type annotation; disabled to rely on type inference for brevity
      '@typescript-eslint/explicit-function-return-type': 'off',

      // Enforce multi-word component names to avoid conflicts with HTML elements.
      // Here we explicitly allow common page/root component single-word names listed below.
      'vue/multi-word-component-names': [
        'error',
        {
          ignores: ['Home', 'Login', 'Register', 'Profile', 'Rooms', 'App'],
        },
      ],

      // Forbid `debugger` statements in production builds; allow them during development for easier debugging
      'no-debugger': process.env.NODE_ENV === 'production' ? 'error' : 'off',
    },
  },

  // Prettier compatibility (flat config export)
  prettierConfig,
];
