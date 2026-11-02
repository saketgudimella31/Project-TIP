import { removeAccents } from "./remove-accents.js";

//#region src/index.ts
/**
* @name match-sorter
* @license MIT license.
* @copyright (c) 2099 Kent C. Dodds
* @author Kent C. Dodds <me@kentcdodds.com> (https://kentcdodds.com)
*/
const rankings = {
	CASE_SENSITIVE_EQUAL: 7,
	EQUAL: 6,
	STARTS_WITH: 5,
	WORD_STARTS_WITH: 4,
	CONTAINS: 3,
	ACRONYM: 2,
	MATCHES: 1,
	NO_MATCH: 0
};
/**
* Gets the highest ranking value for the given item based on its values for the given keys
* @param {*} item - the item to rank
* @param {String} value - the value to rank against
* @param {Object} options - options to control the ranking
* @return {{rank: Number, accessorIndex: Number, accessorThreshold: Number}} - the highest ranking
*/
function rankItem(item, value, options) {
	options = options || {};
	options.threshold = options.threshold ?? rankings.MATCHES;
	if (!options.accessors) {
		const rank = getMatchRanking(item, value, options);
		return {
			rankedValue: item,
			rank,
			accessorIndex: -1,
			accessorThreshold: options.threshold,
			passed: rank >= options.threshold
		};
	}
	const valuesToRank = getAllValuesToRank(item, options.accessors);
	const rankingInfo = {
		rankedValue: item,
		rank: rankings.NO_MATCH,
		accessorIndex: -1,
		accessorThreshold: options.threshold,
		passed: false
	};
	for (let i = 0; i < valuesToRank.length; i++) {
		const rankValue = valuesToRank[i];
		let newRank = getMatchRanking(rankValue.itemValue, value, options);
		const { minRanking, maxRanking, threshold = options.threshold } = rankValue.attributes;
		if (newRank < minRanking && newRank >= rankings.MATCHES) newRank = minRanking;
		else if (newRank > maxRanking) newRank = maxRanking;
		newRank = Math.min(newRank, maxRanking);
		if (newRank >= threshold && newRank > rankingInfo.rank) {
			rankingInfo.rank = newRank;
			rankingInfo.passed = true;
			rankingInfo.accessorIndex = i;
			rankingInfo.accessorThreshold = threshold;
			rankingInfo.rankedValue = rankValue.itemValue;
		}
	}
	return rankingInfo;
}
/**
* Gives a rankings score based on how well the two strings match.
* @param {String} testString - the string to test against
* @param {String} stringToRank - the string to rank
* @param {Object} options - options for the match (like keepDiacritics for comparison)
* @returns {Number} the ranking for how well stringToRank matches testString
*/
function getMatchRanking(testString, stringToRank, options) {
	testString = prepareValueForComparison(testString, options);
	stringToRank = prepareValueForComparison(stringToRank, options);
	if (stringToRank.length > testString.length) return rankings.NO_MATCH;
	if (testString === stringToRank) return rankings.CASE_SENSITIVE_EQUAL;
	testString = testString.toLowerCase();
	stringToRank = stringToRank.toLowerCase();
	if (testString === stringToRank) return rankings.EQUAL;
	if (testString.startsWith(stringToRank)) return rankings.STARTS_WITH;
	if (testString.includes(` ${stringToRank}`)) return rankings.WORD_STARTS_WITH;
	if (testString.includes(stringToRank)) return rankings.CONTAINS;
	else if (stringToRank.length === 1) return rankings.NO_MATCH;
	if (getAcronym(testString).includes(stringToRank)) return rankings.ACRONYM;
	return getClosenessRanking(testString, stringToRank);
}
/**
* Generates an acronym for a string.
*
* @param {String} string the string for which to produce the acronym
* @returns {String} the acronym
*/
function getAcronym(string) {
	let acronym = "";
	string.split(" ").forEach((wordInString) => {
		wordInString.split("-").forEach((splitByHyphenWord) => {
			acronym += splitByHyphenWord.substr(0, 1);
		});
	});
	return acronym;
}
/**
* Returns a score based on how spread apart the
* characters from the stringToRank are within the testString.
* A number close to rankings.MATCHES represents a loose match. A number close
* to rankings.MATCHES + 1 represents a tighter match.
* @param {String} testString - the string to test against
* @param {String} stringToRank - the string to rank
* @returns {Number} the number between rankings.MATCHES and
* rankings.MATCHES + 1 for how well stringToRank matches testString
*/
function getClosenessRanking(testString, stringToRank) {
	let matchingInOrderCharCount = 0;
	let charNumber = 0;
	function findMatchingCharacter(matchChar, string, index) {
		for (let j = index, J = string.length; j < J; j++) if (string[j] === matchChar) {
			matchingInOrderCharCount += 1;
			return j + 1;
		}
		return -1;
	}
	function getRanking(spread) {
		const spreadPercentage = 1 / spread;
		const inOrderPercentage = matchingInOrderCharCount / stringToRank.length;
		return rankings.MATCHES + inOrderPercentage * spreadPercentage;
	}
	const firstIndex = findMatchingCharacter(stringToRank[0], testString, 0);
	if (firstIndex < 0) return rankings.NO_MATCH;
	charNumber = firstIndex;
	for (let i = 1, I = stringToRank.length; i < I; i++) {
		const matchChar = stringToRank[i];
		charNumber = findMatchingCharacter(matchChar, testString, charNumber);
		if (!(charNumber > -1)) return rankings.NO_MATCH;
	}
	return getRanking(charNumber - firstIndex);
}
/**
* Sorts items that have a rank, index, and accessorIndex
* @param {Object} a - the first item to sort
* @param {Object} b - the second item to sort
* @return {Number} -1 if a should come first, 1 if b should come first, 0 if equal
*/
function compareItems(a, b) {
	return a.rank === b.rank ? 0 : a.rank > b.rank ? -1 : 1;
}
/**
* Prepares value for comparison by stringifying it, removing diacritics (if specified)
* @param {String} value - the value to clean
* @param {Object} options - {keepDiacritics: whether to remove diacritics}
* @return {String} the prepared value
*/
function prepareValueForComparison(value, { keepDiacritics }) {
	value = `${value}`;
	if (!keepDiacritics) value = removeAccents(value);
	return value;
}
/**
* Gets value for key in item at arbitrarily nested keypath
* @param {Object} item - the item
* @param {Object|Function} key - the potentially nested keypath or property callback
* @return {Array} - an array containing the value(s) at the nested keypath
*/
function getItemValues(item, accessor) {
	let accessorFn = accessor;
	if (typeof accessor === "object") accessorFn = accessor.accessor;
	const value = accessorFn(item);
	if (value == null) return [];
	if (Array.isArray(value)) return value;
	return [String(value)];
}
/**
* Gets all the values for the given keys in the given item and returns an array of those values
* @param item - the item from which the values will be retrieved
* @param keys - the keys to use to retrieve the values
* @return objects with {itemValue, attributes}
*/
function getAllValuesToRank(item, accessors) {
	const allValues = [];
	for (let j = 0, J = accessors.length; j < J; j++) {
		const accessor = accessors[j];
		const attributes = getAccessorAttributes(accessor);
		const itemValues = getItemValues(item, accessor);
		for (let i = 0, I = itemValues.length; i < I; i++) allValues.push({
			itemValue: itemValues[i],
			attributes
		});
	}
	return allValues;
}
const defaultKeyAttributes = {
	maxRanking: Infinity,
	minRanking: -Infinity
};
/**
* Gets all the attributes for the given accessor
* @param accessor - the accessor from which the attributes will be retrieved
* @return object containing the accessor's attributes
*/
function getAccessorAttributes(accessor) {
	if (typeof accessor === "function") return defaultKeyAttributes;
	return {
		...defaultKeyAttributes,
		...accessor
	};
}

//#endregion
export { compareItems, rankItem, rankings };