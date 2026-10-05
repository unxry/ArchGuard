import { CommitPort } from '../domain/CommitPort';
export class Ledger {
    reference0!: CommitPort;
    // BENCHMARK_DEPENDENCIES
    commit(id: number): void { this.reference0.commit(id); }

}
