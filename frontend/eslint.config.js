import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import reactPlugin from 'eslint-plugin-react'
import reactHooksPlugin from 'eslint-plugin-react-hooks'
import jsxA11yPlugin from 'eslint-plugin-jsx-a11y'
import importX from 'eslint-plugin-import-x'
import { createTypeScriptImportResolver } from 'eslint-import-resolver-typescript'

export default tseslint.config(
  { ignores: ['dist/**', 'node_modules/**'] },

  js.configs.recommended,
  tseslint.configs.recommended,

  reactPlugin.configs.flat['jsx-runtime'],
  reactHooksPlugin.configs.flat['recommended-latest'],
  jsxA11yPlugin.flatConfigs.recommended,

  {
    files: ['src/**/*.{ts,tsx}'],
    plugins: {
      'import-x': importX,
    },
    languageOptions: {
      parserOptions: {
        project: './tsconfig.app.json',
      },
    },
    settings: {
      react: { version: 'detect' },
      'import-x/resolver-next': [
        createTypeScriptImportResolver({
          alwaysTryTypes: true,
          project: './tsconfig.app.json',
        }),
      ],
    },
    rules: {
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      '@typescript-eslint/explicit-function-return-type': [
        'error',
        { allowExpressions: true, allowTypedFunctionExpressions: true },
      ],
      'import-x/order': [
        'error',
        {
          groups: ['builtin', 'external', 'internal', 'parent', 'sibling', 'index'],
          'newlines-between': 'always',
          alphabetize: { order: 'asc' },
        },
      ],
      'import-x/no-duplicates': 'error',
    },
  },
)
