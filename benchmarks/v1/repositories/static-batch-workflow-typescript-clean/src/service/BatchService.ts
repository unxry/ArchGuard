import { Batch } from '../domain/Batch';
import { BatchStore } from '../repository/BatchStore';
export class BatchService {
    reference0!: Batch;
    reference1!: BatchStore;
    // BENCHMARK_DEPENDENCIES
    step(): number { return 2; }

}
