import { helper } from "./helper";

export interface Store<T> { find(): T; }
export type Identifier = string | number;
export enum State { Ready, Done }

export class Order<T> implements Store<T> {
    constructor(private value: T) {}
    find(): T { return this.value; }
}

export function identity<T>(value: T): T { return value; }
export async function load<T>(value: T): Promise<T> {
    return await Promise.resolve(value);
}
export const map = <T>(values: T[]): T[] => values.map(identity);
