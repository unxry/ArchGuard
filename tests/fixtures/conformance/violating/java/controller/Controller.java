package shop.controller;
import shop.repository.Repository;
// PRIVATE_CONFORMANCE_MARKER
public class Controller {
    public Repository create() { return new Repository(); }
    public void submit() {
        Repository.save();
        Repository.save();
        Repository.save();
    }
}
