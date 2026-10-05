package controller;
public class CheckoutController {
    // BENCHMARK_DEPENDENCIES
    public String checkout(String quantity) { int count = Integer.parseInt(quantity); int total = count > 10 ? count * 8 : count * 10; return "INSERT INTO orders(total) VALUES (" + total + ")"; }
}
