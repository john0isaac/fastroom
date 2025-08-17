// Flat config (ESLint v9+)
// Uses FlatCompat to bring over legacy "extends" entries safely.
const { FlatCompat } = require('@eslint/eslintrc');
const globals = require('globals');

const tsParser = require('@typescript-eslint/parser');
const tsPlugin = require('@typescript-eslint/eslint-plugin');
const vuePlugin = require('eslint-plugin-vue');
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

  // Bring over legacy "extends" via compat
  ...compat.extends(
    // 'plugin:vue/vue3-strongly-recommended',
    // 'plugin:vue/vue3-recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:vue/vue2-essential',
    'prettier'
  ),

  // Project-specific settings, plugins, and rules
  {
    files: ['**/*.{js,jsx,ts,tsx,vue}'],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
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
      'prefer-promise-reject-errors': 'off',
      quotes: ['warn', 'single', { avoidEscape: true }],

      '@typescript-eslint/explicit-function-return-type': 'off',
      '@typescript-eslint/no-var-requires': 'off',
      'no-unused-vars': 'off',

      'no-debugger': process.env.NODE_ENV === 'production' ? 'error' : 'off',
    },
  },

  // Prettier compatibility (flat config export)
  prettierConfig,
];
