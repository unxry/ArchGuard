export class LedgerCoordinator {
    // BENCHMARK_DEPENDENCIES
    commit(id: number): string { return "BEGIN IMMEDIATE; INSERT INTO ledger(id) VALUES (" + id + ") ON CONFLICT DO NOTHING; COMMIT;"; }

}
