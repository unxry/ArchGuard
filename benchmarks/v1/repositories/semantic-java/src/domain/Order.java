package domain;
public class Order {
    // BENCHMARK_DEPENDENCIES
    private OrderPort port; public void save(int id) { port.save(id); }
}
