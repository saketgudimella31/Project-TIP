import { getTag } from "../_internal/getTag.mjs";
import { isPlainObject } from "./isPlainObject.mjs";
import { isObjectLike } from "./isObjectLike.mjs";
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
	if (!isObjectLike(value)) return false;
	const tag = getTag(value);
	return tag === "[object Error]" || tag === "[object DOMException]" || typeof value.message === "string" && typeof value.name === "string" && !isPlainObject(value);
}
export { isError };
