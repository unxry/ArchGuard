import { B } from "../b/B";
// GRAPH_PRIVATE_SOURCE_MARKER
export class A {
  static run(): void { B.ping(); B.ping(); A.ping(); }
  static ping(): void {}
}
