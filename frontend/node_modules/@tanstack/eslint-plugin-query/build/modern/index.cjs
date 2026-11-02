Object.defineProperties(exports, {
	__esModule: { value: true },
	[Symbol.toStringTag]: { value: "Module" }
});
const require_rules = require("./rules-B1yVUvLh.cjs");
//#region src/index.ts
const recommendedRules = {
	"@tanstack/query/exhaustive-deps": "error",
	"@tanstack/query/no-rest-destructuring": "warn",
	"@tanstack/query/stable-query-client": "error",
	"@tanstack/query/no-unstable-deps": "error",
	"@tanstack/query/infinite-query-property-order": "error",
	"@tanstack/query/no-void-query-fn": "error",
	"@tanstack/query/mutation-property-order": "error"
};
const recommendedStrictRules = {
	...recommendedRules,
	"@tanstack/query/prefer-query-options": "error"
};
const plugin = {
	meta: { name: "@tanstack/eslint-plugin-query" },
	configs: {
		recommended: {
			plugins: ["@tanstack/query"],
			rules: recommendedRules
		},
		recommendedStrict: {
			plugins: ["@tanstack/query"],
			rules: recommendedStrictRules
		},
		"flat/recommended": [{
			name: "tanstack/query/flat/recommended",
			plugins: { "@tanstack/query": {} },
			rules: recommendedRules
		}],
		"flat/recommended-strict": [{
			name: "tanstack/query/flat/recommended-strict",
			plugins: { "@tanstack/query": {} },
			rules: recommendedStrictRules
		}]
	},
	rules: require_rules.rules
};
plugin.configs["flat/recommended"][0].plugins["@tanstack/query"] = plugin;
plugin.configs["flat/recommended-strict"][0].plugins["@tanstack/query"] = plugin;
//#endregion
exports.default = plugin;
exports.plugin = plugin;

module.exports = module.exports.default
//# sourceMappingURL=index.cjs.map