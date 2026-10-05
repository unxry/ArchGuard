package domain;
public class HttpRepository {
    // BENCHMARK_DEPENDENCIES
    public String handleHttp(int quantity) { int price = quantity > 10 ? quantity * 8 : quantity * 10; return "HTTP/1.1 200 OK price=" + price; }
}
