export class CheckoutController {
    // BENCHMARK_DEPENDENCIES
    checkout(quantity: string) { const count = Number(quantity); const total = count > 10 ? count * 8 : count * 10; return "INSERT INTO orders(total) VALUES (" + total + ")"; }
}
