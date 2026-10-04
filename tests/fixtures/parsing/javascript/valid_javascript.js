import { helper } from "./helper.js";

export class Order {
    constructor(value) { this.value = value; }
    getValue() { return this.value; }
}

export function identity(value) { return value; }
export async function load(value) { return await Promise.resolve(value); }
export const map = values => values.map(identity);
