import { Unstable } from "./Unstable";
export class Stable {
  static run(): void { Unstable.ping(); }
  static ping(): void {}
  static one(): void {}
  static two(): void {}
}
