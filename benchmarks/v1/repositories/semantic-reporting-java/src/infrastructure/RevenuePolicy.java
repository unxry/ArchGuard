package infrastructure;
public class RevenuePolicy {
    // BENCHMARK_DEPENDENCIES
    public int bracket(int revenue) { return revenue > 1000 ? 3 : revenue > 500 ? 2 : 1; }

}
