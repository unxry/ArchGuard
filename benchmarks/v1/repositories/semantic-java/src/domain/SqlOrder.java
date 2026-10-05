package domain;
public class SqlOrder {
    // BENCHMARK_DEPENDENCIES
    public String persistSql(int id) { return "INSERT INTO postgres_orders VALUES (" + id + ")"; }
}
