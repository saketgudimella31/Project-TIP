let _typescript_eslint_utils = require("@typescript-eslint/utils");
//#region src/utils/unique-by.ts
function uniqueBy(arr, fn) {
	return arr.filter((x, i, a) => a.findIndex((y) => fn(x) === fn(y)) === i);
}
//#endregion
//#region src/utils/ast-utils.ts
const ASTUtils = {
	isNodeOfOneOf(node, types) {
		return types.includes(node.type);
	},
	isIdentifier(node) {
		return node.type === _typescript_eslint_utils.AST_NODE_TYPES.Identifier;
	},
	isIdentifierWithName(node, name) {
		return ASTUtils.isIdentifier(node) && node.name === name;
	},
	isIdentifierWithOneOfNames(node, name) {
		return ASTUtils.isIdentifier(node) && name.includes(node.name);
	},
	isProperty(node) {
		return node.type === _typescript_eslint_utils.AST_NODE_TYPES.Property;
	},
	isObjectExpression(node) {
		return node.type === _typescript_eslint_utils.AST_NODE_TYPES.ObjectExpression;
	},
	isPropertyWithIdentifierKey(node, key) {
		return ASTUtils.isProperty(node) && ASTUtils.isIdentifierWithName(node.key, key);
	},
	findPropertyWithIdentifierKey(properties, key) {
		return properties.find((x) => ASTUtils.isPropertyWithIdentifierKey(x, key));
	},
	traverseUpOnly(identifier, allowedNodeTypes) {
		const parent = identifier.parent;
		if (parent !== void 0 && allowedNodeTypes.includes(parent.type)) return ASTUtils.traverseUpOnly(parent, allowedNodeTypes);
		return identifier;
	},
	traverseUpMemberExpression(node) {
		const parent = node.parent;
		if (parent !== void 0 && (parent.type === _typescript_eslint_utils.AST_NODE_TYPES.MemberExpression && parent.object === node || parent.type === _typescript_eslint_utils.AST_NODE_TYPES.ChainExpression || parent.type === _typescript_eslint_utils.AST_NODE_TYPES.TSNonNullExpression)) return ASTUtils.traverseUpMemberExpression(parent);
		return node;
	},
	isDeclaredInNode(params) {
		const { functionNode, reference, scopeManager } = params;
		const scope = scopeManager.acquire(functionNode);
		if (scope === null) return false;
		return scope.set.has(reference.identifier.name);
	},
	getExternalRefs(params) {
		const { scopeManager, sourceCode, node } = params;
		const scope = scopeManager.acquire(node);
		if (scope === null) return [];
		const collectReferences = (currentScope) => {
			const references = [...currentScope.references];
			for (const childScope of currentScope.childScopes) references.push(...collectReferences(childScope));
			return references;
		};
		const references = collectReferences(scope).filter((x) => x.isRead() && !scope.set.has(x.identifier.name)).map((x) => {
			const memberPath = ASTUtils.traverseUpMemberExpression(x.identifier);
			const memberExpression = memberPath.parent;
			const referenceNode = memberExpression !== void 0 && memberExpression.type === _typescript_eslint_utils.AST_NODE_TYPES.MemberExpression && memberExpression.computed && memberExpression.property === memberPath && memberExpression.parent.type === _typescript_eslint_utils.AST_NODE_TYPES.CallExpression && memberExpression.parent.callee === memberExpression ? memberPath : ASTUtils.traverseUpOnly(x.identifier, [_typescript_eslint_utils.AST_NODE_TYPES.MemberExpression, _typescript_eslint_utils.AST_NODE_TYPES.Identifier]);
			return {
				variable: x,
				node: referenceNode,
				text: sourceCode.getText(referenceNode)
			};
		});
		const localRefIds = new Set([...scope.set.values()].map((x) => sourceCode.getText(x.identifiers[0])));
		return uniqueBy(references.filter((x) => x.variable.resolved === null || !localRefIds.has(x.text)), (x) => x.text).map((x) => x.variable);
	},
	isValidReactComponentOrHookName(identifier) {
		return identifier !== null && identifier !== void 0 && /^(use|[A-Z])/.test(identifier.name);
	},
	getFunctionAncestor(sourceCode, node) {
		for (const ancestor of sourceCode.getAncestors(node)) {
			if (ASTUtils.isNodeOfOneOf(ancestor, [
				_typescript_eslint_utils.AST_NODE_TYPES.FunctionDeclaration,
				_typescript_eslint_utils.AST_NODE_TYPES.FunctionExpression,
				_typescript_eslint_utils.AST_NODE_TYPES.ArrowFunctionExpression
			])) return ancestor;
			if (ancestor.parent?.type === _typescript_eslint_utils.AST_NODE_TYPES.VariableDeclarator && ancestor.parent.id.type === _typescript_eslint_utils.AST_NODE_TYPES.Identifier && ASTUtils.isNodeOfOneOf(ancestor, [
				_typescript_eslint_utils.AST_NODE_TYPES.FunctionDeclaration,
				_typescript_eslint_utils.AST_NODE_TYPES.FunctionExpression,
				_typescript_eslint_utils.AST_NODE_TYPES.ArrowFunctionExpression
			])) return ancestor;
		}
	},
	getReferencedExpressionByIdentifier(params) {
		const { node, context } = params;
		const sourceCode = context.sourceCode ?? context.getSourceCode();
		const resolvedNode = (context.sourceCode.getScope(node) ? sourceCode.getScope(node) : context.getScope()).references.find((ref) => ref.identifier === node)?.resolved?.defs[0]?.node;
		if (resolvedNode?.type !== _typescript_eslint_utils.AST_NODE_TYPES.VariableDeclarator) return null;
		return resolvedNode.init;
	}
};
//#endregion
//#region src/utils/get-docs-url.ts
const getDocsUrl = (ruleName) => `https://tanstack.com/query/latest/docs/eslint/${ruleName}`;
//#endregion
//#region src/utils/detect-react-query-imports.ts
function detectTanstackQueryImports(create) {
	return (context, optionsWithDefault) => {
		const tanstackQueryImportSpecifiers = [];
		const helpers = {
			isSpecificTanstackQueryImport(node, source) {
				return !!tanstackQueryImportSpecifiers.find((specifier) => {
					if (specifier.type === _typescript_eslint_utils.TSESTree.AST_NODE_TYPES.ImportSpecifier && specifier.parent.type === _typescript_eslint_utils.TSESTree.AST_NODE_TYPES.ImportDeclaration && specifier.parent.source.value === source) return node.name === specifier.local.name;
					return false;
				});
			},
			isTanstackQueryImport(node) {
				return !!tanstackQueryImportSpecifiers.find((specifier) => {
					if (specifier.type === _typescript_eslint_utils.TSESTree.AST_NODE_TYPES.ImportSpecifier) return node.name === specifier.local.name;
					return false;
				});
			}
		};
		const detectionInstructions = { ImportDeclaration(node) {
			if (node.specifiers.length > 0 && (node.importKind === "value" || node.importKind === void 0) && node.source.value.startsWith("@tanstack/") && node.source.value.endsWith("-query")) tanstackQueryImportSpecifiers.push(...node.specifiers);
		} };
		const ruleInstructions = create(context, optionsWithDefault, helpers);
		const enhancedRuleInstructions = {};
		new Set(Object.keys(detectionInstructions).concat(Object.keys(ruleInstructions))).forEach((instruction) => {
			enhancedRuleInstructions[instruction] = (node) => {
				if (instruction in detectionInstructions) detectionInstructions[instruction]?.(node);
				const ruleInstruction = ruleInstructions[instruction];
				if (ruleInstruction) return ruleInstruction(node);
			};
		});
		return enhancedRuleInstructions;
	};
}
//#endregion
//#region src/rules/exhaustive-deps/exhaustive-deps.utils.ts
const ExhaustiveDepsUtils = {
	isRelevantReference(params) {
		const { sourceCode, reference, scopeManager, node, filename } = params;
		const component = ASTUtils.getFunctionAncestor(sourceCode, node);
		const queryFnScope = scopeManager.acquire(node);
		if (queryFnScope === null || reference.isValueReference === false) return false;
		let currentScope = reference.resolved?.scope ?? null;
		while (currentScope !== null) {
			if (currentScope === queryFnScope) return false;
			currentScope = currentScope.upper;
		}
		if (component !== void 0) {
			if (!ASTUtils.isDeclaredInNode({
				scopeManager,
				reference,
				functionNode: component
			})) return false;
		} else {
			if (!filename.endsWith(".vue")) return false;
			const definition = reference.resolved?.defs[0];
			const isGlobalVariable = definition === void 0;
			const isImport = definition?.type === "ImportBinding";
			if (isGlobalVariable || isImport) return false;
		}
		return reference.identifier.name !== "undefined" && !ExhaustiveDepsUtils.isFunctionCallTarget(reference.identifier) && reference.identifier.parent.type !== _typescript_eslint_utils.AST_NODE_TYPES.NewExpression && !ExhaustiveDepsUtils.isInstanceOfKind(reference.identifier.parent);
	},
	isFunctionCallTarget(identifier) {
		const callee = ASTUtils.traverseUpMemberExpression(identifier);
		return callee.parent !== void 0 && callee.parent.type === _typescript_eslint_utils.AST_NODE_TYPES.CallExpression && callee.parent.callee === callee;
	},
	/**
	* Given required refs and existing queryKey entries, compute missing dependency paths
	* respecting allowlisted variables and types.
	*/
	computeFilteredMissingPaths(params) {
		const { requiredRefs, allowlistedVariables, existingRootIdentifiers, existingFullPaths } = params;
		const missingPaths = /* @__PURE__ */ new Set();
		for (const { root, path, allowlistedByType } of requiredRefs) {
			if (existingRootIdentifiers.has(root)) continue;
			if (allowlistedVariables.has(root)) continue;
			if (existingFullPaths.has(path)) continue;
			if (allowlistedByType) continue;
			missingPaths.add(path);
		}
		for (const path of missingPaths) {
			const root = path.split(".")[0];
			if (root !== path && root !== void 0 && missingPaths.has(root)) missingPaths.delete(path);
		}
		return Array.from(missingPaths);
	},
	/**
	* Extract existing queryKey deps as root identifiers and full member paths.
	*/
	collectQueryKeyDeps(params) {
		const { sourceCode, scopeManager, queryKeyNode } = params;
		const roots = /* @__PURE__ */ new Set();
		const paths = /* @__PURE__ */ new Set();
		const visitorKeys = sourceCode.visitorKeys;
		function addRoot(name) {
			const cleaned = ExhaustiveDepsUtils.normalizeChain(name);
			roots.add(cleaned);
			paths.add(cleaned);
		}
		function addFull(text) {
			const cleaned = ExhaustiveDepsUtils.normalizeChain(text);
			paths.add(cleaned);
		}
		function addRefPath(refPath) {
			if (!refPath) return;
			if (refPath.coversRootMembers) {
				addRoot(refPath.root);
				return;
			}
			addFull(refPath.path);
		}
		function visitChildren(node) {
			const keys = visitorKeys[node.type] ?? [];
			for (const key of keys) {
				const value = node[key];
				if (Array.isArray(value)) {
					for (const item of value) if (ExhaustiveDepsUtils.isNode(item)) visit(item);
					continue;
				}
				if (ExhaustiveDepsUtils.isNode(value)) visit(value);
			}
		}
		function visit(node) {
			if (!node) return;
			switch (node.type) {
				case _typescript_eslint_utils.AST_NODE_TYPES.Identifier:
					addRefPath(ExhaustiveDepsUtils.computeRefPath({
						identifier: node,
						sourceCode
					}));
					return;
				case _typescript_eslint_utils.AST_NODE_TYPES.ArrowFunctionExpression:
				case _typescript_eslint_utils.AST_NODE_TYPES.FunctionExpression:
					for (const reference of ExhaustiveDepsUtils.collectExternalRefsInFunction({
						functionNode: node,
						scopeManager
					})) {
						if (reference.identifier.type !== _typescript_eslint_utils.AST_NODE_TYPES.Identifier) continue;
						addRefPath(ExhaustiveDepsUtils.computeRefPath({
							identifier: reference.identifier,
							sourceCode
						}));
					}
					return;
				case _typescript_eslint_utils.AST_NODE_TYPES.Property:
					visit(node.value);
					return;
				case _typescript_eslint_utils.AST_NODE_TYPES.MemberExpression:
					if (node.parent.type === _typescript_eslint_utils.AST_NODE_TYPES.CallExpression && node.parent.callee === node && node.object.type === _typescript_eslint_utils.AST_NODE_TYPES.Identifier) addRoot(node.object.name);
					else visit(node.object);
					return;
				case _typescript_eslint_utils.AST_NODE_TYPES.CallExpression:
					node.arguments.forEach((argument) => visit(argument));
					switch (node.callee.type) {
						case _typescript_eslint_utils.AST_NODE_TYPES.Identifier:
						case _typescript_eslint_utils.AST_NODE_TYPES.MemberExpression:
						case _typescript_eslint_utils.AST_NODE_TYPES.ChainExpression:
						case _typescript_eslint_utils.AST_NODE_TYPES.TSNonNullExpression: visit(node.callee);
					}
					return;
			}
			visitChildren(node);
		}
		visit(queryKeyNode);
		return {
			roots,
			paths
		};
	},
	isNode(value) {
		return typeof value === "object" && value !== null && "type" in value && typeof value.type === "string";
	},
	/**
	* Checks whether the resolved variable is allowlisted by its type annotation
	*/
	variableIsAllowlistedByType(params) {
		const { allowlistedTypes, variable } = params;
		if (allowlistedTypes.size === 0) return false;
		if (!variable) return false;
		for (const id of variable.identifiers) if (id.typeAnnotation) {
			const typeIdentifiers = /* @__PURE__ */ new Set();
			ExhaustiveDepsUtils.collectTypeIdentifiers(id.typeAnnotation.typeAnnotation, typeIdentifiers);
			for (const typeIdentifier of typeIdentifiers) if (allowlistedTypes.has(typeIdentifier)) return true;
		}
		return false;
	},
	isInstanceOfKind(node) {
		return node.type === _typescript_eslint_utils.AST_NODE_TYPES.BinaryExpression && node.operator === "instanceof";
	},
	/**
	* Normalizes a chain by removing optional chaining operators
	*
	* Example: `a?.b.c!` -> `a.b.c`
	*/
	normalizeChain(text) {
		return text.replace(/(?:\?(\.)|!)/g, "$1").replace(/\s+/g, "");
	},
	/**
	* Computes the reference path for an identifier
	*
	* Example: `a.b.c!` -> `{ path: 'a.b.c', root: 'a' }`
	*/
	computeRefPath(params) {
		const { identifier, sourceCode } = params;
		const fullChainNode = ASTUtils.traverseUpMemberExpression(identifier);
		const fullText = ExhaustiveDepsUtils.normalizeChain(sourceCode.getText(fullChainNode));
		const parent = fullChainNode.parent;
		let dependencyPath = fullText;
		let coversRootMembers = fullText === identifier.name;
		if (parent && parent.type === _typescript_eslint_utils.AST_NODE_TYPES.CallExpression && parent.callee === fullChainNode) {
			const segments = fullText.split(".");
			if (segments.length > 1) dependencyPath = segments.slice(0, -1).join(".");
			coversRootMembers = false;
		}
		dependencyPath = dependencyPath.split(".")[0] === "" ? identifier.name : dependencyPath;
		const root = dependencyPath.split(".")[0];
		return {
			path: dependencyPath,
			root: root ?? identifier.name,
			coversRootMembers: coversRootMembers && dependencyPath === root
		};
	},
	collectExternalRefsInFunction(params) {
		const { functionNode, scopeManager } = params;
		const functionScope = scopeManager.acquire(functionNode);
		if (functionScope === null) return [];
		const externalRefs = [];
		function collect(scope) {
			for (const reference of scope.references) {
				if (!reference.isRead() || reference.resolved === null) continue;
				let currentScope = reference.resolved.scope;
				let declaredInsideFunction = false;
				while (currentScope !== null) {
					if (currentScope === functionScope) {
						declaredInsideFunction = true;
						break;
					}
					currentScope = currentScope.upper;
				}
				if (!declaredInsideFunction) externalRefs.push(reference);
			}
			for (const childScope of scope.childScopes) collect(childScope);
		}
		collect(functionScope);
		return externalRefs;
	},
	/**
	* Recursively collects type identifiers from a type annotation
	*/
	collectTypeIdentifiers(typeNode, out) {
		switch (typeNode.type) {
			case _typescript_eslint_utils.AST_NODE_TYPES.TSTypeReference:
				if (typeNode.typeName.type === _typescript_eslint_utils.AST_NODE_TYPES.Identifier) out.add(typeNode.typeName.name);
				break;
			case _typescript_eslint_utils.AST_NODE_TYPES.TSUnionType:
			case _typescript_eslint_utils.AST_NODE_TYPES.TSIntersectionType:
				typeNode.types.forEach((t) => ExhaustiveDepsUtils.collectTypeIdentifiers(t, out));
				break;
			case _typescript_eslint_utils.AST_NODE_TYPES.TSArrayType:
				ExhaustiveDepsUtils.collectTypeIdentifiers(typeNode.elementType, out);
				break;
			case _typescript_eslint_utils.AST_NODE_TYPES.TSTupleType: typeNode.elementTypes.forEach((et) => ExhaustiveDepsUtils.collectTypeIdentifiers(et, out));
		}
	},
	/**
	* Gets the function expression nodes from a queryFn property, handling conditional expressions.
	* When neither branch is skipToken, returns both branches so all deps are scanned.
	*/
	getQueryFnNodes(queryFn) {
		if (queryFn.value.type !== _typescript_eslint_utils.AST_NODE_TYPES.ConditionalExpression) return [queryFn.value];
		if (queryFn.value.consequent.type === _typescript_eslint_utils.AST_NODE_TYPES.Identifier && queryFn.value.consequent.name === "skipToken") return [queryFn.value.alternate];
		if (queryFn.value.alternate.type === _typescript_eslint_utils.AST_NODE_TYPES.Identifier && queryFn.value.alternate.name === "skipToken") return [queryFn.value.consequent];
		return [queryFn.value.consequent, queryFn.value.alternate];
	}
};
//#endregion
//#region src/rules/exhaustive-deps/exhaustive-deps.rule.ts
const QUERY_KEY = "queryKey";
const QUERY_FN = "queryFn";
const name$7 = "exhaustive-deps";
const rule$7 = _typescript_eslint_utils.ESLintUtils.RuleCreator(getDocsUrl)({
	name: name$7,
	meta: {
		type: "problem",
		docs: {
			description: "Exhaustive deps rule for useQuery",
			recommended: "error"
		},
		messages: {
			missingDeps: `The following dependencies are missing in your queryKey: {{deps}}`,
			fixTo: "Fix to {{result}}"
		},
		hasSuggestions: true,
		fixable: "code",
		schema: [{
			type: "object",
			properties: { allowlist: {
				type: "object",
				properties: {
					variables: {
						type: "array",
						items: { type: "string" }
					},
					types: {
						type: "array",
						items: { type: "string" }
					}
				},
				additionalProperties: false
			} },
			additionalProperties: false
		}]
	},
	defaultOptions: [],
	create: detectTanstackQueryImports((context) => {
		return { ObjectExpression: (node) => {
			const scopeManager = context.sourceCode.scopeManager;
			const queryKey = ASTUtils.findPropertyWithIdentifierKey(node.properties, QUERY_KEY);
			const queryFn = ASTUtils.findPropertyWithIdentifierKey(node.properties, QUERY_FN);
			if (scopeManager === null || queryKey === void 0 || queryFn === void 0 || !ASTUtils.isNodeOfOneOf(queryFn.value, [
				_typescript_eslint_utils.AST_NODE_TYPES.ArrowFunctionExpression,
				_typescript_eslint_utils.AST_NODE_TYPES.FunctionExpression,
				_typescript_eslint_utils.AST_NODE_TYPES.ConditionalExpression
			])) return;
			const queryKeyNode = dereferenceVariablesAndTypeAssertions(queryKey.value, context);
			const queryFnNodes = ExhaustiveDepsUtils.getQueryFnNodes(queryFn);
			const relevantRefs = queryFnNodes.flatMap((fnNode) => ASTUtils.getExternalRefs({
				scopeManager,
				sourceCode: context.sourceCode,
				node: fnNode
			})).filter((reference) => queryFnNodes.some((fnNode) => ExhaustiveDepsUtils.isRelevantReference({
				sourceCode: context.sourceCode,
				reference,
				scopeManager,
				node: fnNode,
				filename: context.filename
			})));
			const ruleOptions = context.options.at(0);
			const allowlistedVariables = new Set(ruleOptions?.allowlist?.variables ?? []);
			const allowlistedTypes = new Set(ruleOptions?.allowlist?.types ?? []);
			const requiredRefs = relevantRefs.flatMap((ref) => {
				if (ref.identifier.type !== _typescript_eslint_utils.AST_NODE_TYPES.Identifier) return [];
				const refPath = ExhaustiveDepsUtils.computeRefPath({
					identifier: ref.identifier,
					sourceCode: context.sourceCode
				});
				if (refPath === null) return [];
				return [{
					...refPath,
					allowlistedByType: ExhaustiveDepsUtils.variableIsAllowlistedByType({
						allowlistedTypes,
						variable: ref.resolved ?? null
					})
				}];
			});
			if (requiredRefs.length === 0) return;
			const queryKeyDeps = ExhaustiveDepsUtils.collectQueryKeyDeps({
				sourceCode: context.sourceCode,
				scopeManager,
				queryKeyNode
			});
			const missingPaths = ExhaustiveDepsUtils.computeFilteredMissingPaths({
				requiredRefs,
				allowlistedVariables,
				existingRootIdentifiers: queryKeyDeps.roots,
				existingFullPaths: queryKeyDeps.paths
			});
			if (missingPaths.length === 0) return;
			const missingAsText = missingPaths.join(", ");
			const suggestions = buildSuggestions({
				queryKeyNode,
				missingPaths,
				missingAsText,
				sourceCode: context.sourceCode
			});
			context.report({
				node,
				messageId: "missingDeps",
				data: { deps: missingAsText },
				suggest: suggestions
			});
		} };
	})
});
function buildSuggestions(params) {
	const { queryKeyNode, missingPaths, missingAsText, sourceCode } = params;
	if (queryKeyNode.type !== _typescript_eslint_utils.AST_NODE_TYPES.ArrayExpression) return [];
	const closingBracket = sourceCode.getLastToken(queryKeyNode);
	if (!closingBracket) return [];
	const resultText = `[${[...queryKeyNode.elements.filter((el) => el !== null).map((el) => sourceCode.getText(el)), ...missingPaths].join(", ")}]`;
	if (queryKeyNode.elements.length === 0) return [{
		messageId: "fixTo",
		data: { result: resultText },
		fix: (fixer) => fixer.replaceText(queryKeyNode, resultText)
	}];
	const separator = sourceCode.getTokenBefore(closingBracket)?.value === "," ? " " : ", ";
	return [{
		messageId: "fixTo",
		data: { result: resultText },
		fix: (fixer) => fixer.insertTextBefore(closingBracket, `${separator}${missingAsText}`)
	}];
}
function dereferenceVariablesAndTypeAssertions(queryKeyNode, context) {
	const visitedNodes = /* @__PURE__ */ new Set();
	for (let i = 0; i < 256; ++i) {
		if (visitedNodes.has(queryKeyNode)) return queryKeyNode;
		visitedNodes.add(queryKeyNode);
		switch (queryKeyNode.type) {
			case _typescript_eslint_utils.AST_NODE_TYPES.TSAsExpression:
				queryKeyNode = queryKeyNode.expression;
				break;
			case _typescript_eslint_utils.AST_NODE_TYPES.Identifier: {
				const expression = ASTUtils.getReferencedExpressionByIdentifier({
					context,
					node: queryKeyNode
				});
				if (expression == null) return queryKeyNode;
				queryKeyNode = expression;
				break;
			}
			default: return queryKeyNode;
		}
	}
	return queryKeyNode;
}
//#endregion
//#region src/rules/stable-query-client/stable-query-client.rule.ts
const name$6 = "stable-query-client";
const rule$6 = _typescript_eslint_utils.ESLintUtils.RuleCreator(getDocsUrl)({
	name: name$6,
	meta: {
		type: "problem",
		docs: {
			description: "Makes sure that QueryClient is stable",
			recommended: "error"
		},
		messages: {
			unstable: ["QueryClient is not stable. It should be either extracted from the component or wrapped in React.useState.", "See https://tkdodo.eu/blog/react-query-fa-qs#2-the-queryclient-is-not-stable"].join("\n"),
			fixTo: "Fix to {{result}}"
		},
		hasSuggestions: true,
		fixable: "code",
		schema: []
	},
	defaultOptions: [],
	create: detectTanstackQueryImports((context, _, helpers) => {
		return { NewExpression: (node) => {
			if (node.callee.type !== _typescript_eslint_utils.AST_NODE_TYPES.Identifier || node.callee.name !== "QueryClient" || node.parent.type !== _typescript_eslint_utils.AST_NODE_TYPES.VariableDeclarator || !helpers.isSpecificTanstackQueryImport(node.callee, "@tanstack/react-query")) return;
			const fnAncestor = ASTUtils.getFunctionAncestor(context.sourceCode, node);
			const isReactServerComponent = fnAncestor?.async === true;
			if (!ASTUtils.isValidReactComponentOrHookName(fnAncestor?.id) || isReactServerComponent) return;
			context.report({
				node: node.parent,
				messageId: "unstable",
				fix: (() => {
					const { parent } = node;
					if (parent.id.type !== _typescript_eslint_utils.AST_NODE_TYPES.Identifier) return;
					const nodeText = (context.sourceCode ?? context.getSourceCode()).getText(node);
					const variableName = parent.id.name;
					return (fixer) => {
						return fixer.replaceTextRange([parent.range[0], parent.range[1]], `[${variableName}] = React.useState(() => ${nodeText})`);
					};
				})()
			});
		} };
	})
});
//#endregion
//#region src/rules/no-rest-destructuring/no-rest-destructuring.utils.ts
const QUERY_RESULT_TYPE_NAMES = /* @__PURE__ */ new Set([
	"UseBaseQueryResult",
	"UseQueryResult",
	"UseSuspenseQueryResult",
	"DefinedUseQueryResult",
	"UseInfiniteQueryResult",
	"UseSuspenseInfiniteQueryResult",
	"DefinedUseInfiniteQueryResult",
	"QueryObserverResult",
	"InfiniteQueryObserverResult"
]);
function isQueryResultType(type) {
	if (type.aliasSymbol && QUERY_RESULT_TYPE_NAMES.has(type.aliasSymbol.name)) return true;
	const symbol = type.getSymbol();
	if (symbol && QUERY_RESULT_TYPE_NAMES.has(symbol.name)) return true;
	return type.isUnion() && type.types.some(isQueryResultType);
}
const NoRestDestructuringUtils = {
	isObjectRestDestructuring(node) {
		if (node.type !== _typescript_eslint_utils.AST_NODE_TYPES.ObjectPattern) return false;
		return node.properties.some((p) => p.type === _typescript_eslint_utils.AST_NODE_TYPES.RestElement);
	},
	isQueryResultCall(node, parserServices) {
		if (!parserServices?.program || !parserServices.esTreeNodeToTSNodeMap) return false;
		const checker = parserServices.program.getTypeChecker();
		const tsNode = parserServices.esTreeNodeToTSNodeMap.get(node.callee);
		return checker.getTypeAtLocation(tsNode).getCallSignatures().some((sig) => isQueryResultType(sig.getReturnType()));
	}
};
//#endregion
//#region src/rules/no-rest-destructuring/no-rest-destructuring.rule.ts
const name$5 = "no-rest-destructuring";
const queryHooks$1 = [
	"useQuery",
	"useQueries",
	"useInfiniteQuery",
	"useSuspenseQuery",
	"useSuspenseQueries",
	"useSuspenseInfiniteQuery"
];
const rule$5 = _typescript_eslint_utils.ESLintUtils.RuleCreator(getDocsUrl)({
	name: name$5,
	meta: {
		type: "problem",
		docs: {
			description: "Disallows rest destructuring in queries",
			recommended: "warn"
		},
		messages: { objectRestDestructure: `Object rest destructuring on a query will observe all changes to the query, leading to excessive re-renders.` },
		schema: []
	},
	defaultOptions: [],
	create: detectTanstackQueryImports((context, _, helpers) => {
		const queryResultVariables = /* @__PURE__ */ new Set();
		return {
			CallExpression: (node) => {
				if (node.parent.type !== _typescript_eslint_utils.AST_NODE_TYPES.VariableDeclarator) return;
				const returnValue = node.parent.id;
				if (!(ASTUtils.isIdentifierWithOneOfNames(node.callee, queryHooks$1) && helpers.isTanstackQueryImport(node.callee))) {
					if (!(returnValue.type === _typescript_eslint_utils.AST_NODE_TYPES.Identifier || NoRestDestructuringUtils.isObjectRestDestructuring(returnValue)) || !NoRestDestructuringUtils.isQueryResultCall(node, context.sourceCode.parserServices)) return;
				}
				const calleeName = ASTUtils.isIdentifier(node.callee) ? node.callee.name : null;
				if (calleeName !== "useQueries" && calleeName !== "useSuspenseQueries") {
					if (NoRestDestructuringUtils.isObjectRestDestructuring(returnValue)) return context.report({
						node: node.parent,
						messageId: "objectRestDestructure"
					});
					if (returnValue.type === _typescript_eslint_utils.AST_NODE_TYPES.Identifier) queryResultVariables.add(returnValue.name);
					return;
				}
				if (returnValue.type !== _typescript_eslint_utils.AST_NODE_TYPES.ArrayPattern) {
					if (returnValue.type === _typescript_eslint_utils.AST_NODE_TYPES.Identifier) queryResultVariables.add(returnValue.name);
					return;
				}
				returnValue.elements.forEach((queryResult) => {
					if (queryResult === null) return;
					if (NoRestDestructuringUtils.isObjectRestDestructuring(queryResult)) context.report({
						node: queryResult,
						messageId: "objectRestDestructure"
					});
				});
			},
			VariableDeclarator: (node) => {
				if (node.init?.type === _typescript_eslint_utils.AST_NODE_TYPES.Identifier && queryResultVariables.has(node.init.name) && NoRestDestructuringUtils.isObjectRestDestructuring(node.id)) context.report({
					node,
					messageId: "objectRestDestructure"
				});
			},
			SpreadElement: (node) => {
				if (node.argument.type === _typescript_eslint_utils.AST_NODE_TYPES.Identifier && queryResultVariables.has(node.argument.name)) context.report({
					node,
					messageId: "objectRestDestructure"
				});
			}
		};
	})
});
//#endregion
//#region src/rules/no-unstable-deps/no-unstable-deps.rule.ts
const name$4 = "no-unstable-deps";
const reactHookNames = [
	"useEffect",
	"useCallback",
	"useMemo"
];
const allHookNames = ["useMutation", ...[
	"useQuery",
	"useSuspenseQuery",
	"useQueries",
	"useSuspenseQueries",
	"useInfiniteQuery",
	"useSuspenseInfiniteQuery"
]];
const rule$4 = _typescript_eslint_utils.ESLintUtils.RuleCreator(getDocsUrl)({
	name: name$4,
	meta: {
		type: "problem",
		docs: {
			description: "Disallow putting the result of query hooks directly in a React hook dependency array",
			recommended: "error"
		},
		messages: { noUnstableDeps: `The result of {{queryHook}} is not referentially stable, so don't pass it directly into the dependencies array of {{reactHook}}. Instead, destructure the return value of {{queryHook}} and pass the destructured values into the dependency array of {{reactHook}}.` },
		schema: []
	},
	defaultOptions: [],
	create: detectTanstackQueryImports((context, _options, helpers) => {
		const trackedVariables = Object.create(null);
		const trackedCustomHooks = Object.create(null);
		const hookAliasMap = Object.create(null);
		const pendingVariableDeclarators = [];
		const pendingDependencyChecks = [];
		function getReactHook(node) {
			if (node.callee.type === "Identifier") {
				const calleeName = node.callee.name;
				if (reactHookNames.includes(calleeName) || calleeName in hookAliasMap) return calleeName;
			} else if (node.callee.type === "MemberExpression" && node.callee.object.type === "Identifier" && node.callee.object.name === "React" && node.callee.property.type === "Identifier" && reactHookNames.includes(node.callee.property.name)) return node.callee.property.name;
		}
		function collectVariableNames(pattern, queryHook) {
			if (pattern.type === _typescript_eslint_utils.AST_NODE_TYPES.Identifier) trackedVariables[pattern.name] = queryHook;
			else if (pattern.type === _typescript_eslint_utils.AST_NODE_TYPES.ArrayPattern) for (const element of pattern.elements) {
				if (element === null) continue;
				if (element.type === _typescript_eslint_utils.AST_NODE_TYPES.Identifier) trackedVariables[element.name] = queryHook;
				else if (element.type === _typescript_eslint_utils.AST_NODE_TYPES.RestElement && element.argument.type === _typescript_eslint_utils.AST_NODE_TYPES.Identifier) trackedVariables[element.argument.name] = queryHook;
			}
		}
		function isCustomHookName(hookName) {
			return /^use[A-Z0-9]/.test(hookName);
		}
		function hasCombineProperty(callExpression) {
			if (callExpression.arguments.length === 0) return false;
			const firstArg = callExpression.arguments[0];
			if (!firstArg || firstArg.type !== _typescript_eslint_utils.AST_NODE_TYPES.ObjectExpression) return false;
			return firstArg.properties.some((prop) => prop.type === _typescript_eslint_utils.AST_NODE_TYPES.Property && prop.key.type === _typescript_eslint_utils.AST_NODE_TYPES.Identifier && prop.key.name === "combine");
		}
		function getDirectQueryHook(callExpression) {
			if (callExpression.callee.type !== _typescript_eslint_utils.AST_NODE_TYPES.Identifier || !allHookNames.includes(callExpression.callee.name) || !helpers.isTanstackQueryImport(callExpression.callee)) return;
			if ((callExpression.callee.name === "useQueries" || callExpression.callee.name === "useSuspenseQueries") && hasCombineProperty(callExpression)) return;
			return callExpression.callee.name;
		}
		function getTrackedQueryHook(callExpression) {
			const directQueryHook = getDirectQueryHook(callExpression);
			if (directQueryHook !== void 0) return directQueryHook;
			if (callExpression.callee.type === _typescript_eslint_utils.AST_NODE_TYPES.Identifier) return trackedCustomHooks[callExpression.callee.name];
		}
		function getReturnedQueryHook(body) {
			if (body.type === _typescript_eslint_utils.AST_NODE_TYPES.CallExpression) return getDirectQueryHook(body);
			if (body.type !== _typescript_eslint_utils.AST_NODE_TYPES.BlockStatement) return;
			const returnStatements = body.body.filter((statement) => statement.type === _typescript_eslint_utils.AST_NODE_TYPES.ReturnStatement);
			if (returnStatements.length !== 1) return;
			const returnArgument = returnStatements[0]?.argument;
			if (returnArgument?.type === _typescript_eslint_utils.AST_NODE_TYPES.CallExpression) return getDirectQueryHook(returnArgument);
		}
		function checkDependencyArray(reactHook, depsArray) {
			depsArray.elements.forEach((dep) => {
				if (dep !== null && dep.type === _typescript_eslint_utils.AST_NODE_TYPES.Identifier && trackedVariables[dep.name] !== void 0) {
					const queryHook = trackedVariables[dep.name];
					context.report({
						node: dep,
						messageId: "noUnstableDeps",
						data: {
							queryHook,
							reactHook
						}
					});
				}
			});
		}
		return {
			ImportDeclaration(node) {
				if (node.specifiers.length > 0 && node.importKind === "value" && node.source.value === "React") node.specifiers.forEach((specifier) => {
					if (specifier.type === _typescript_eslint_utils.AST_NODE_TYPES.ImportSpecifier && specifier.imported.type === _typescript_eslint_utils.AST_NODE_TYPES.Identifier && reactHookNames.includes(specifier.imported.name)) hookAliasMap[specifier.local.name] = specifier.imported.name;
				});
			},
			FunctionDeclaration(node) {
				if (node.id === null || !isCustomHookName(node.id.name)) return;
				const queryHook = getReturnedQueryHook(node.body);
				if (queryHook !== void 0) trackedCustomHooks[node.id.name] = queryHook;
			},
			VariableDeclarator(node) {
				if (node.id.type === _typescript_eslint_utils.AST_NODE_TYPES.Identifier && isCustomHookName(node.id.name) && node.init !== null && (node.init.type === _typescript_eslint_utils.AST_NODE_TYPES.ArrowFunctionExpression || node.init.type === _typescript_eslint_utils.AST_NODE_TYPES.FunctionExpression)) {
					const queryHook = getReturnedQueryHook(node.init.body);
					if (queryHook !== void 0) trackedCustomHooks[node.id.name] = queryHook;
				}
				if (node.init !== null && node.init.type === _typescript_eslint_utils.AST_NODE_TYPES.CallExpression) pendingVariableDeclarators.push(node);
			},
			CallExpression: (node) => {
				const reactHook = getReactHook(node);
				if (reactHook !== void 0 && node.arguments.length > 1 && node.arguments[1]?.type === _typescript_eslint_utils.AST_NODE_TYPES.ArrayExpression) pendingDependencyChecks.push({
					reactHook,
					depsArray: node.arguments[1]
				});
			},
			"Program:exit"() {
				pendingVariableDeclarators.forEach((node) => {
					if (node.init?.type !== _typescript_eslint_utils.AST_NODE_TYPES.CallExpression) return;
					const queryHook = getTrackedQueryHook(node.init);
					if (queryHook !== void 0) collectVariableNames(node.id, queryHook);
				});
				pendingDependencyChecks.forEach(({ reactHook, depsArray }) => {
					checkDependencyArray(reactHook, depsArray);
				});
			}
		};
	})
});
//#endregion
//#region src/utils/sort-data-by-order.ts
function sortDataByOrder(data, orderRules, key) {
	const getSubsetIndex = (item, subsets) => {
		for (let i = 0; i < subsets.length; i++) if (subsets[i]?.includes(item)) return i;
		return null;
	};
	const orderSets = orderRules.reduce((sets, [A, B]) => [
		...sets,
		A,
		B
	], []);
	const inOrderArray = data.filter((item) => getSubsetIndex(item[key], orderSets) !== null);
	let wasResorted = false;
	const inOrderIterator = inOrderArray.sort((a, b) => {
		const aKey = a[key], bKey = b[key];
		const aSubsetIndex = getSubsetIndex(aKey, orderSets);
		const bSubsetIndex = getSubsetIndex(bKey, orderSets);
		if (aSubsetIndex !== null && bSubsetIndex !== null && aSubsetIndex !== bSubsetIndex) return aSubsetIndex - bSubsetIndex;
		return 0;
	}).values();
	const result = data.map((item) => {
		if (getSubsetIndex(item[key], orderSets) !== null) {
			const sortedItem = inOrderIterator.next().value;
			if (sortedItem[key] !== item[key]) wasResorted = true;
			return sortedItem;
		}
		return item;
	});
	if (!wasResorted) return null;
	return result;
}
//#endregion
//#region src/utils/create-property-order-rule.ts
const createRule$2 = _typescript_eslint_utils.ESLintUtils.RuleCreator(getDocsUrl);
function createPropertyOrderRule(options, targetFunctions, orderRules) {
	const targetFunctionSet = new Set(targetFunctions);
	function isTargetFunction(node) {
		return targetFunctionSet.has(node);
	}
	return createRule$2({
		...options,
		create: detectTanstackQueryImports((context) => {
			return { CallExpression(node) {
				if (node.callee.type !== _typescript_eslint_utils.AST_NODE_TYPES.Identifier) return;
				const functions = node.callee.name;
				if (!isTargetFunction(functions)) return;
				const argument = node.arguments[0];
				if (argument === void 0 || argument.type !== "ObjectExpression") return;
				const allProperties = argument.properties;
				if (allProperties.length < 2) return;
				const sortedProperties = sortDataByOrder(allProperties.flatMap((p, index) => {
					if (p.type === _typescript_eslint_utils.AST_NODE_TYPES.Property && p.key.type === _typescript_eslint_utils.AST_NODE_TYPES.Identifier) return {
						name: p.key.name,
						property: p
					};
					else return {
						name: `_property_${index}`,
						property: p
					};
				}), orderRules, "name");
				if (sortedProperties === null) return;
				context.report({
					node: argument,
					data: { function: node.callee.name },
					messageId: "invalidOrder",
					fix(fixer) {
						const sourceCode = context.sourceCode;
						const reorderedText = sortedProperties.reduce((sourceText, specifier, index) => {
							let textBetweenProperties = "";
							if (index < allProperties.length - 1) textBetweenProperties = sourceCode.getText().slice(allProperties[index].range[1], allProperties[index + 1].range[0]);
							return sourceText + sourceCode.getText(specifier.property) + textBetweenProperties;
						}, "");
						return fixer.replaceTextRange([allProperties[0].range[0], allProperties.at(-1).range[1]], reorderedText);
					}
				});
			} };
		})
	});
}
//#endregion
//#region src/rules/infinite-query-property-order/constants.ts
const infiniteQueryFunctions = [
	"infiniteQueryOptions",
	"useInfiniteQuery",
	"useSuspenseInfiniteQuery"
];
const sortRules$1 = [[["queryFn"], ["getPreviousPageParam", "getNextPageParam"]]];
//#endregion
//#region src/rules/infinite-query-property-order/infinite-query-property-order.rule.ts
const name$3 = "infinite-query-property-order";
const rule$3 = createPropertyOrderRule({
	name: name$3,
	meta: {
		type: "problem",
		docs: {
			description: "Ensure correct order of inference sensitive properties for infinite queries",
			recommended: "error"
		},
		messages: { invalidOrder: "Invalid order of properties for `{{function}}`." },
		schema: [],
		hasSuggestions: true,
		fixable: "code"
	},
	defaultOptions: []
}, infiniteQueryFunctions, sortRules$1);
//#endregion
//#region src/rules/no-void-query-fn/no-void-query-fn.rule.ts
const name$2 = "no-void-query-fn";
const rule$2 = _typescript_eslint_utils.ESLintUtils.RuleCreator(getDocsUrl)({
	name: name$2,
	meta: {
		type: "problem",
		docs: {
			description: "Ensures queryFn returns a non-undefined value",
			recommended: "error"
		},
		messages: { noVoidReturn: "queryFn must return a non-undefined value" },
		schema: []
	},
	defaultOptions: [],
	create: detectTanstackQueryImports((context) => {
		return { Property(node) {
			if (!ASTUtils.isObjectExpression(node.parent) || !ASTUtils.isIdentifierWithName(node.key, "queryFn")) return;
			const parserServices = context.sourceCode.parserServices;
			if (!parserServices || !parserServices.esTreeNodeToTSNodeMap || !parserServices.program) return;
			const checker = parserServices.program.getTypeChecker();
			const tsNode = parserServices.esTreeNodeToTSNodeMap.get(node.value);
			const type = checker.getTypeAtLocation(tsNode);
			if (type.getCallSignatures().length > 0) {
				const returnType = type.getCallSignatures()[0]?.getReturnType();
				if (!returnType) return;
				if (isIllegalReturn(checker, returnType)) context.report({
					node: node.value,
					messageId: "noVoidReturn"
				});
			}
		} };
	})
});
function isIllegalReturn(checker, type) {
	const awaited = checker.getAwaitedType(type);
	if (!awaited) return false;
	if (awaited.isUnion()) return awaited.types.some((t) => isIllegalReturn(checker, t));
	const typeString = checker.typeToString(awaited);
	return typeString === "void" || typeString === "undefined";
}
//#endregion
//#region src/rules/mutation-property-order/constants.ts
const mutationFunctions = ["useMutation"];
const sortRules = [[["onMutate"], ["onError", "onSettled"]]];
//#endregion
//#region src/rules/mutation-property-order/mutation-property-order.rule.ts
const name$1 = "mutation-property-order";
const rule$1 = createPropertyOrderRule({
	name: name$1,
	meta: {
		type: "problem",
		docs: {
			description: "Ensure correct order of inference-sensitive properties in useMutation()",
			recommended: "error"
		},
		messages: { invalidOrder: "Invalid order of properties for `{{function}}`." },
		schema: [],
		hasSuggestions: true,
		fixable: "code"
	},
	defaultOptions: []
}, mutationFunctions, sortRules);
//#endregion
//#region src/rules/prefer-query-options/prefer-query-options.rule.ts
const name = "prefer-query-options";
const queryHooks = [
	"useQuery",
	"useInfiniteQuery",
	"useSuspenseQuery",
	"useSuspenseInfiniteQuery",
	"usePrefetchQuery",
	"usePrefetchInfiniteQuery"
];
const queriesHooks = ["useQueries", "useSuspenseQueries"];
const filterHooks = ["useIsFetching"];
const queryClientOptionMethods = [
	"fetchQuery",
	"prefetchQuery",
	"fetchInfiniteQuery",
	"prefetchInfiniteQuery",
	"ensureQueryData",
	"ensureInfiniteQueryData"
];
const queryClientQueryKeyMethods = [
	"getQueryData",
	"setQueryData",
	"getQueryState",
	"setQueryDefaults",
	"getQueryDefaults"
];
const queryClientFilterMethods = [
	"invalidateQueries",
	"cancelQueries",
	"refetchQueries",
	"removeQueries",
	"resetQueries",
	"isFetching",
	"getQueriesData",
	"setQueriesData"
];
const queryOptionsBuilders = ["queryOptions", "infiniteQueryOptions"];
const rule = _typescript_eslint_utils.ESLintUtils.RuleCreator(getDocsUrl)({
	name,
	meta: {
		type: "problem",
		docs: {
			description: "Prefer using queryOptions() to co-locate queryKey and queryFn",
			recommended: "strict"
		},
		messages: {
			preferQueryOptions: "Prefer using queryOptions() or infiniteQueryOptions() to co-locate queryKey and queryFn.",
			preferQueryOptionsQueryKey: "Prefer referencing a queryKey from a queryOptions() result instead of typing it manually."
		},
		schema: []
	},
	defaultOptions: [],
	create: detectTanstackQueryImports((context, _, helpers) => {
		function reportInlineQueryOptions(node) {
			if (ASTUtils.isObjectExpression(node) && hasInlineQueryOptions(node)) context.report({
				node,
				messageId: "preferQueryOptions"
			});
		}
		function reportInlineFilterQueryKey(node) {
			if (ASTUtils.isObjectExpression(node) && hasInlineFilterQueryKey(node)) context.report({
				node,
				messageId: "preferQueryOptionsQueryKey"
			});
		}
		return { CallExpression: (node) => {
			if (ASTUtils.isIdentifier(node.callee)) {
				const importedName = getTanstackImportName(context, helpers, node.callee);
				if (importedName === null) return;
				if (queryOptionsBuilders.includes(importedName)) return;
				const options = node.arguments[0];
				if (options === void 0) return;
				if (queryHooks.includes(importedName)) {
					reportInlineQueryOptions(options);
					return;
				}
				if (queriesHooks.includes(importedName) && ASTUtils.isObjectExpression(options)) {
					const queries = ASTUtils.findPropertyWithIdentifierKey(options.properties, "queries")?.value;
					if (queries !== void 0) getQueryObjects(queries).forEach((query) => {
						reportInlineQueryOptions(query);
					});
					return;
				}
				if (filterHooks.includes(importedName)) reportInlineFilterQueryKey(options);
				return;
			}
			if (node.callee.type !== _typescript_eslint_utils.AST_NODE_TYPES.MemberExpression || !ASTUtils.isIdentifier(node.callee.property) || !isTanstackQueryClient(node.callee.object, context, helpers)) return;
			const method = node.callee.property.name;
			const options = node.arguments[0];
			if (options === void 0) return;
			if (queryClientOptionMethods.includes(method)) {
				reportInlineQueryOptions(options);
				return;
			}
			if (queryClientQueryKeyMethods.includes(method) && isInlineArrayExpression(options)) {
				context.report({
					node: options,
					messageId: "preferQueryOptionsQueryKey"
				});
				return;
			}
			if (queryClientFilterMethods.includes(method)) reportInlineFilterQueryKey(options);
		} };
	})
});
function hasInlineQueryOptions(node) {
	return ASTUtils.findPropertyWithIdentifierKey(node.properties, "queryKey") !== void 0 || ASTUtils.findPropertyWithIdentifierKey(node.properties, "queryFn") !== void 0;
}
function hasInlineFilterQueryKey(node) {
	const queryKey = ASTUtils.findPropertyWithIdentifierKey(node.properties, "queryKey")?.value;
	return queryKey !== void 0 && isInlineArrayExpression(queryKey);
}
function isInlineArrayExpression(node) {
	return unwrapTypeAssertions(node).type === _typescript_eslint_utils.AST_NODE_TYPES.ArrayExpression;
}
function getReturnedObjectExpressions(node) {
	if (ASTUtils.isObjectExpression(node)) return [node];
	if (node.type === _typescript_eslint_utils.AST_NODE_TYPES.ArrowFunctionExpression || node.type === _typescript_eslint_utils.AST_NODE_TYPES.FunctionExpression) return getReturnedObjectExpressions(node.body);
	if (node.type === _typescript_eslint_utils.AST_NODE_TYPES.BlockStatement) return node.body.flatMap((statement) => {
		if (statement.type === _typescript_eslint_utils.AST_NODE_TYPES.ReturnStatement && statement.argument !== null) return getReturnedObjectExpressions(statement.argument);
		return [];
	});
	if (node.type === _typescript_eslint_utils.AST_NODE_TYPES.ConditionalExpression) return [...getReturnedObjectExpressions(node.consequent), ...getReturnedObjectExpressions(node.alternate)];
	if (node.type === _typescript_eslint_utils.AST_NODE_TYPES.LogicalExpression) return [...getReturnedObjectExpressions(node.left), ...getReturnedObjectExpressions(node.right)];
	if (node.type === _typescript_eslint_utils.AST_NODE_TYPES.SequenceExpression) return node.expressions.flatMap((expression) => getReturnedObjectExpressions(expression));
	return [];
}
function getQueryObjects(node) {
	if (node.type === _typescript_eslint_utils.AST_NODE_TYPES.ArrayExpression) return node.elements.flatMap((element) => {
		if (element !== null && ASTUtils.isObjectExpression(element)) return [element];
		return [];
	});
	if (node.type === _typescript_eslint_utils.AST_NODE_TYPES.CallExpression && node.callee.type === _typescript_eslint_utils.AST_NODE_TYPES.MemberExpression && ASTUtils.isIdentifierWithName(node.callee.property, "map")) {
		const mapper = node.arguments[0];
		if (mapper?.type === _typescript_eslint_utils.AST_NODE_TYPES.ArrowFunctionExpression || mapper?.type === _typescript_eslint_utils.AST_NODE_TYPES.FunctionExpression) return getReturnedObjectExpressions(mapper);
	}
	return [];
}
function isTanstackQueryClient(node, context, helpers) {
	const source = resolveQueryClientSource(node, context);
	if (source.type === _typescript_eslint_utils.AST_NODE_TYPES.CallExpression && ASTUtils.isIdentifier(source.callee)) return getTanstackImportName(context, helpers, source.callee) === "useQueryClient";
	if (source.type === _typescript_eslint_utils.AST_NODE_TYPES.NewExpression && ASTUtils.isIdentifier(source.callee)) return getTanstackImportName(context, helpers, source.callee) === "QueryClient";
	return false;
}
function getTanstackImportName(context, helpers, node) {
	if (!helpers.isTanstackQueryImport(node)) return null;
	const definition = context.sourceCode.getScope(node).references.find((reference) => reference.identifier === node)?.resolved?.defs[0]?.node;
	if (definition?.type !== _typescript_eslint_utils.AST_NODE_TYPES.ImportSpecifier || definition.imported.type !== _typescript_eslint_utils.AST_NODE_TYPES.Identifier) return null;
	return definition.imported.name;
}
function resolveQueryClientSource(node, context) {
	const visitedNodes = /* @__PURE__ */ new Set();
	while (!visitedNodes.has(node)) {
		visitedNodes.add(node);
		if (node.type === _typescript_eslint_utils.AST_NODE_TYPES.ChainExpression) {
			node = node.expression;
			continue;
		}
		node = unwrapTypeAssertions(node);
		if (node.type !== _typescript_eslint_utils.AST_NODE_TYPES.Identifier) return node;
		const expression = ASTUtils.getReferencedExpressionByIdentifier({
			context,
			node
		});
		if (expression === null) return node;
		node = expression;
	}
	return node;
}
function unwrapTypeAssertions(node) {
	while (node.type === _typescript_eslint_utils.AST_NODE_TYPES.TSAsExpression || node.type === _typescript_eslint_utils.AST_NODE_TYPES.TSSatisfiesExpression || node.type === _typescript_eslint_utils.AST_NODE_TYPES.TSTypeAssertion) node = node.expression;
	return node;
}
//#endregion
//#region src/rules.ts
const rules = {
	[name$7]: rule$7,
	[name$6]: rule$6,
	[name$5]: rule$5,
	[name$4]: rule$4,
	[name$3]: rule$3,
	[name$2]: rule$2,
	[name$1]: rule$1,
	[name]: rule
};
//#endregion
Object.defineProperty(exports, "rules", {
	enumerable: true,
	get: function() {
		return rules;
	}
});


//# sourceMappingURL=rules-B1yVUvLh.cjs.map