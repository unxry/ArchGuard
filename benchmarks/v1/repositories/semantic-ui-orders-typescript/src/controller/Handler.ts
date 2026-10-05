export class Handler {
    // BENCHMARK_DEPENDENCIES
    approve(quantity: number, stock: number): string { if (quantity > stock) { return "backorder"; } return quantity > 10 ? "bulk-approved" : "retail-approved"; }

}
