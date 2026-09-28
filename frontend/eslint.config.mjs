import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";
import prettier from "eslint-config-prettier";

const eslintConfig = [
  {
    ignores: [".next/**", "node_modules/**", "coverage/**", "next-env.d.ts"],
  },

  ...nextCoreWebVitals,
  ...nextTypescript,
  prettier,

  {
    rules: {
      // Unused arguments prefixed with '_' are intentional (interface
      // conformance), so they should not be reported.
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },

  {
    files: ["**/*.test.ts", "**/*.test.tsx", "src/test/**"],
    rules: {
      // Test helpers legitimately use 'any' when constructing partial fakes.
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
];

export default eslintConfig;
