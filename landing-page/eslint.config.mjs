import next from "eslint-config-next";

/** @type {import('eslint').Linter.FlatConfig[]} */
export default [
  ...next,
  {
    rules: {
      // project-specific overrides go here
    },
  },
];
