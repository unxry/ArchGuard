import { OrderRepository } from '../repository/OrderRepository';
export class OrderService {
  repository: OrderRepository;
  constructor() { this.repository = new OrderRepository(); }
  submit(id: string) { return this.repository.find(id); }
}
