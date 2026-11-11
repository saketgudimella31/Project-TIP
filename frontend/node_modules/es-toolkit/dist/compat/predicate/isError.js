const require_getTag = require("../_internal/getTag.js");
const require_isPlainObject = require("./isPlainObject.js");
const require_isObjectLike = require("./isObjectLike.js");
// src/compat/predicate/isError.ts
/**
* Checks if `value` is an Error object.
*
* @param value The value to check.
* @returns Returns `true` if `value` is an Error object, `false` otherwise.
*
* @example
* ```typescript
* console.log(isError(new Error())); // true
* console.log(isError('Error')); // false
* console.log(isError({ name: 'Error', message: '' })); // false
* ```
*/
function isError(value) {
	if (!require_isObjectLike.isObjectLike(value)) return false;
	const tag = require_getTag.getTag(value);
	return tag === "[object Error]" || tag === "[object DOMException]" || typeof value.message === "string" && typeof value.name === "string" && !require_isPlainObject.isPlainObject(value);
}
exports.isError = isError;
