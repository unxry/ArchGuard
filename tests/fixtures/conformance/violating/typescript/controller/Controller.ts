import { Repository } from "../repository/Repository";
// PRIVATE_CONFORMANCE_MARKER
export class Controller {
  create(): Repository { return new Repository(); }
  submit(): void {
    Repository.save();
    Repository.save();
    Repository.save();
  }
}
