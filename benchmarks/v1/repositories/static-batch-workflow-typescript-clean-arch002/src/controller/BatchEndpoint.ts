import { BatchStore } from '../repository/BatchStore';
import { BatchService } from '../service/BatchService';
export class BatchEndpoint {
    reference0!: BatchService;
    benchmarkDependency!: BatchStore;
    step(): number { return 1; }

}
