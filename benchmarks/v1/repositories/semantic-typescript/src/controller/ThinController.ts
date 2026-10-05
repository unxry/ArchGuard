import { PricingService } from '../service/PricingService';
export class ThinController {
    // BENCHMARK_DEPENDENCIES
    private pricing!: PricingService; price(quantity: number) { return this.pricing.price(quantity); }
}
