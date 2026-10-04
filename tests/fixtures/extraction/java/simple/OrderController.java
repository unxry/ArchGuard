package shop;
import java.util.List;
public class OrderController {
 private OrderService service;
 public OrderController(OrderService service) { this.service = service; }
 public void submit() { helper(); helper(); service.execute(); new OrderService(); }
 private void helper() {}
}
class OrderService { public void execute() {} }
enum Status { NEW, DONE }
