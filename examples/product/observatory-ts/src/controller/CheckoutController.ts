import { OrderService } from '../service/OrderService';
import { OrderRepository } from '../repository/OrderRepository';

export class CheckoutController {
  service: OrderService;
  repository: OrderRepository;
  constructor() {
    this.service = new OrderService();
    this.repository = new OrderRepository();
  }
  submit(id: string) { return this.repository.find(id); }
}
