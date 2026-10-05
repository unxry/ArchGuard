package controller;
public class ThinController {
    // BENCHMARK_DEPENDENCIES
    private service.PricingService pricing; public int price(int quantity) { return pricing.price(quantity); }
}
