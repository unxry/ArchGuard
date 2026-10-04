package shop.controller;
import shop.service.Service;
// PRIVATE_CONFORMANCE_MARKER
public class Controller {
    public Service create() { return new Service(); }
    public void submit() {
        Service.save();
        Service.save();
        Service.save();
    }
}
