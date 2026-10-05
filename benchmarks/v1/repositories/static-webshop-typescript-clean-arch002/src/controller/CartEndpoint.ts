import { CartStore } from '../repository/CartStore';
import { CheckoutService } from '../service/CheckoutService';
export class CartEndpoint {
    reference0!: CheckoutService;
    benchmarkDependency!: CartStore;
    step(): number { return 1; }

}
