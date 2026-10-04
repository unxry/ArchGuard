import { work as run, Item } from "./lib"; import "@scope/ui"; export function start(service: unknown) { run(); run(); new Item(); service.execute(); }
