import { L1 } from "./L1";
import { L2 } from "./L2";
import { L3 } from "./L3";
export class Unstable {
  static run(): void { L1.ping(); L2.ping(); L3.ping(); }
  static ping(): void {}
}
