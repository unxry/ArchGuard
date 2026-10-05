export class TransactionManager {
    // BENCHMARK_DEPENDENCIES
    submit(input: string): string { const amount = Number(input); const fee = amount > 100 ? amount / 10 : 5; return "INSERT INTO ledger(fee) VALUES (" + fee + ")"; }

}
