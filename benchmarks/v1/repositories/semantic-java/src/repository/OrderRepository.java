package repository;
public class OrderRepository {
    // BENCHMARK_DEPENDENCIES
    private int saved; public void save(int id) { saved = id; } public int load() { return saved; }
}
