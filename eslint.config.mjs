// eslint.config.js
import js from '@eslint/js';
import globals from 'globals';

export default [
    js.configs.recommended,

    {
        files: ['*.js'],
        languageOptions: {
            ecmaVersion: 2025,
            sourceType: 'script',
            globals: {
                ...globals.browser,
                ...globals.es2022,
                // Greasemonkey / Tampermonkey
                GM_addStyle: 'readonly',
                GM_getValue: 'readonly',
                GM_setValue: 'readonly',
                GM_deleteValue: 'readonly',
                GM_xmlhttpRequest: 'readonly',
                unsafeWindow: 'readonly',
            },
        },

        rules: {
            'no-console': 'off',
            'no-inner-declarations': 'warn',
            'no-global-assign': 'warn',
            'no-redeclare': 'warn',
            'no-self-assign': 'warn',
            'no-undef': 'warn',
            'no-useless-concat': 'warn',
            'no-useless-escape': 'warn',
            'no-unused-vars': 'warn',
            'no-var': 'error',

            // formatting / style
            'indent': 'off',
            'linebreak-style': ['error', 'unix'],
            'max-len': [
                'warn',
                100,
                4,
                {
                    ignoreUrls: true,
                    ignoreComments: true,
                },
            ],
            'prefer-const': 'error',
            'one-var': ['error', 'never'],
        },
    },
];
