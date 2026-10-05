package controller;
public class PricingController {
    // BENCHMARK_DEPENDENCIES
    public int price(int quantity) { int subtotal = quantity > 10 ? quantity * 8 : quantity * 10; return subtotal + subtotal / 5; }
}
