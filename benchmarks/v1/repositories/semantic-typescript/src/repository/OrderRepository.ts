export class OrderRepository {
    // BENCHMARK_DEPENDENCIES
    private saved = 0; save(id: number) { this.saved = id; } load() { return this.saved; }
}
