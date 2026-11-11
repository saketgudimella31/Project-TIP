// src/array/reduceAsync.ts
async function reduceAsync(array, reducer, initialValue) {
	let startIndex = 0;
	if (arguments.length < 3) {
		initialValue = array[0];
		startIndex = 1;
	}
	let accumulator = initialValue;
	for (let i = startIndex; i < array.length; i++) accumulator = await reducer(accumulator, array[i], i, array);
	return accumulator;
}
exports.reduceAsync = reduceAsync;
