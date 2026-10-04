import { Service } from "../service/Service";
// PRIVATE_CONFORMANCE_MARKER
export class Controller {
  create(): Service { return new Service(); }
  submit(): void {
    Service.save();
    Service.save();
    Service.save();
  }
}
