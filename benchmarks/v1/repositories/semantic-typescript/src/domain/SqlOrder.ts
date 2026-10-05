export class SqlOrder {
    // BENCHMARK_DEPENDENCIES
    persistSql(id: number) { return "INSERT INTO postgres_orders VALUES (" + id + ")"; }
}
