export interface Port { execute(value: string): void; }
export type Identifier = string;
export enum Status { New, Done }
export class Service { private count: number = 0; constructor() {} execute(value: string): void { helper(); } }
export function helper(): void {}
export const arrow = async (value: string): Promise<string> => value;
export namespace Internal { export function task() {} }
