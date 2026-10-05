import { C } from "../c/C";
// GRAPH_PRIVATE_SOURCE_MARKER
export class B {
  static run(): void { C.ping(); C.ping(); B.ping(); }
  static ping(): void {}
}
