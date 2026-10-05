import { A } from "../a/A";
// GRAPH_PRIVATE_SOURCE_MARKER
export class C {
  static run(): void { A.ping(); A.ping(); C.ping(); }
  static ping(): void {}
}
