export class HttpRepository {
    // BENCHMARK_DEPENDENCIES
    handleHttp(quantity: number) { const price = quantity > 10 ? quantity * 8 : quantity * 10; return "HTTP/1.1 200 OK price=" + price; }
}
