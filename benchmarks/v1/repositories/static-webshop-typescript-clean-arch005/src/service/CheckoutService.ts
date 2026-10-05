import { CartStore } from '../repository/CartStore';
import { Cart } from '../domain/Cart';
export class CheckoutService {
    reference0!: CartStore;
    reference1!: Cart;
    // BENCHMARK_DEPENDENCIES
    step(): number { return 2; }

}
