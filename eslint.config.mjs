import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = [
  ...nextVitals,
  ...nextTs,
  {
    ignores: [
      ".next/**",
      "generated/**",
      "node_modules/**",
      "storage/**",
      "prisma/migrations/**",
    ],
  },
];

export default eslintConfig;
