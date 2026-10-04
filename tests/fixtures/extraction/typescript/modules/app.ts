import Base, { work as run } from "./lib"; import * as library from "./lib"; import "@scope/pkg/subpath"; export function start() { run(); library.work(); new Base(); } export { work } from "./lib";
