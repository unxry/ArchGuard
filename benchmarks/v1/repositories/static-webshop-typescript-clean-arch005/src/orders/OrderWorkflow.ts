import { SettlementInternal } from '../payments/SettlementInternal';
import { CheckoutService } from '../service/CheckoutService';
export class OrderWorkflow {
    reference0!: CheckoutService;
    benchmarkDependency!: SettlementInternal;
    step(): number { return 6; }

}
