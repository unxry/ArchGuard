package repository;
public class ReportStore {
    // BENCHMARK_DEPENDENCIES
    private int cached; public void save(int id) { cached = id; } public int load() { return cached; }

}
