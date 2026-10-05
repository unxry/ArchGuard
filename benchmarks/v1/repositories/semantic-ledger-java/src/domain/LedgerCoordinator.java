package domain;
public class LedgerCoordinator {
    // BENCHMARK_DEPENDENCIES
    public String commit(int id) { return "BEGIN IMMEDIATE; INSERT INTO ledger(id) VALUES (" + id + ") ON CONFLICT DO NOTHING; COMMIT;"; }

}
