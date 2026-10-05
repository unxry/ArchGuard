export class PricingController {
    // BENCHMARK_DEPENDENCIES
    price(quantity: number) { const subtotal = quantity > 10 ? quantity * 8 : quantity * 10; return subtotal + subtotal / 5; }
}
